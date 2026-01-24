"""Manual CSV reconciliation helpers for fallback ingestion."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.utils.hashing import sha256_path
DEFAULT_MANUAL_CSV_AUDIT = Path("logs/audit/manual_csv.jsonl")
DEFAULT_MANUAL_CSV_METRICS = Path("metrics/data_ingestion_manual.jsonl")
DEFAULT_MANUAL_CSV_EVIDENCE = Path("evidence/data/manual_csv")

__all__ = [
    "ManualCsvError",
    "ManualCsvReconciler",
    "ManualCsvValidationResult",
    "DEFAULT_MANUAL_CSV_AUDIT",
    "DEFAULT_MANUAL_CSV_METRICS",
    "DEFAULT_MANUAL_CSV_EVIDENCE",
    "parse_manual_csv_meta",
]


class ManualCsvError(ValueError):
    """Raised when manual CSV reconciliation fails."""

    def __init__(self, message: str, *, code: str = "manual_csv_invalid") -> None:
        super().__init__(message)
        self.code = code


@dataclass(slots=True)
class ManualCsvValidationResult:
    status: str
    provider: str
    symbol: str
    timeframe: str
    date: str
    op_path: Path
    review_path: Path
    op_hash: str
    review_hash: str
    rows: int
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "provider": self.provider,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "date": self.date,
            "op_path": str(self.op_path),
            "review_path": str(self.review_path),
            "op_hash": self.op_hash,
            "review_hash": self.review_hash,
            "rows": self.rows,
            "errors": list(self.errors),
        }


class ManualCsvReconciler:
    """Validate manual CSV pairs and emit audit evidence."""

    def __init__(
        self,
        *,
        audit_path: Path = DEFAULT_MANUAL_CSV_AUDIT,
        metrics_path: Path = DEFAULT_MANUAL_CSV_METRICS,
        evidence_dir: Path = DEFAULT_MANUAL_CSV_EVIDENCE,
        runbook_id: str = "RUN-DATA-06",
    ) -> None:
        self._audit_path = audit_path
        self._metrics_path = metrics_path
        self._evidence_dir = evidence_dir
        self._runbook_id = runbook_id

    def validate_path(self, path: Path) -> ManualCsvValidationResult:
        op_path, review_path = _resolve_pair(path)
        provider, symbol, timeframe, date = parse_manual_csv_meta(op_path)
        errors: list[str] = []

        op_frame = _load_frame(op_path, label="op")
        review_frame = _load_frame(review_path, label="review")
        _validate_required(op_frame, "op")
        _validate_required(review_frame, "review")

        if list(op_frame.columns) != list(review_frame.columns) or len(op_frame) != len(
            review_frame
        ):
            raise ManualCsvError("op/review shape mismatch", code="shape_mismatch")

        for frame, label, path in (
            (op_frame, "op", op_path),
            (review_frame, "review", review_path),
        ):
            _validate_frame(frame, label=label, path=path)

        op_hash = sha256_path(op_path)
        review_hash = sha256_path(review_path)
        if op_hash != review_hash:
            raise ManualCsvError("op/review hash mismatch", code="hash_mismatch")

        status = "ok" if not errors else "fail"
        return ManualCsvValidationResult(
            status=status,
            provider=provider,
            symbol=symbol,
            timeframe=timeframe,
            date=date,
            op_path=op_path,
            review_path=review_path,
            op_hash=op_hash,
            review_hash=review_hash,
            rows=len(op_frame),
            errors=errors,
        )

    def approve(
        self,
        result: ManualCsvValidationResult,
        *,
        approver: str,
        attachments: list[str] | None = None,
    ) -> Mapping[str, object]:
        evidence_path = self._write_evidence(result, approver=approver, attachments=attachments)
        payload = {
            "ts": _utcnow_iso(),
            "event": "audit.manual_csv",
            "path": str(result.op_path),
            "hash_primary": result.op_hash,
            "hash_review": result.review_hash,
            "approver": approver,
            "symbol": result.symbol,
            "provider": result.provider,
            "timeframe": result.timeframe,
            "rows": result.rows,
            "runbook_id": self._runbook_id,
            "evidence_path": str(evidence_path),
        }
        _append_jsonl(self._audit_path, payload)
        _append_jsonl(
            self._metrics_path,
            {
                "ts": payload["ts"],
                "symbol": result.symbol,
                "provider": result.provider,
                "rows": result.rows,
                "hash_primary": result.op_hash,
                "hash_review": result.review_hash,
                "approver": approver,
            },
        )
        return payload

    def _write_evidence(
        self,
        result: ManualCsvValidationResult,
        *,
        approver: str,
        attachments: list[str] | None = None,
    ) -> Path:
        date_key = result.date.replace("-", "")
        out_dir = self._evidence_dir / date_key
        out_dir.mkdir(parents=True, exist_ok=True)
        evidence_path = out_dir / f"{result.symbol}.md"
        lines = [
            f"# Manual CSV Evidence {result.symbol} {result.date}",
            "",
            f"- provider: {result.provider}",
            f"- timeframe: {result.timeframe}",
            f"- op_hash: {result.op_hash}",
            f"- review_hash: {result.review_hash}",
            f"- approver: {approver}",
            f"- runbook_id: {self._runbook_id}",
            "",
        ]
        if attachments:
            lines.append("## Attachments")
            lines.extend(f"- {item}" for item in attachments)
        evidence_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return evidence_path


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _append_jsonl(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _resolve_pair(path: Path) -> tuple[Path, Path]:
    if path.name.endswith("_op.csv"):
        review_path = path.with_name(path.name.replace("_op.csv", "_review.csv"))
        op_path = path
    elif path.name.endswith("_review.csv"):
        op_path = path.with_name(path.name.replace("_review.csv", "_op.csv"))
        review_path = path
    else:
        raise ManualCsvError(
            f"Expected _op/_review CSV suffix, got: {path.name}",
            code="invalid_pair",
        )
    if not review_path.exists():
        raise ManualCsvError(f"Missing twin CSV: {review_path}", code="missing_review")
    return op_path, review_path


def _load_frame(path: Path, *, label: str) -> pd.DataFrame:
    if path.suffix.lower() != ".csv":
        raise ManualCsvError(f"Expected CSV file, got: {path}", code="invalid_extension")
    frame = pd.read_csv(path)
    required_cols = {"open", "high", "low", "close", "volume", "spread", "timestamp_jst"}
    ts_cols = {"ts", "timestamp"}
    missing = required_cols - set(frame.columns)
    if missing:
        raise ManualCsvError(f"Missing required columns {missing} in {label} file", code="missing")
    if not (ts_cols & set(frame.columns)):
        raise ManualCsvError(f"Missing timestamp column in {label} file", code="missing_ts")
    return frame


def _validate_required(frame: pd.DataFrame, label: str) -> None:
    required_cols = {"open", "high", "low", "close", "volume", "spread", "timestamp_jst"}
    ts_cols = {"ts", "timestamp"}
    missing = required_cols - set(frame.columns)
    if missing:
        raise ManualCsvError(f"Missing required columns {missing} in {label} file", code="missing")
    if not (ts_cols & set(frame.columns)):
        raise ManualCsvError(f"Missing timestamp column in {label} file", code="missing_ts")


def _detect_non_utc(value: object) -> bool:
    if value is None:
        return False
    text = str(value)
    if text.endswith("Z"):
        return False
    match = re.search(r"([+-])(\d{2}):(\d{2})$", text)
    if not match:
        return False
    sign, hours, minutes = match.groups()
    return not (sign in {"+", "-"} and hours == "00" and minutes == "00")


def _validate_frame(frame: pd.DataFrame, *, label: str, path: Path) -> None:
    if frame.isnull().any().any():
        raise ManualCsvError(f"Missing values detected in {label} file: {path}")
    low_ok = (frame["low"] <= frame["open"]) & (frame["low"] <= frame["close"])
    high_ok = (frame["high"] >= frame["open"]) & (frame["high"] >= frame["close"])
    if not bool(low_ok.all() and high_ok.all()):
        raise ManualCsvError(f"Price envelope violation in {label} file: {path}")
    if (frame["volume"] < 0).any():
        raise ManualCsvError(f"Negative volume detected in {label} file: {path}")
    if (frame["spread"] < 0).any():
        raise ManualCsvError(f"Negative spread detected in {label} file: {path}")
    session_col = frame.get("session_tag")
    if session_col is not None:
        allowed_sessions = {"asia", "london", "newyork", "overlap", "holiday"}
        if not set(session_col.dropna().unique()).issubset(allowed_sessions):
            raise ManualCsvError(f"Invalid session_tag in {label} file: {path}")
    ts_col = "ts" if "ts" in frame.columns else "timestamp"
    if frame[ts_col].apply(_detect_non_utc).any():
        raise ManualCsvError("Timestamp timezone mismatch (expected UTC)", code="clock_mismatch")
    try:
        timestamps = pd.to_datetime(frame[ts_col], utc=True)
    except Exception as exc:  # pragma: no cover - defensive
        raise ManualCsvError(f"Timestamp parsing failed for {label} file: {exc}") from exc
    if timestamps.duplicated().any():
        raise ManualCsvError(f"Duplicate timestamps detected in {label} file: {path}")
    expected_step = _infer_step_seconds(path.stem)
    if expected_step and len(timestamps) >= 2:
        diffs = (timestamps.sort_values().diff().dropna().dt.total_seconds()).unique()
        if any(d != expected_step for d in diffs):
            raise ManualCsvError(
                f"Timestamp gap detected in {label} file: {path} (expected {expected_step}s)"
            )
    _assert_bar_alignment(timestamps, expected_step, label=label, path=path)
    ts_jst = pd.to_datetime(frame["timestamp_jst"], utc=True)
    if not ((ts_jst - timestamps).dt.total_seconds() == 9 * 3600).all():
        raise ManualCsvError(f"UTC/JST mismatch in {label} file: {path}")


def _infer_step_seconds(stem: str) -> int | None:
    for token in stem.lower().split("_"):
        match = re.fullmatch(r"(\d+)([mh])", token)
        if not match:
            continue
        value, unit = match.groups()
        try:
            magnitude = int(value)
        except ValueError:
            continue
        if unit == "m":
            return magnitude * 60
        if unit == "h":
            return magnitude * 3600
    return None


def _assert_bar_alignment(
    timestamps: pd.Series, step_seconds: int | None, *, label: str, path: Path
) -> None:
    if not step_seconds:
        return
    expected_minutes = step_seconds // 60
    for ts in timestamps:
        if ts.second != 0 or ts.microsecond != 0:
            raise ManualCsvError(f"Timestamp boundary mismatch in {label} file: {path}")
        if expected_minutes >= 60:
            if ts.minute != 0:
                raise ManualCsvError(f"Timestamp boundary mismatch in {label} file: {path}")
        else:
            if ts.minute % expected_minutes != 0:
                raise ManualCsvError(f"Timestamp boundary mismatch in {label} file: {path}")


def parse_manual_csv_meta(path: Path) -> tuple[str, str, str, str]:
    provider = "unknown"
    symbol = "unknown"
    timeframe = "unknown"
    date = "unknown"
    tokens = path.stem.split("_")
    if len(tokens) >= 6 and tokens[0] == "fallback":
        provider = tokens[1]
        symbol = tokens[2].upper()
        timeframe = tokens[3]
        date = tokens[4]
    else:
        try:
            date = path.parent.name
            symbol = path.parent.parent.name.upper()
            provider = path.parent.parent.parent.name
        except Exception:
            pass
    return provider, symbol, timeframe, date
