"""Local web GUI server for signal monitoring."""

from __future__ import annotations

import csv
import json
import logging
import mimetypes
import threading
import time
from copy import deepcopy
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import yaml
import pandas as pd

from src.interfaces.gui.allocation_surface import summarize_allocation_surface
from src.interfaces.gui.candidate_surface import summarize_candidate_surface
from src.interfaces.gui.shadow_feedback_validation_surface import (
    summarize_shadow_feedback_validation_result,
)
from src.interfaces.gui.shadow_feedback_rollout_surface import (
    summarize_shadow_feedback_rollout_alignment,
)
from src.interfaces.gui.shadow_next_stage_surface import summarize_shadow_next_stage_execution

logger = logging.getLogger(__name__)

DEFAULT_SIGNAL_LOG = Path("logs") / "events" / "signal.gui.jsonl"
DEFAULT_EXPORT_DIR = Path("ui") / "web"
DEFAULT_PRICE_PREFERRED = Path("reports") / "price" / "usdjpy_m5.csv"
DEFAULT_PRICE_FALLBACK = Path("usdjpy_5m_2018-2024_utc.csv")
SYNC_TOTAL_STEPS = 2
SYNC_STAGE_LABELS: dict[str, str] = {
    "sync.start": "同期準備",
    "sync.backfill.start": "差分補完を実行中",
    "sync.backfill.done": "差分補完が完了",
    "sync.refresh.start": "最新データを更新中",
    "sync.refresh.done": "最新データ更新が完了",
    "sync.done": "同期完了",
}
GUI_STRATEGY_DISPLAY_OVERRIDES: dict[str, dict[str, str]] = {
    "m1_asia_compression_expansion_breakout": {
        "state": "recommended",
        "label": "本線",
        "note": "shadow/live候補",
    },
    "m1_baseline_donchian_upper_only": {
        "state": "recommended",
        "label": "採用",
        "note": "Donchian系の残し枠",
    },
    "m1_us_session_trend_pullback": {
        "state": "recommended",
        "label": "採用",
        "note": "US時間帯の残し枠",
    },
    "m1_baseline_donchian_long_only": {
        "state": "excluded",
        "label": "外す",
        "note": "upper_onlyと重複するためGUIでは区別表示",
    },
    "m1_baseline_donchian": {
        "state": "excluded",
        "label": "外す",
        "note": "fixed-assumption fail",
    },
    "m1_baseline_ma_rsi": {
        "state": "excluded",
        "label": "外す",
        "note": "fixed-assumption fail",
    },
    "m1_us_orb_vwap_retest": {
        "state": "excluded",
        "label": "外す",
        "note": "research-only fail",
    },
}


@dataclass(frozen=True)
class GuiOpsRuntimeConfig:
    symbol: str
    source_dir: Path
    manifest: Path
    validation_dir: Path
    latest_days: int
    gap_minutes: int
    chunk_hours: int
    gap_exclude_weekend: bool
    run_fetch_plan: bool
    provider: str
    symbols: list[str]
    timeframe: str
    lookback_hours: int
    raw_dir: Path
    curated_dir: Path
    metrics_path: Path
    price_csv_dir: Path
    bootstrap_rows: int
    profile_path: Path
    data_dir: Path
    feature_config: Path
    strategy_manifest: Path
    signal_log_path: Path
    backfill_days: int
    target_r_multiple: float
    ttl_bars: int
    trail_atr_mult: float | None
    spread_pips: float
    slippage_pips: float
    slippage_std: float
    interval_sec: int
    signals_csv_append: bool
    signals_csv_monthly: bool


