"""Local web GUI server for signal monitoring."""

from __future__ import annotations

import csv
import json
import logging
import mimetypes
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)

DEFAULT_SIGNAL_LOG = Path("logs") / "events" / "signal.generated.jsonl"
DEFAULT_EXPORT_DIR = Path("ui") / "web"
DEFAULT_PRICE_PREFERRED = Path("reports") / "price" / "usdjpy_m5.csv"
DEFAULT_PRICE_FALLBACK = Path("usdjpy_5m_2018-2024_utc.csv")


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
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event: threading.Event | None = None
        self._phase = "idle"
        self._started_at: str | None = None
        self._finished_at: str | None = None
        self._last_error: str | None = None
        self._loop_iterations = 0
        self._last_sync: dict[str, Any] | None = None
        self._last_loop: dict[str, Any] | None = None
        self._recent_logs: list[str] = []

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self._is_running_locked():
                snapshot = self._snapshot_locked()
                snapshot["accepted"] = False
                snapshot["reason"] = "already_running"
                return snapshot
            self._stop_event = threading.Event()
            self._thread = threading.Thread(target=self._run_worker, daemon=True)
            self._phase = "starting"
            self._started_at = _utcnow_iso()
            self._finished_at = None
            self._last_error = None
            self._loop_iterations = 0
            self._last_sync = None
            self._last_loop = None
            self._recent_logs = []
            self._thread.start()
            snapshot = self._snapshot_locked()
            snapshot["accepted"] = True
            return snapshot

    def stop(self) -> dict[str, Any]:
        with self._lock:
            if self._stop_event is not None:
                self._stop_event.set()
                self._phase = "stopping"
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
        return {
            "status": "ok",
            "running": running,
            "phase": self._phase,
            "started_at": self._started_at,
            "finished_at": self._finished_at,
            "last_error": self._last_error,
            "loop_iterations": self._loop_iterations,
            "last_sync": self._last_sync,
            "last_loop": self._last_loop,
            "symbol": self._config.symbol,
            "provider": self._config.provider,
            "interval_sec": self._config.interval_sec,
            "recent_logs": self._recent_logs[-20:],
        }

    def _append_log(self, message: str) -> None:
        with self._lock:
            self._recent_logs.append(f"{_utcnow_iso()} {message}")
            if len(self._recent_logs) > 200:
                self._recent_logs = self._recent_logs[-200:]

    def _run_worker(self) -> None:
        from src.interfaces.cli.gui_sync import GuiDataSyncError, run_gui_data_sync
        from tools.gui_ops_loop import run_gui_ops_once

        self._append_log("sync started")
        stop_event = self._stop_event or threading.Event()
        try:
            with self._lock:
                self._phase = "sync"
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
            )
            with self._lock:
                self._last_sync = sync_result.to_dict()
                self._phase = "loop"
            self._append_log("sync finished")

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
                    strategy_manifest=self._config.strategy_manifest,
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
                self._append_log(
                    f"loop iteration={self._loop_iterations} signals={self._last_loop.get('signal_preview', {}).get('signals', 0)}"
                )
                if stop_event.wait(self._config.interval_sec):
                    break
        except GuiDataSyncError as exc:
            with self._lock:
                self._last_error = str(exc)
                self._phase = "error"
            self._append_log(f"sync failed: {exc}")
        except Exception as exc:  # pragma: no cover - defensive
            with self._lock:
                self._last_error = str(exc)
                self._phase = "error"
            self._append_log(f"loop failed: {exc}")
        finally:
            with self._lock:
                if self._phase != "error":
                    self._phase = "stopped"
                self._finished_at = _utcnow_iso()
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
                payload = _signals_payload(config.signal_log_path, limit=limit)
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
            if parsed.path == "/api/ops/start":
                payload, status_code = _ops_start_payload(config)
                self._json(payload, status=status_code)
                return
            if parsed.path == "/api/ops/stop":
                payload = _ops_stop_payload(config)
                self._json(payload)
                return
            self._json({"status": "error", "error": "not_found"}, status=404)

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


def _signals_payload(path: Path, *, limit: int) -> dict[str, Any]:
    records = _load_signal_records(path, limit=limit)
    return {"status": "ok", "count": len(records), "signals": records}


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
    lines = path.read_text(encoding="utf-8").splitlines()
    lines = [line for line in lines if line.strip()]
    selected = lines[-limit:] if limit > 0 else lines
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
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        if line.strip():
            return line.strip()
    return None


def _parse_csv_line(line: str) -> list[str]:
    return next(csv.reader([line])) if line else []


def _parse_int(values: list[str] | None, *, default: int) -> int:
    if not values:
        return default
    try:
        return int(values[0])
    except ValueError:
        return default


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
    return next((candidate for candidate in candidates if candidate.exists()), candidates[0])


def _ops_status_payload(config: GuiServerConfig) -> dict[str, Any]:
    if config.ops_controller is None:
        return {"status": "disabled", "reason": "ops_runtime_not_configured"}
    return config.ops_controller.snapshot()


def _ops_start_payload(config: GuiServerConfig) -> tuple[dict[str, Any], int]:
    if config.ops_controller is None:
        return {"status": "disabled", "reason": "ops_runtime_not_configured"}, 503
    payload = config.ops_controller.start()
    status_code = 200 if payload.get("accepted") else 409
    return payload, status_code


def _ops_stop_payload(config: GuiServerConfig) -> dict[str, Any]:
    if config.ops_controller is None:
        return {"status": "disabled", "reason": "ops_runtime_not_configured"}
    return config.ops_controller.stop()
