"""Pre-trade compliance checks and reporting."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
import os
from pathlib import Path
from time import perf_counter
from typing import Any

try:  # pragma: no cover - dependency guard mirrors broker rules loader
    import yaml
except ModuleNotFoundError:  # pragma: no cover - environments without PyYAML
    yaml = None  # type: ignore[assignment]

try:  # pragma: no cover - optional schema validation
    import jsonschema
except ModuleNotFoundError:  # pragma: no cover - environments without jsonschema
    jsonschema = None  # type: ignore[assignment]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RULES_DIR = Path("config/compliance")
_SCHEMA_PATH = Path("docs/schemas/compliance_pretrade_rules.schema.json")

_DANGEROUS_KEYS = (
    "max_leverage",
    "blocked_pairs",
    "blocked_time_windows",
    "override_roles",
)


class PreTradeComplianceError(RuntimeError):
    """Base exception for pre-trade compliance failures."""


class PreTradeRuleNotFound(PreTradeComplianceError):
    """Raised when no rules file can be located."""


class PreTradeRuleValidationError(PreTradeComplianceError):
    """Raised when rules validation fails."""


class PreTradeInputError(PreTradeComplianceError):
    """Raised when a request is missing required inputs."""


class ReduceOnlyNotAvailable(PreTradeComplianceError):
    """Raised when reduce-only suggestion cannot be computed."""


class ComplianceSummaryError(PreTradeComplianceError):
    """Raised when summary formatting fails."""


class PreTradeAuditError(PreTradeComplianceError):
    """Raised when audit logging fails."""


class PreTradeOverrideDenied(PreTradeComplianceError):
    """Raised when an override attempt lacks required roles."""


@dataclass(frozen=True)
class BlockedTimeWindow:
    weekday: str
    start: str
    end: str
    reason: str | None = None

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> BlockedTimeWindow:
        try:
            weekday = str(payload["weekday"]).lower()
            start = str(payload["start"])
            end = str(payload["end"])
        except KeyError as exc:  # pragma: no cover - schema should catch
            raise PreTradeRuleValidationError("Blocked time window missing fields") from exc
        reason = payload.get("reason")
        return cls(weekday=weekday, start=start, end=end, reason=str(reason) if reason else None)


@dataclass(frozen=True)
class SymbolPositionLimit:
    max_lots: float
    max_side: str

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> SymbolPositionLimit:
        try:
            max_lots = float(payload["max_lots"])
            max_side = str(payload["max_side"])
        except KeyError as exc:  # pragma: no cover - schema should catch
            raise PreTradeRuleValidationError("Symbol limit missing required fields") from exc
        return cls(max_lots=max_lots, max_side=max_side)


@dataclass(frozen=True)
class PositionLimits:
    total_open_positions: int | None
    symbol_limits: Mapping[str, SymbolPositionLimit]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> PositionLimits:
        total_open = payload.get("total_open_positions")
        total_open_positions = int(total_open) if total_open is not None else None
        symbol_payload = payload.get("symbol", {})
        if not isinstance(symbol_payload, Mapping):
            raise PreTradeRuleValidationError("position_limits.symbol must be a mapping")
        symbol_limits = {
            str(symbol): SymbolPositionLimit.from_mapping(rule)
            for symbol, rule in symbol_payload.items()
            if isinstance(rule, Mapping)
        }
        return cls(total_open_positions=total_open_positions, symbol_limits=symbol_limits)


@dataclass(frozen=True)
class PreTradeRuleSet:
    schema_version: str
    max_leverage: float | None
    fifo_required: bool
    hedge_allowed: bool
    position_limits: PositionLimits
    blocked_pairs: tuple[str, ...]
    blocked_time_windows: tuple[BlockedTimeWindow, ...]
    override_roles: tuple[str, ...]
    runbook_map: Mapping[str, str]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> PreTradeRuleSet:
        try:
            schema_version = str(payload["schema_version"])
        except KeyError as exc:  # pragma: no cover - schema should catch
            raise PreTradeRuleValidationError("schema_version is required") from exc
        max_leverage = payload.get("max_leverage")
        fifo_required = bool(payload.get("fifo_required", False))
        hedge_allowed = bool(payload.get("hedge_allowed", True))
        position_limits = PositionLimits.from_mapping(payload.get("position_limits", {}))
        blocked_pairs = tuple(str(pair) for pair in payload.get("blocked_pairs", ()))
        blocked_time_windows = tuple(
            BlockedTimeWindow.from_mapping(window)
            for window in payload.get("blocked_time_windows", ())
        )
        override_roles = tuple(str(role) for role in payload.get("override_roles", ()))
        runbook_map_raw = payload.get("runbook_map", {})
        if not isinstance(runbook_map_raw, Mapping):
            raise PreTradeRuleValidationError("runbook_map must be a mapping")
        runbook_map = {str(key): str(value) for key, value in runbook_map_raw.items()}
        return cls(
            schema_version=schema_version,
            max_leverage=float(max_leverage) if max_leverage is not None else None,
            fifo_required=fifo_required,
            hedge_allowed=hedge_allowed,
            position_limits=position_limits,
            blocked_pairs=blocked_pairs,
            blocked_time_windows=blocked_time_windows,
            override_roles=override_roles,
            runbook_map=runbook_map,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "max_leverage": self.max_leverage,
            "fifo_required": self.fifo_required,
            "hedge_allowed": self.hedge_allowed,
            "position_limits": {
                "total_open_positions": self.position_limits.total_open_positions,
                "symbol": {
                    symbol: {"max_lots": limit.max_lots, "max_side": limit.max_side}
                    for symbol, limit in self.position_limits.symbol_limits.items()
                },
            },
            "blocked_pairs": list(self.blocked_pairs),
            "blocked_time_windows": [
                {
                    "weekday": window.weekday,
                    "start": window.start,
                    "end": window.end,
                    "reason": window.reason,
                }
                for window in self.blocked_time_windows
            ],
            "override_roles": list(self.override_roles),
            "runbook_map": dict(self.runbook_map),
            "dangerous_keys": list(_DANGEROUS_KEYS),
        }


@dataclass(frozen=True)
class PreTradeCheckRequest:
    ticket_id: str | None
    symbol: str
    side: str
    lot: float | None
    leverage: float | None
    fifo_compliant: bool | None
    hedge_detected: bool | None
    total_open_positions: int | None
    symbol_open_lots: float | None
    symbol_side: str | None
    board_mode: str
    mode: str
    timestamp: datetime
    override_user: str | None = None
    override_roles: tuple[str, ...] = field(default_factory=tuple)
    override_reason: str | None = None
    reduce_only_available: bool | None = None


@dataclass(frozen=True)
class PreTradeViolation:
    rule_id: str
    code: str
    severity: str
    value: float | str | None
    threshold: float | int | str | None
    message: str
    runbook: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "rule_id": self.rule_id,
            "code": self.code,
            "severity": self.severity,
            "value": self.value,
            "threshold": self.threshold,
            "message": self.message,
        }
        if self.runbook:
            payload["runbook"] = self.runbook
        return payload


@dataclass(frozen=True)
class PreTradeCheckResult:
    ticket_id: str | None
    status: str
    violations: tuple[PreTradeViolation, ...]
    override: bool
    override_user: str | None
    override_reason: str | None
    board_mode: str
    mode: str
    checked_at: datetime
    check_latency_ms: float
    reduce_only_suggestion: Mapping[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "ticket_id": self.ticket_id,
            "status": self.status,
            "violations": [violation.to_dict() for violation in self.violations],
            "override": self.override,
            "override_user": self.override_user,
            "override_reason": self.override_reason,
            "board_mode": self.board_mode,
            "mode": self.mode,
            "checked_at": self.checked_at.isoformat().replace("+00:00", "Z"),
            "check_latency_ms": round(self.check_latency_ms, 2),
            "reduce_only_suggestion": self.reduce_only_suggestion,
        }


@dataclass(frozen=True)
class ComplianceSummary:
    text: str
    payload: Mapping[str, object]

    def to_dict(self) -> dict[str, object]:
        return {"text": self.text, "payload": dict(self.payload)}


class PreTradeComplianceService:
    def __init__(
        self,
        *,
        rules_path: Path | None = None,
        metrics_path: Path = Path("metrics/compliance_pretrade.jsonl"),
        audit_dir: Path = Path("logs/audit"),
        feature_flags_path: Path = Path("config/feature_flags.yaml"),
    ) -> None:
        self._rules_path = rules_path
        self._metrics_path = metrics_path
        self._audit_dir = audit_dir
        self._feature_flags_path = feature_flags_path

    def load_rules(self, profile: str) -> PreTradeRuleSet:
        path = self._resolve_rules_path(profile)
        if not path.exists():
            raise PreTradeRuleNotFound(f"Pre-trade rules not found: {path}")
        payload = _load_yaml(path)
        _validate_schema_if_available(payload, schema_path=_REPO_ROOT / _SCHEMA_PATH)
        if not isinstance(payload, Mapping):
            raise PreTradeRuleValidationError("Pre-trade rules must be a mapping")
        return PreTradeRuleSet.from_mapping(payload)

    def evaluate(
        self,
        request: PreTradeCheckRequest,
        rules: PreTradeRuleSet,
        *,
        strict: bool = True,
    ) -> PreTradeCheckResult:
        start = perf_counter()
        violations: list[PreTradeViolation] = []
        missing_inputs: list[str] = []

        timestamp = _normalize_timestamp(request.timestamp)

        if rules.max_leverage is not None:
            if request.leverage is None:
                missing_inputs.append("leverage")
            elif request.leverage > rules.max_leverage:
                violations.append(
                    _violation(
                        "max_leverage",
                        "leverage_exceeded",
                        "warn",
                        request.leverage,
                        rules.max_leverage,
                        "Leverage exceeds configured maximum.",
                        rules,
                    )
                )

        if rules.fifo_required:
            if request.fifo_compliant is None:
                missing_inputs.append("fifo_compliant")
            elif request.fifo_compliant is False:
                violations.append(
                    _violation(
                        "fifo_required",
                        "fifo_violation",
                        "block",
                        request.fifo_compliant,
                        True,
                        "FIFO requirement not satisfied.",
                        rules,
                    )
                )

        if not rules.hedge_allowed:
            if request.hedge_detected is None:
                missing_inputs.append("hedge_detected")
            elif request.hedge_detected:
                violations.append(
                    _violation(
                        "hedge_allowed",
                        "hedge_blocked",
                        "block",
                        request.hedge_detected,
                        False,
                        "Hedging is not allowed for this profile.",
                        rules,
                    )
                )

        total_limit = rules.position_limits.total_open_positions
        if total_limit is not None:
            if request.total_open_positions is None:
                missing_inputs.append("total_open_positions")
            elif request.total_open_positions > total_limit:
                violations.append(
                    _violation(
                        "position_limits",
                        "total_positions_exceeded",
                        "block",
                        request.total_open_positions,
                        total_limit,
                        "Total open positions exceed the configured limit.",
                        rules,
                    )
                )

        symbol_limit = rules.position_limits.symbol_limits.get(request.symbol)
        if symbol_limit is not None:
            if request.symbol_open_lots is None:
                missing_inputs.append("symbol_open_lots")
            elif request.symbol_open_lots > symbol_limit.max_lots:
                violations.append(
                    _violation(
                        "position_limits",
                        "symbol_lot_exceeded",
                        "block",
                        request.symbol_open_lots,
                        symbol_limit.max_lots,
                        "Symbol lot size exceeds configured limit.",
                        rules,
                    )
                )
            if request.symbol_side is None:
                missing_inputs.append("symbol_side")
            elif not _side_allowed(request.symbol_side, symbol_limit.max_side):
                violations.append(
                    _violation(
                        "position_limits",
                        "symbol_side_blocked",
                        "block",
                        request.symbol_side,
                        symbol_limit.max_side,
                        "Symbol side is not allowed.",
                        rules,
                    )
                )

        if request.symbol in rules.blocked_pairs:
            violations.append(
                _violation(
                    "blocked_pairs",
                    "pair_blocked",
                    "block",
                    request.symbol,
                    ",".join(rules.blocked_pairs),
                    "Symbol is blocked by compliance rules.",
                    rules,
                )
            )

        if _blocked_by_time_window(timestamp, rules.blocked_time_windows):
            violations.append(
                _violation(
                    "blocked_time_windows",
                    "time_window_blocked",
                    "block",
                    timestamp.isoformat(),
                    "blocked_window",
                    "Trade attempted during a blocked window.",
                    rules,
                )
            )

        if missing_inputs and strict:
            raise PreTradeInputError(
                f"Missing inputs for pretrade check: {', '.join(sorted(missing_inputs))}"
            )

        status = _status_from_violations(violations)
        if request.board_mode == "guarded" and status == "warn":
            status = "blocked"

        override_used = False
        if request.override_user and violations:
            if not _override_allowed(request, rules):
                raise PreTradeOverrideDenied("Override role not permitted for this user.")
            override_used = True
            status = "override"

        reduce_only_suggestion = None
        if status == "blocked" and self._reduce_only_enabled():
            if request.reduce_only_available is False:
                raise ReduceOnlyNotAvailable("Reduce-only suggestion not available.")
            reduce_only_suggestion = {
                "recommended": True,
                "reason": "pretrade_violation",
                "symbol": request.symbol,
                "side": request.side,
            }

        latency_ms = (perf_counter() - start) * 1000.0
        return PreTradeCheckResult(
            ticket_id=request.ticket_id,
            status=status,
            violations=tuple(violations),
            override=override_used,
            override_user=request.override_user,
            override_reason=request.override_reason,
            board_mode=request.board_mode,
            mode=request.mode,
            checked_at=datetime.now(timezone.utc),
            check_latency_ms=latency_ms,
            reduce_only_suggestion=reduce_only_suggestion,
        )

    def summarize(self, result: PreTradeCheckResult, *, locale: str = "ja") -> ComplianceSummary:
        try:
            lines = [
                f"Pre-trade compliance: {result.status}",
                f"Ticket: {result.ticket_id or 'n/a'}",
                f"Mode: {result.mode} / Board: {result.board_mode}",
            ]
            if result.violations:
                lines.append("Violations:")
                for violation in result.violations:
                    lines.append(
                        f"- [{violation.severity}] {violation.code} ({violation.message})"
                    )
            else:
                lines.append("Violations: none")
            if result.override:
                lines.append(f"Override by {result.override_user or 'unknown'}")
            if locale != "ja":
                lines.append(f"Locale: {locale}")
        except Exception as exc:
            raise ComplianceSummaryError(str(exc)) from exc
        return ComplianceSummary(text="\n".join(lines), payload=result.to_dict())

    def audit(self, result: PreTradeCheckResult, *, actor: str | None = None) -> Path:
        self._audit_dir.mkdir(parents=True, exist_ok=True)
        audit_path = self._audit_dir / f"pretrade_{date.today().isoformat()}.jsonl"
        payload = {
            "ts": result.checked_at.isoformat().replace("+00:00", "Z"),
            "event": "audit.pretrade_check",
            "schema_version": "audit.pretrade.v1",
            "ticket_id": result.ticket_id,
            "status": result.status,
            "violations": [
                {
                    "rule_id": violation.rule_id,
                    "code": violation.code,
                    "severity": violation.severity,
                    "value": violation.value,
                    "threshold": violation.threshold,
                }
                for violation in result.violations
            ],
            "override_user": result.override_user,
            "override_reason": result.override_reason,
            "actor": actor,
        }
        try:
            with audit_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False))
                handle.write("\n")
                if result.override:
                    override_payload = {
                        "ts": payload["ts"],
                        "event": "audit.pretrade_override",
                        "schema_version": "audit.pretrade.v1",
                        "ticket_id": result.ticket_id,
                        "status": result.status,
                        "override_user": result.override_user,
                        "override_reason": result.override_reason,
                        "actor": actor,
                    }
                    handle.write(json.dumps(override_payload, ensure_ascii=False))
                    handle.write("\n")
        except OSError as exc:
            raise PreTradeAuditError(str(exc)) from exc
        return audit_path

    def record_metrics(self, result: PreTradeCheckResult) -> Path:
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "compliance_pretrade.v1",
            "ts": result.checked_at.isoformat().replace("+00:00", "Z"),
            "ticket_id": result.ticket_id,
            "status": result.status,
            "violation_codes": [violation.code for violation in result.violations],
            "override": result.override,
            "board_mode": result.board_mode,
            "mode": result.mode,
            "check_latency_ms": round(result.check_latency_ms, 2),
        }
        with self._metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")
        return self._metrics_path

    def _resolve_rules_path(self, profile: str) -> Path:
        if self._rules_path is not None:
            return _resolve_path(self._rules_path)
        candidate = _RULES_DIR / f"pretrade_rules_{profile}.yaml"
        return candidate

    def _reduce_only_enabled(self) -> bool:
        return _read_feature_flag(
            "compliance.reduce_only_suggest",
            path=self._feature_flags_path,
        )


def _read_feature_flag(flag: str, *, path: Path) -> bool:
    profile = os.getenv("TRADECTL_PROFILE") or "paper"
    if not path.exists() or yaml is None:
        return False
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return False
    defaults = payload.get("defaults") or {}
    profile_defaults = defaults.get(profile)
    if not isinstance(profile_defaults, Mapping):
        return False
    return bool(profile_defaults.get(flag, False))


def _resolve_path(path: Path) -> Path:
    if not path.is_absolute():
        candidate = _REPO_ROOT / path
        if candidate.exists():
            return candidate
    return path


def _load_yaml(path: Path) -> Any:
    if yaml is None:
        raise PreTradeRuleValidationError("PyYAML is required to load pretrade rules")
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        raise PreTradeRuleValidationError(str(exc)) from exc


def _validate_schema_if_available(payload: Any, *, schema_path: Path) -> None:
    if jsonschema is None:
        return
    if not schema_path.exists():
        return
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    validator.validate(payload)


def _side_allowed(side: str, allowed: str) -> bool:
    normalized = side.lower()
    allowed_norm = allowed.lower()
    if allowed_norm == "both":
        return True
    return normalized == allowed_norm


def _blocked_by_time_window(
    timestamp: datetime, windows: tuple[BlockedTimeWindow, ...]
) -> bool:
    if not windows:
        return False
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    weekday = timestamp.strftime("%a").lower()[:3]
    now_time = timestamp.timetz().replace(tzinfo=None)
    for window in windows:
        if window.weekday != weekday:
            continue
        if _time_in_window(now_time, window.start, window.end):
            return True
    return False


def _time_in_window(now: time, start: str, end: str) -> bool:
    start_time = _parse_time(start)
    end_time = _parse_time(end)
    if start_time <= end_time:
        return start_time <= now <= end_time
    return now >= start_time or now <= end_time


def _parse_time(value: str) -> time:
    try:
        parsed = datetime.strptime(value, "%H:%M")
    except ValueError:
        parsed = datetime.strptime(value, "%H:%M:%S")
    return parsed.time()


def _violation(
    rule_id: str,
    code: str,
    severity: str,
    value: float | str | bool | None,
    threshold: float | int | str | None,
    message: str,
    rules: PreTradeRuleSet,
) -> PreTradeViolation:
    runbook = rules.runbook_map.get(rule_id)
    return PreTradeViolation(
        rule_id=rule_id,
        code=code,
        severity=severity,
        value=value if not isinstance(value, bool) else str(value).lower(),
        threshold=threshold,
        message=message,
        runbook=runbook,
    )


def _status_from_violations(violations: list[PreTradeViolation]) -> str:
    if not violations:
        return "pass"
    if any(violation.severity == "block" for violation in violations):
        return "blocked"
    return "warn"


def _override_allowed(request: PreTradeCheckRequest, rules: PreTradeRuleSet) -> bool:
    if not request.override_user:
        return False
    if not request.override_reason:
        return False
    if not request.override_roles:
        return False
    allowed = {role.lower() for role in rules.override_roles}
    provided = {role.lower() for role in request.override_roles}
    return bool(allowed & provided)


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


__all__ = [
    "BlockedTimeWindow",
    "ComplianceSummary",
    "PositionLimits",
    "PreTradeAuditError",
    "PreTradeCheckRequest",
    "PreTradeCheckResult",
    "PreTradeComplianceService",
    "PreTradeComplianceError",
    "PreTradeInputError",
    "PreTradeOverrideDenied",
    "PreTradeRuleNotFound",
    "PreTradeRuleSet",
    "PreTradeRuleValidationError",
    "PreTradeViolation",
    "ReduceOnlyNotAvailable",
    "SymbolPositionLimit",
]