class GuiOpsRuntimeController:
    def __init__(self, config: GuiOpsRuntimeConfig) -> None:
        self._config = config
        self._available_strategy_manifests = tuple(
            _discover_strategy_manifests(config.strategy_manifest)
        )
        self._selected_strategy_manifest = _normalize_manifest_path(config.strategy_manifest)
        self._manifest_payloads: dict[Path, dict[str, Any]] = _load_manifest_payloads(
            self._available_strategy_manifests
        )
        self._strategy_catalog = _build_strategy_catalog(self._manifest_payloads)
        self._selected_strategy_ids: tuple[str, ...] = _resolve_initial_selected_strategy_ids(
            selected_manifest=self._selected_strategy_manifest,
            manifest_payloads=self._manifest_payloads,
            strategy_catalog=self._strategy_catalog,
        )
        self._selected_run_sync = True
        self._selected_run_loop = True
        self._active_strategy_ids: tuple[str, ...] = ()
        self._active_strategy_manifest: Path | None = None
        self._active_run_sync = True
        self._active_run_loop = True
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event: threading.Event | None = None
        self._phase = "idle"
        self._started_at: str | None = None
        self._finished_at: str | None = None
        self._last_error: str | None = None
        self._loop_iterations = 0
        self._last_sync: dict[str, Any] | None = None
        self._sync_progress: dict[str, Any] | None = None
        self._sync_started_perf: float | None = None
        self._last_loop: dict[str, Any] | None = None
        self._recent_logs: list[str] = []

    def start(self, overrides: Mapping[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            if self._is_running_locked():
                snapshot = self._snapshot_locked()
                snapshot["accepted"] = False
                snapshot["reason"] = "already_running"
                return snapshot
            override_error = self._apply_overrides_locked(overrides)
            if override_error is not None:
                snapshot = self._snapshot_locked()
                snapshot["accepted"] = False
                snapshot["reason"] = override_error
                return snapshot
            try:
                self._active_strategy_manifest = _materialize_runtime_manifest(
                    selected_manifest=self._selected_strategy_manifest,
                    manifest_payloads=self._manifest_payloads,
                    strategy_catalog=self._strategy_catalog,
                    selected_strategy_ids=self._selected_strategy_ids,
                )
            except ValueError:
                snapshot = self._snapshot_locked()
                snapshot["accepted"] = False
                snapshot["reason"] = "strategy_manifest_build_failed"
                return snapshot
            self._active_strategy_ids = self._selected_strategy_ids
            self._stop_event = threading.Event()
            self._thread = threading.Thread(target=self._run_worker, daemon=True)
            self._phase = "starting"
            self._started_at = _utcnow_iso()
            self._finished_at = None
            self._last_error = None
            self._loop_iterations = 0
            self._last_sync = None
            self._sync_progress = None
            self._sync_started_perf = None
            self._last_loop = None
            self._recent_logs = []
            self._active_run_sync = self._selected_run_sync
            self._active_run_loop = self._selected_run_loop
            self._thread.start()
            snapshot = self._snapshot_locked()
            snapshot["accepted"] = True
            return snapshot

    def stop(self) -> dict[str, Any]:
        with self._lock:
            if self._stop_event is not None:
                self._stop_event.set()
                self._phase = "stopping"
                self._recent_logs.append(f"{_utcnow_iso()} stop requested")
                if len(self._recent_logs) > 200:
                    self._recent_logs = self._recent_logs[-200:]
            snapshot = self._snapshot_locked()
            snapshot["accepted"] = True
            return snapshot

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return self._snapshot_locked()

    def _is_running_locked(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _snapshot_locked(self) -> dict[str, Any]:
        running = self._is_running_locked()
        selected_manifest = self._active_strategy_manifest or self._selected_strategy_manifest
        selected_ids = self._active_strategy_ids if running else self._selected_strategy_ids
        run_sync = self._active_run_sync if running else self._selected_run_sync
        run_loop = self._active_run_loop if running else self._selected_run_loop
        sync_progress = self._sync_progress
        if isinstance(sync_progress, dict) and sync_progress.get("state") == "running":
            progress_pct = _clamp_pct(sync_progress.get("progress_pct"), default=0)
            elapsed_sec = _elapsed_sec(self._sync_started_perf)
            sync_progress = {
                **sync_progress,
                "elapsed_sec": elapsed_sec,
                "eta_sec": _estimate_eta_sec(elapsed_sec, progress_pct),
                "updated_at": _utcnow_iso(),
            }
        return {
            "status": "ok",
            "running": running,
            "phase": self._phase,
            "started_at": self._started_at,
            "finished_at": self._finished_at,
            "last_error": self._last_error,
            "loop_iterations": self._loop_iterations,
            "last_sync": self._last_sync,
            "sync_progress": sync_progress,
            "last_loop": self._last_loop,
            "symbol": self._config.symbol,
            "symbols": self._config.symbols,
            "provider": self._config.provider,
            "timeframe": self._config.timeframe,
            "interval_sec": self._config.interval_sec,
            "strategy_manifest": _display_path(selected_manifest),
            "selected_strategy_manifest": _display_path(self._selected_strategy_manifest),
            "available_strategy_manifests": [
                _display_path(path) for path in self._available_strategy_manifests
            ],
            "selected_strategy_ids": list(selected_ids),
            "run_sync": run_sync,
            "run_loop": run_loop,
            "available_strategies": [
                {
                    "id": strategy_id,
                    "name": str(meta.get("name") or strategy_id),
                    "source_manifest": _display_path(Path(str(meta.get("source_manifest")))),
                    **_strategy_ops_display(strategy_id),
                }
                for strategy_id, meta in sorted(
                    self._strategy_catalog.items(), key=lambda item: item[0]
                )
            ],
            "data_manifest": str(self._config.manifest),
            "source_dir": str(self._config.source_dir),
            "recent_logs": self._recent_logs[-20:],
        }

    def _append_log(self, message: str) -> None:
        with self._lock:
            self._recent_logs.append(f"{_utcnow_iso()} {message}")
            if len(self._recent_logs) > 200:
                self._recent_logs = self._recent_logs[-200:]

    def _update_sync_progress(self, event: str, payload: Mapping[str, Any] | None = None) -> None:
        progress_payload = payload or {}
        with self._lock:
            if self._sync_started_perf is None:
                self._sync_started_perf = time.perf_counter()
            elapsed_sec = int(max(0.0, time.perf_counter() - self._sync_started_perf))
            previous_progress = self._sync_progress or {}
            progress_pct = _clamp_pct(
                progress_payload.get("progress_pct"), default=previous_progress.get("progress_pct", 0)
            )
            step = _positive_int(progress_payload.get("step"), default=0)
            total_steps = _positive_int(progress_payload.get("total_steps"), default=SYNC_TOTAL_STEPS)
            eta_sec = _estimate_eta_sec(elapsed_sec, progress_pct)
            self._sync_progress = {
                "event": event,
                "stage": str(progress_payload.get("stage") or event),
                "stage_label": SYNC_STAGE_LABELS.get(event, event),
                "state": "running",
                "step": step,
                "total_steps": total_steps,
                "progress_pct": progress_pct,
                "elapsed_sec": elapsed_sec,
                "eta_sec": eta_sec,
                "updated_at": _utcnow_iso(),
            }

    def _mark_sync_done(self) -> None:
        with self._lock:
            elapsed_sec = _elapsed_sec(self._sync_started_perf)
            self._sync_progress = {
                "event": "sync.done",
                "stage": "sync.done",
                "stage_label": SYNC_STAGE_LABELS.get("sync.done", "同期完了"),
                "state": "done",
                "step": SYNC_TOTAL_STEPS,
                "total_steps": SYNC_TOTAL_STEPS,
                "progress_pct": 100,
                "elapsed_sec": elapsed_sec,
                "eta_sec": 0,
                "updated_at": _utcnow_iso(),
            }

    def _mark_sync_error(self, error: str) -> None:
        with self._lock:
            previous = self._sync_progress or {}
            self._sync_progress = {
                "event": str(previous.get("event") or "sync.error"),
                "stage": str(previous.get("stage") or "sync.error"),
                "stage_label": str(previous.get("stage_label") or "同期エラー"),
                "state": "error",
                "step": _positive_int(previous.get("step"), default=0),
                "total_steps": _positive_int(previous.get("total_steps"), default=SYNC_TOTAL_STEPS),
                "progress_pct": _clamp_pct(previous.get("progress_pct"), default=0),
                "elapsed_sec": _elapsed_sec(self._sync_started_perf),
                "eta_sec": None,
                "error": error,
                "updated_at": _utcnow_iso(),
            }

    def _mark_sync_stopped(self) -> None:
        with self._lock:
            previous = self._sync_progress or {}
            self._sync_progress = {
                "event": str(previous.get("event") or "sync.stopped"),
                "stage": "sync.stopped",
                "stage_label": "同期停止",
                "state": "stopped",
                "step": _positive_int(previous.get("step"), default=0),
                "total_steps": _positive_int(previous.get("total_steps"), default=SYNC_TOTAL_STEPS),
                "progress_pct": _clamp_pct(previous.get("progress_pct"), default=0),
                "elapsed_sec": _elapsed_sec(self._sync_started_perf),
                "eta_sec": None,
                "updated_at": _utcnow_iso(),
            }

    def _apply_overrides_locked(self, overrides: Mapping[str, Any] | None) -> str | None:
        if overrides is None:
            return None
        if not isinstance(overrides, Mapping):
            return "invalid_request_payload"

        raw_strategy_manifest = overrides.get("strategy_manifest")
        if raw_strategy_manifest is not None:
            if not isinstance(raw_strategy_manifest, str):
                return "invalid_strategy_manifest"
            strategy_manifest = raw_strategy_manifest.strip()
            if not strategy_manifest:
                return "invalid_strategy_manifest"
            candidate = _normalize_manifest_path(Path(strategy_manifest))
            if not candidate.exists():
                return "strategy_manifest_not_found"
            self._selected_strategy_manifest = candidate
            if candidate not in self._available_strategy_manifests:
                manifests = list(self._available_strategy_manifests)
                manifests.append(candidate)
                manifests.sort(key=lambda item: _display_path(item))
                self._available_strategy_manifests = tuple(manifests)
                self._manifest_payloads.update(_load_manifest_payloads([candidate]))
                self._strategy_catalog = _build_strategy_catalog(self._manifest_payloads)

        if "strategy_ids" in overrides:
            raw_strategy_ids = overrides.get("strategy_ids")
            if not isinstance(raw_strategy_ids, list):
                return "invalid_strategy_ids"
            selected_ids: list[str] = []
            seen: set[str] = set()
            for value in raw_strategy_ids:
                if not isinstance(value, str):
                    return "invalid_strategy_ids"
                strategy_id = value.strip()
                if not strategy_id or strategy_id in seen:
                    continue
                selected_ids.append(strategy_id)
                seen.add(strategy_id)
            if not selected_ids:
                return "empty_strategy_ids"
            unknown = [sid for sid in selected_ids if sid not in self._strategy_catalog]
            if unknown:
                return "unknown_strategy_ids"
            self._selected_strategy_ids = tuple(selected_ids)
        elif not self._selected_strategy_ids:
            self._selected_strategy_ids = _resolve_initial_selected_strategy_ids(
                selected_manifest=self._selected_strategy_manifest,
                manifest_payloads=self._manifest_payloads,
                strategy_catalog=self._strategy_catalog,
            )

        run_sync = self._selected_run_sync
        if "run_sync" in overrides:
            raw_run_sync = overrides.get("run_sync")
            if not isinstance(raw_run_sync, bool):
                return "invalid_run_sync"
            run_sync = raw_run_sync

        run_loop = self._selected_run_loop
        if "run_loop" in overrides:
            raw_run_loop = overrides.get("run_loop")
            if not isinstance(raw_run_loop, bool):
                return "invalid_run_loop"
            run_loop = raw_run_loop

        if not run_sync and not run_loop:
            return "invalid_run_mode"
        self._selected_run_sync = run_sync
        self._selected_run_loop = run_loop
        return None

    def _run_worker(self) -> None:
        from src.interfaces.cli.gui_sync import (
            GuiDataSyncError,
            GuiDataSyncStopped,
            run_gui_data_sync,
        )
        from tools.gui_ops_loop import run_gui_ops_once

        with self._lock:
            strategy_manifest = self._active_strategy_manifest or self._selected_strategy_manifest
            run_sync = self._active_run_sync
            run_loop = self._active_run_loop

        mode_parts = []
        if run_sync:
            mode_parts.append("sync")
        if run_loop:
            mode_parts.append("loop")
        self._append_log(f"worker started mode={'+'.join(mode_parts)}")
        stop_event = self._stop_event or threading.Event()
        try:
            if run_sync:
                self._append_log("sync started")
                with self._lock:
                    self._phase = "sync"
                    self._sync_started_perf = time.perf_counter()
                    self._sync_progress = {
                        "event": "sync.start",
                        "stage": "sync.start",
                        "stage_label": SYNC_STAGE_LABELS.get("sync.start", "同期準備"),
                        "state": "running",
                        "step": 0,
                        "total_steps": SYNC_TOTAL_STEPS,
                        "progress_pct": 1,
                        "elapsed_sec": 0,
                        "eta_sec": None,
                        "updated_at": _utcnow_iso(),
                    }
                sync_result = run_gui_data_sync(
                    symbol=self._config.symbol,
                    source_dir=self._config.source_dir,
                    manifest=self._config.manifest,
                    validation_dir=self._config.validation_dir,
                    latest_days=self._config.latest_days,
                    gap_minutes=self._config.gap_minutes,
                    chunk_hours=self._config.chunk_hours,
                    gap_exclude_weekend=self._config.gap_exclude_weekend,
                    run_fetch_plan=self._config.run_fetch_plan,
                    progress_hook=self._update_sync_progress,
                    should_stop=stop_event.is_set,
                )
                self._mark_sync_done()
                sync_payload = sync_result.to_dict()
                with self._lock:
                    self._last_sync = sync_payload
                for warning in sync_payload.get("warnings", []):
                    self._append_log(f"sync warning: {warning}")
                self._append_log("sync finished")
            else:
                with self._lock:
                    self._sync_started_perf = None
                    self._sync_progress = {
                        "event": "sync.skipped",
                        "stage": "sync.skipped",
                        "stage_label": "同期スキップ",
                        "state": "skipped",
                        "step": 0,
                        "total_steps": SYNC_TOTAL_STEPS,
                        "progress_pct": 100,
                        "elapsed_sec": 0,
                        "eta_sec": 0,
                        "updated_at": _utcnow_iso(),
                    }
                self._append_log("sync skipped")

            if not run_loop:
                with self._lock:
                    self._phase = "sync_done" if run_sync else "idle"
                return

            with self._lock:
                self._phase = "loop"
            while not stop_event.is_set():
                loop_result = run_gui_ops_once(
                    provider=self._config.provider,
                    symbols=self._config.symbols,
                    timeframe=self._config.timeframe,
                    lookback_hours=self._config.lookback_hours,
                    raw_dir=self._config.raw_dir,
                    curated_dir=self._config.curated_dir,
                    metrics_path=self._config.metrics_path,
                    price_csv_dir=self._config.price_csv_dir,
                    bootstrap_rows=self._config.bootstrap_rows,
                    profile_path=self._config.profile_path,
                    data_dir=self._config.data_dir,
                    feature_config=self._config.feature_config,
                    strategy_manifest=strategy_manifest,
                    data_manifest=self._config.manifest,
                    signal_log_path=self._config.signal_log_path,
                    backfill_days=self._config.backfill_days,
                    target_r_multiple=self._config.target_r_multiple,
                    ttl_bars=self._config.ttl_bars,
                    trail_atr_mult=self._config.trail_atr_mult,
                    spread_pips=self._config.spread_pips,
                    slippage_pips=self._config.slippage_pips,
                    slippage_std=self._config.slippage_std,
                    signals_csv_append=self._config.signals_csv_append,
                    signals_csv_monthly=self._config.signals_csv_monthly,
                )
                with self._lock:
                    self._last_loop = loop_result.to_dict()
                    self._loop_iterations += 1
                warnings = self._last_loop.get("signal_preview", {}).get("warnings", [])
                warning_suffix = ""
                if isinstance(warnings, list) and warnings:
                    warning_suffix = f" warnings={warnings[0]}"
                self._append_log(
                    f"loop iteration={self._loop_iterations} signals={self._last_loop.get('signal_preview', {}).get('signals', 0)}{warning_suffix}"
                )
                if stop_event.wait(self._config.interval_sec):
                    break
        except GuiDataSyncStopped:
            self._mark_sync_stopped()
            with self._lock:
                self._phase = "stopped"
            self._append_log("sync stopped by user")
        except GuiDataSyncError as exc:
            with self._lock:
                self._last_error = str(exc)
                self._phase = "error"
            self._mark_sync_error(str(exc))
            self._append_log(f"sync failed: {exc}")
        except Exception as exc:  # pragma: no cover - defensive
            with self._lock:
                self._last_error = str(exc)
                self._phase = "error"
            self._mark_sync_error(str(exc))
            self._append_log(f"loop failed: {exc}")
        finally:
            with self._lock:
                if self._phase != "error":
                    self._phase = "stopped"
                self._finished_at = _utcnow_iso()
                self._active_strategy_ids = ()
                self._active_strategy_manifest = None
                self._active_run_sync = self._selected_run_sync
                self._active_run_loop = self._selected_run_loop
            self._append_log("worker finished")


@dataclass(frozen=True)
class GuiServerConfig:
    host: str
    port: int
    refresh_sec: int
    signal_log_path: Path
    price_csv_path: Path | None
    price_column: str
    ts_column: str
    static_dir: Path
    ops_controller: GuiOpsRuntimeController | None


class GuiServer:
    def __init__(self, config: GuiServerConfig) -> None:
        self._config = config

    def serve(self) -> None:
        handler = _build_handler(self._config)
        server = ThreadingHTTPServer((self._config.host, self._config.port), handler)
        logger.info(
            "gui.server.start",
            extra={"host": self._config.host, "port": self._config.port},
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            logger.info("gui.server.stop")
        finally:
            server.server_close()


def run_gui_server(
    *,
    host: str = "127.0.0.1",
    port: int = 8787,
    refresh_sec: int = 30,
    signal_log_path: Path = DEFAULT_SIGNAL_LOG,
    price_csv_path: Path | None = None,
    price_column: str = "close",
    ts_column: str = "ts",
    static_dir: Path | None = None,
    ops_runtime: GuiOpsRuntimeConfig | None = None,
) -> None:
    resolved_static = static_dir or _default_static_dir()
    resolved_price = price_csv_path
    if resolved_price is None and DEFAULT_PRICE_PREFERRED.exists():
        resolved_price = DEFAULT_PRICE_PREFERRED
    if resolved_price is None and DEFAULT_PRICE_FALLBACK.exists():
        resolved_price = DEFAULT_PRICE_FALLBACK

    config = GuiServerConfig(
        host=host,
        port=port,
        refresh_sec=refresh_sec,
        signal_log_path=signal_log_path,
        price_csv_path=resolved_price,
        price_column=price_column,
        ts_column=ts_column,
        static_dir=resolved_static,
        ops_controller=GuiOpsRuntimeController(ops_runtime) if ops_runtime else None,
    )
    GuiServer(config).serve()


def _default_static_dir() -> Path:
    base = Path(__file__).resolve().parents[3]
    return base / DEFAULT_EXPORT_DIR


def _build_handler(config: GuiServerConfig):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path.startswith("/api/"):
                self._handle_api(parsed)
                return
            self._handle_static(parsed.path)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path.startswith("/api/"):
                self._handle_api_post(parsed)
                return
            self._json({"status": "error", "error": "not_found"}, status=404)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            logger.info("gui.http", extra={"http_message": format % args})

        def _handle_api(self, parsed) -> None:
            if parsed.path == "/api/status":
                payload = _status_payload(config)
                self._json(payload)
                return
            if parsed.path == "/api/signals":
                params = parse_qs(parsed.query)
                limit = _parse_int(params.get("limit"), default=100)
                selected_symbols: frozenset[str] | None = None
                selected_strategy_ids: frozenset[str] | None = None
                if config.ops_controller is not None:
                    snapshot = config.ops_controller.snapshot()
                    selected_symbols = _normalise_filter_symbols(
                        snapshot.get("symbols"), fallback=snapshot.get("symbol")
                    )
                    selected_strategy_ids = _normalise_filter_strategy_ids(
                        snapshot.get("selected_strategy_ids")
                    )
                payload = _signals_payload(
                    config.signal_log_path,
                    limit=limit,
                    symbols=selected_symbols,
                    strategy_ids=selected_strategy_ids,
                )
                self._json(payload)
                return
            if parsed.path == "/api/price":
                payload = _price_payload(config)
                self._json(payload)
                return
            if parsed.path == "/api/ops/status":
                payload = _ops_status_payload(config)
                self._json(payload)
                return
            self._json({"status": "error", "error": "not_found"}, status=404)

        def _handle_api_post(self, parsed) -> None:
            body = self._read_json_body()
            if body is None:
                self._json({"status": "error", "error": "invalid_json"}, status=400)
                return
            if parsed.path == "/api/ops/start":
                payload, status_code = _ops_start_payload(config, body)
                self._json(payload, status=status_code)
                return
            if parsed.path == "/api/ops/stop":
                payload = _ops_stop_payload(config)
                self._json(payload)
                return
            self._json({"status": "error", "error": "not_found"}, status=404)

        def _read_json_body(self) -> dict[str, Any] | None:
            content_length = self.headers.get("Content-Length")
            if content_length is None:
                return {}
            try:
                size = int(content_length)
            except ValueError:
                return None
            if size <= 0:
                return {}
            raw = self.rfile.read(size)
            if not raw:
                return {}
            try:
                payload = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                return None
            if not isinstance(payload, dict):
                return None
            return payload

        def _handle_static(self, path: str) -> None:
            target = path or "/"
            if target == "/":
                target = "/index.html"
            safe_path = (config.static_dir / target.lstrip("/")).resolve()
            if not str(safe_path).startswith(str(config.static_dir.resolve())):
                self._json({"status": "error", "error": "forbidden"}, status=403)
                return
            if not safe_path.exists() or safe_path.is_dir():
                self._json({"status": "error", "error": "not_found"}, status=404)
                return
            content = safe_path.read_bytes()
            mime = mimetypes.guess_type(safe_path.name)[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)

        def _json(self, payload: dict[str, Any], status: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return Handler


def _status_payload(config: GuiServerConfig) -> dict[str, Any]:
    payload = {
        "status": "ok",
        "server_time": _utcnow_iso(),
        "refresh_sec": config.refresh_sec,
        "signal_log": str(config.signal_log_path),
        "price_source": str(config.price_csv_path) if config.price_csv_path else None,
    }
    if config.ops_controller is not None:
        payload["ops"] = config.ops_controller.snapshot()
    return payload


def _signals_payload(
    path: Path,
    *,
    limit: int,
    symbols: frozenset[str] | None = None,
    strategy_ids: frozenset[str] | None = None,
) -> dict[str, Any]:
    records = _load_signal_records(path, limit=limit)
    records = [
        record
        for record in records
        if record.get("event") == "signal.generated"
        and record.get("status") == "generated"
        and record.get("symbol")
        and _is_signal_time_order_valid(record)
    ]
    if symbols:
        records = [
            record
            for record in records
            if str(record.get("symbol", "")).strip().upper() in symbols
        ]
    if strategy_ids:
        records = [
            record
            for record in records
            if str(record.get("strategy_id", "")).strip() in strategy_ids
        ]
    return {"status": "ok", "count": len(records), "signals": records}


def _allocation_decisions_payload(
    path: Path,
    *,
    limit: int,
    symbols: frozenset[str] | None = None,
    strategy_ids: frozenset[str] | None = None,
) -> dict[str, Any]:
    return summarize_allocation_surface(
        path,
        limit=limit,
        symbols=symbols,
        strategy_ids=strategy_ids,
    )


def _is_signal_time_order_valid(record: Mapping[str, Any]) -> bool:
    ts = _parse_utc_datetime(record.get("ts"))
    expire_at = _parse_utc_datetime(record.get("expire_at"))
    if ts is None or expire_at is None:
        return True
    return expire_at >= ts


def _parse_utc_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    token = value.strip()
    if not token:
        return None
    if token.endswith("Z"):
        token = token[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(token)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _price_payload(config: GuiServerConfig) -> dict[str, Any]:
    if config.price_csv_path is None:
        return {"status": "unavailable", "reason": "price_source_not_configured"}
    if not config.price_csv_path.exists():
        return {"status": "unavailable", "reason": "price_source_missing"}
    row = _read_latest_price_from_csv(
        config.price_csv_path, price_column=config.price_column, ts_column=config.ts_column
    )
    if row is None:
        return {"status": "unavailable", "reason": "price_row_missing"}
    payload = {
        "status": "ok",
        "price": row.get(config.price_column),
        "ts": row.get(config.ts_column),
        "row": row,
        "source": str(config.price_csv_path),
    }
    return payload


def _load_signal_records(path: Path, *, limit: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    effective_limit = limit if limit > 0 else 1000
    selected = _read_last_non_empty_lines(path, limit=effective_limit)
    records: list[dict[str, Any]] = []
    for line in selected:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        records.append(payload)
    records.sort(key=lambda item: item.get("ts") or "")
    return records


def _read_latest_price_from_csv(
    path: Path, *, price_column: str, ts_column: str
) -> dict[str, Any] | None:
    if not path.exists():
        return None
    header_line = _read_first_line(path)
    if header_line is None:
        return None
    last_line = _read_last_line(path)
    if last_line is None:
        return None
    headers = _parse_csv_line(header_line)
    values = _parse_csv_line(last_line)
    if not headers or not values:
        return None
    if len(values) != len(headers):
        return None
    row = dict(zip(headers, values))
    if price_column not in row:
        return None
    if ts_column not in row:
        row[ts_column] = row.get("timestamp") or row.get("time")
    return row


def _read_first_line(path: Path) -> str | None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            line = handle.readline()
            return line.strip() or None
    except OSError:
        return None


def _read_last_line(path: Path) -> str | None:
    lines = _read_last_non_empty_lines(path, limit=1)
    if not lines:
        return None
    return lines[-1]


def _read_last_non_empty_lines(path: Path, *, limit: int, chunk_size: int = 64 * 1024) -> list[str]:
    if limit <= 0 or not path.exists():
        return []
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            position = handle.tell()
            chunks: list[bytes] = []
            newline_count = 0
            while position > 0 and newline_count <= limit:
                read_size = min(chunk_size, position)
                position -= read_size
                handle.seek(position)
                data = handle.read(read_size)
                chunks.append(data)
                newline_count += data.count(b"\n")
    except OSError:
        return []

    blob = b"".join(reversed(chunks))
    lines = [line.strip() for line in blob.decode("utf-8", errors="ignore").splitlines() if line.strip()]
    if not lines:
        return []
    return lines[-limit:]


def _parse_csv_line(line: str) -> list[str]:
    return next(csv.reader([line])) if line else []


def _parse_int(values: list[str] | None, *, default: int) -> int:
    if not values:
        return default
    try:
        return int(values[0])
    except ValueError:
        return default


def _normalise_filter_symbols(
    symbols: Any,
    *,
    fallback: Any = None,
) -> frozenset[str] | None:
    values: list[str] = []
    if isinstance(symbols, (list, tuple, set, frozenset)):
        values.extend(str(item).strip().upper() for item in symbols if str(item).strip())
    elif isinstance(symbols, str) and symbols.strip():
        values.extend(token.strip().upper() for token in symbols.split(",") if token.strip())
    if not values and isinstance(fallback, str) and fallback.strip():
        values.append(fallback.strip().upper())
    if not values:
        return None
    return frozenset(values)


def _normalise_filter_strategy_ids(value: Any) -> frozenset[str] | None:
    if not isinstance(value, (list, tuple, set, frozenset)):
        return None
    values = [str(item).strip() for item in value if str(item).strip()]
    if not values:
        return None
    return frozenset(values)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _positive_int(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed <= 0:
        return default
    return parsed


def _clamp_pct(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(0, min(100, parsed))


def _estimate_eta_sec(elapsed_sec: int, progress_pct: int) -> int | None:
    if progress_pct <= 0 or progress_pct >= 100:
        return 0 if progress_pct >= 100 else None
    remaining_pct = 100 - progress_pct
    eta = int((elapsed_sec * remaining_pct) / progress_pct)
    return max(0, eta)


def _elapsed_sec(started_perf: float | None) -> int:
    if started_perf is None:
        return 0
    return int(max(0.0, time.perf_counter() - started_perf))


def _normalize_manifest_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return (Path.cwd() / path).resolve()


def _display_path(path: Path) -> str:
    resolved = _normalize_manifest_path(path)
    try:
        return str(resolved.relative_to(Path.cwd()))
    except ValueError:
        return str(resolved)


def _yaml_dump_text(payload: Mapping[str, Any]) -> str:
    dumper = getattr(yaml, "safe_dump", None)
    if dumper is not None:
        return dumper(dict(payload), allow_unicode=True, sort_keys=False)
    return "# JSON\n" + json.dumps(payload, ensure_ascii=False, indent=2)


def _discover_strategy_manifests(preferred: Path) -> list[Path]:
    preferred_path = _normalize_manifest_path(preferred)
    parent = preferred_path.parent
    manifests = []
    seen: set[Path] = set()

    if preferred_path not in seen:
        manifests.append(preferred_path)
        seen.add(preferred_path)

    if parent.exists():
        for candidate in sorted(parent.glob("strategy_manifest*.yaml")):
            resolved = _normalize_manifest_path(candidate)
            if resolved in seen:
                continue
            manifests.append(resolved)
            seen.add(resolved)
    return manifests


def _load_manifest_payloads(paths: list[Path] | tuple[Path, ...]) -> dict[Path, dict[str, Any]]:
    payloads: dict[Path, dict[str, Any]] = {}
    for path in paths:
        resolved = _normalize_manifest_path(path)
        if not resolved.exists():
            continue
        try:
            loaded = yaml.safe_load(resolved.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(loaded, dict):
            payloads[resolved] = loaded
    return payloads


def _manifest_enabled_strategy_ids(payload: Mapping[str, Any] | None) -> tuple[str, ...]:
    if payload is None:
        return ()
    strategies = payload.get("strategies")
    if not isinstance(strategies, Mapping):
        return ()
    selected: list[str] = []
    for strategy_id, entry in strategies.items():
        if not isinstance(strategy_id, str):
            continue
        if not isinstance(entry, Mapping):
            continue
        if bool(entry.get("enabled")):
            selected.append(strategy_id)
    return tuple(selected)


def _resolve_initial_selected_strategy_ids(
    *,
    selected_manifest: Path,
    manifest_payloads: Mapping[Path, Mapping[str, Any]],
    strategy_catalog: Mapping[str, Mapping[str, Any]],
) -> tuple[str, ...]:
    payload = manifest_payloads.get(selected_manifest)
    selected = _manifest_enabled_strategy_ids(payload)
    if selected:
        return selected
    if strategy_catalog:
        first_strategy = sorted(strategy_catalog.keys())[0]
        return (first_strategy,)
    return ()


def _build_strategy_catalog(
    manifest_payloads: Mapping[Path, Mapping[str, Any]]
) -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    for manifest_path, payload in manifest_payloads.items():
        strategies = payload.get("strategies")
        if not isinstance(strategies, Mapping):
            continue
        for strategy_id, entry in strategies.items():
            if not isinstance(strategy_id, str):
                continue
            if not isinstance(entry, Mapping):
                continue
            metadata = entry.get("metadata")
            strategy_name = strategy_id
            if isinstance(metadata, Mapping):
                raw_name = metadata.get("name")
                if isinstance(raw_name, str) and raw_name.strip():
                    strategy_name = raw_name.strip()
            if strategy_id not in catalog:
                catalog[strategy_id] = {
                    "name": strategy_name,
                    "entry": deepcopy(dict(entry)),
                    "source_manifest": manifest_path,
                }
    return catalog


def _strategy_ops_display(strategy_id: str) -> dict[str, str]:
    override = GUI_STRATEGY_DISPLAY_OVERRIDES.get(strategy_id)
    if override is None:
        return {"ops_state": "default", "ops_state_label": "", "ops_state_note": ""}
    return {
        "ops_state": override.get("state", "default"),
        "ops_state_label": override.get("label", ""),
        "ops_state_note": override.get("note", ""),
    }


def _materialize_runtime_manifest(
    *,
    selected_manifest: Path,
    manifest_payloads: Mapping[Path, Mapping[str, Any]],
    strategy_catalog: Mapping[str, Mapping[str, Any]],
    selected_strategy_ids: tuple[str, ...],
) -> Path:
    if not selected_strategy_ids:
        raise ValueError("at least one strategy is required")
    base_payload = manifest_payloads.get(selected_manifest)
    if base_payload is None:
        raise ValueError("selected manifest payload unavailable")
    runtime_payload = deepcopy(dict(base_payload))
    strategies = runtime_payload.get("strategies")
    if not isinstance(strategies, dict):
        strategies = {}
        runtime_payload["strategies"] = strategies

    selected_set = set(selected_strategy_ids)
    for strategy_id, entry in list(strategies.items()):
        if not isinstance(entry, dict):
            continue
        entry["enabled"] = strategy_id in selected_set

    for strategy_id in selected_strategy_ids:
        if strategy_id in strategies:
            continue
        catalog_entry = strategy_catalog.get(strategy_id)
        if not catalog_entry:
            raise ValueError(f"unknown strategy: {strategy_id}")
        source_entry = catalog_entry.get("entry")
        if not isinstance(source_entry, Mapping):
            raise ValueError(f"invalid strategy entry: {strategy_id}")
        clone = deepcopy(dict(source_entry))
        clone["enabled"] = True
        strategies[strategy_id] = clone

    _normalise_enabled_strategy_weights(strategies)

    runtime_payload["manifest_name"] = f"{runtime_payload.get('manifest_name', 'GUI Runtime')} [GUI Selected]"
    runtime_payload["revision_tag"] = "GUI-RUNTIME-SELECTED"
    runtime_payload["last_reviewed_at"] = _utcnow_iso()

    runtime_dir = Path("reports") / "gui" / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    runtime_path = runtime_dir / "strategy_manifest.selected.yaml"
    runtime_path.write_text(
        _yaml_dump_text(runtime_payload),
        encoding="utf-8",
    )
    return runtime_path.resolve()


def _normalise_enabled_strategy_weights(strategies: Mapping[str, Any]) -> None:
    enabled_entries: list[dict[str, Any]] = []
    total_weight = 0.0
    for entry in strategies.values():
        if not isinstance(entry, dict):
            continue
        if not bool(entry.get("enabled")):
            continue
        try:
            weight = float(entry.get("weight", 0.0))
        except (TypeError, ValueError):
            weight = 0.0
        if weight < 0.0:
            weight = 0.0
        entry["weight"] = weight
        enabled_entries.append(entry)
        total_weight += weight

    if not enabled_entries:
        return
    if total_weight <= 1.0 + 1e-9:
        return

    scale = 1.0 / total_weight
    for entry in enabled_entries:
        weight = float(entry.get("weight", 0.0))
        entry["weight"] = max(0.0, weight * scale)


def resolve_sync_source_dir(symbol: str, source_dir: Path | None = None) -> Path:
    if source_dir is not None:
        return source_dir
    symbol_key = symbol.strip().lower()
    curated_root = Path("data/research/curated")
    candidates = [
        curated_root / f"{symbol_key}_m5_clean",
        curated_root / f"{symbol_key}_m5",
        curated_root / symbol_key,
    ]
    existing = [candidate for candidate in candidates if candidate.exists()]
    if not existing:
        return candidates[0]

    best = existing[0]
    best_ts = _latest_bar_timestamp_in_dir(best)
    for candidate in existing[1:]:
        candidate_ts = _latest_bar_timestamp_in_dir(candidate)
        if best_ts is None and candidate_ts is not None:
            best = candidate
            best_ts = candidate_ts
            continue
        if candidate_ts is not None and best_ts is not None and candidate_ts > best_ts:
            best = candidate
            best_ts = candidate_ts
    return best


def _latest_bar_timestamp_in_dir(path: Path) -> datetime | None:
    if not path.exists() or not path.is_dir():
        return None
    latest: datetime | None = None
    for parquet_path in sorted(path.glob("*.parquet")):
        ts = _latest_bar_timestamp_in_parquet(parquet_path)
        if ts is None:
            continue
        if latest is None or ts > latest:
            latest = ts
    return latest


def _latest_bar_timestamp_in_parquet(path: Path) -> datetime | None:
    for col in ("timestamp", "ts"):
        try:
            frame = pd.read_parquet(path, columns=[col])
        except Exception:
            continue
        if frame.empty:
            continue
        series = pd.to_datetime(frame[col], utc=True, errors="coerce").dropna()
        if series.empty:
            continue
        return series.max().to_pydatetime()
    return None


def _ops_status_payload(config: GuiServerConfig) -> dict[str, Any]:
    if config.ops_controller is None:
        return {"status": "disabled", "reason": "ops_runtime_not_configured"}
    payload = config.ops_controller.snapshot()
    selected_symbols = _normalise_filter_symbols(
        payload.get("symbols"), fallback=payload.get("symbol")
    )
    selected_strategy_ids = _normalise_filter_strategy_ids(payload.get("selected_strategy_ids"))
    payload["recent_allocation_decisions"] = _allocation_decisions_payload(
        config.signal_log_path,
        limit=50,
        symbols=selected_symbols,
        strategy_ids=selected_strategy_ids,
    )
    payload["recent_candidates"] = summarize_candidate_surface(
        config.signal_log_path,
        limit=50,
        symbols=selected_symbols,
        strategy_ids=selected_strategy_ids,
    )
    payload["shadow_next_stage_execution_state"] = summarize_shadow_next_stage_execution()
    payload["shadow_feedback_validation_result"] = summarize_shadow_feedback_validation_result()
    payload["shadow_feedback_rollout_alignment"] = summarize_shadow_feedback_rollout_alignment(
        payload.get("shadow_feedback_validation_result"),
        payload.get("shadow_next_stage_execution_state"),
    )
    return payload


def _ops_start_payload(
    config: GuiServerConfig, payload: Mapping[str, Any] | None
) -> tuple[dict[str, Any], int]:
    if config.ops_controller is None:
        return {"status": "disabled", "reason": "ops_runtime_not_configured"}, 503
    response = config.ops_controller.start(overrides=payload)
    if response.get("accepted"):
        return response, 200
    if response.get("reason") == "already_running":
        return response, 409
    return response, 400


def _ops_stop_payload(config: GuiServerConfig) -> dict[str, Any]:
    if config.ops_controller is None:
        return {"status": "disabled", "reason": "ops_runtime_not_configured"}
    return config.ops_controller.stop()
