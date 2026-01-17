"""Research pipeline validation and manifest draft helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

DEFAULT_SUITE_PATH = Path("config") / "research_validation.yaml"
DEFAULT_METRICS_DIR = Path("reports") / "research" / "metrics"
DEFAULT_REPORT_DIR = Path("reports") / "research" / "validation"
DEFAULT_MANIFEST_DRAFT_DIR = Path("reports") / "research" / "manifest_drafts"
DEFAULT_PIPELINE_METRICS = Path("metrics") / "research_pipeline.jsonl"


class ResearchPipelineError(RuntimeError):
    """Base error for research pipeline errors."""


class ResearchDataError(ResearchPipelineError):
    """Raised when validation data cannot be loaded."""


@dataclass(slots=True)
class ValidationRule:
    name: str
    min_value: float | None = None
    max_value: float | None = None

    def evaluate(self, value: float | None) -> tuple[bool, str]:
        if value is None:
            return False, "missing"
        if self.min_value is not None and value < self.min_value:
            return False, f"below_min({self.min_value})"
        if self.max_value is not None and value > self.max_value:
            return False, f"above_max({self.max_value})"
        return True, "ok"


@dataclass(slots=True)
class ValidationSuite:
    rules: dict[str, ValidationRule]
    runbook: str | None = None

    @classmethod
    def load(cls, path: Path = DEFAULT_SUITE_PATH) -> ValidationSuite:
        if not path.exists():
            raise ResearchDataError(f"Validation suite not found: {path}")
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        metrics = payload.get("metrics") or {}
        rules: dict[str, ValidationRule] = {}
        for key, entry in metrics.items():
            if not isinstance(entry, Mapping):
                continue
            rules[str(key)] = ValidationRule(
                name=str(key),
                min_value=_coerce_float(entry.get("min")),
                max_value=_coerce_float(entry.get("max")),
            )
        runbook = payload.get("runbook")
        return cls(rules=rules, runbook=str(runbook) if runbook else None)


@dataclass(slots=True)
class ValidationResult:
    strategy_id: str
    window: str
    mode: str
    status: str
    metrics: dict[str, float | None]
    failures: dict[str, str]
    report_path: Path | None
    runbook: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_id": self.strategy_id,
            "window": self.window,
            "mode": self.mode,
            "status": self.status,
            "metrics": dict(self.metrics),
            "failures": dict(self.failures),
            "report_path": str(self.report_path) if self.report_path else None,
            "runbook": self.runbook,
        }


@dataclass(slots=True)
class GateEvaluationResult:
    status: str
    reasons: list[str]

    def to_dict(self) -> dict[str, object]:
        return {"status": self.status, "reasons": list(self.reasons)}


class ResearchPipelineService:
    def __init__(
        self,
        *,
        suite_path: Path = DEFAULT_SUITE_PATH,
        metrics_dir: Path = DEFAULT_METRICS_DIR,
        report_dir: Path = DEFAULT_REPORT_DIR,
        manifest_draft_dir: Path = DEFAULT_MANIFEST_DRAFT_DIR,
        pipeline_metrics: Path = DEFAULT_PIPELINE_METRICS,
    ) -> None:
        self._suite_path = suite_path
        self._metrics_dir = metrics_dir
        self._report_dir = report_dir
        self._manifest_draft_dir = manifest_draft_dir
        self._pipeline_metrics = pipeline_metrics

    def run_validation(
        self,
        *,
        strategy_id: str,
        window: str,
        mode: str,
        metrics: Mapping[str, Any] | None = None,
        metrics_path: Path | None = None,
        export_path: Path | None = None,
    ) -> ValidationResult:
        suite = ValidationSuite.load(self._suite_path)
        metrics_payload = (
            _coerce_metrics(metrics)
            if metrics is not None
            else _load_metrics(strategy_id, window, self._metrics_dir, metrics_path)
        )
        failures: dict[str, str] = {}
        if not metrics_payload:
            result = ValidationResult(
                strategy_id=strategy_id,
                window=window,
                mode=mode,
                status="missing",
                metrics={},
                failures={},
                report_path=None,
                runbook=suite.runbook,
            )
            _append_pipeline_metric(self._pipeline_metrics, result)
            return result

        for name, rule in suite.rules.items():
            value = metrics_payload.get(name)
            ok, reason = rule.evaluate(value)
            if not ok:
                failures[name] = reason

        status = "pass" if not failures else "fail"
        report_path = export_path or self._report_dir / f"{strategy_id}_{window}.md"
        _write_report(report_path, strategy_id, window, mode, metrics_payload, suite, failures)
        result = ValidationResult(
            strategy_id=strategy_id,
            window=window,
            mode=mode,
            status=status,
            metrics=metrics_payload,
            failures=failures,
            report_path=report_path,
            runbook=suite.runbook,
        )
        _append_pipeline_metric(self._pipeline_metrics, result)
        return result

    def evaluate_gate(self, result: ValidationResult) -> GateEvaluationResult:
        if result.status == "pass":
            return GateEvaluationResult(status="pass", reasons=[])
        reasons = [f"{name}:{reason}" for name, reason in result.failures.items()]
        if result.status == "missing":
            reasons.append("validation_metrics_missing")
        return GateEvaluationResult(status="fail", reasons=reasons)

    def generate_manifest(
        self,
        *,
        strategy_id: str,
        idea_id: str | None = None,
        validation: ValidationResult | None = None,
        data_manifest_path: Path = Path("reports") / "data_manifest.json",
        validation_playbook_id: str | None = None,
    ) -> Path:
        self._manifest_draft_dir.mkdir(parents=True, exist_ok=True)
        draft_path = self._manifest_draft_dir / f"{strategy_id}_{_date_stamp()}.yaml"
        payload: dict[str, Any] = {
            "schema_version": "research.manifest.v1",
            "strategy_id": strategy_id,
            "idea_id": idea_id,
            "generated_at": _utcnow_iso(),
            "validation_playbook_id": validation_playbook_id,
            "datasets": _load_dataset_refs(strategy_id, data_manifest_path),
            "metrics": validation.metrics if validation else {},
            "status": "draft",
        }
        draft_path.write_text(_dump_yaml(payload), encoding="utf-8")
        return draft_path


def _load_metrics(
    strategy_id: str,
    window: str,
    metrics_dir: Path,
    override_path: Path | None,
) -> dict[str, float | None]:
    path = override_path or metrics_dir / f"{strategy_id}_{window}.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _coerce_metrics(payload)


def _coerce_metrics(payload: Mapping[str, Any]) -> dict[str, float | None]:
    metrics: dict[str, float | None] = {}
    for key, value in payload.items():
        metrics[str(key)] = _coerce_float(value)
    return metrics


def _write_report(
    path: Path,
    strategy_id: str,
    window: str,
    mode: str,
    metrics: Mapping[str, float | None],
    suite: ValidationSuite,
    failures: Mapping[str, str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Research Validation ({strategy_id})",
        "",
        f"- Window: {window}",
        f"- Mode: {mode}",
        f"- Status: {'PASS' if not failures else 'FAIL'}",
        "",
        "| Metric | Value | Min | Max | Status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name, rule in suite.rules.items():
        value = metrics.get(name)
        status = failures.get(name, "ok")
        lines.append(
            "| {metric} | {value} | {min} | {max} | {status} |".format(
                metric=name,
                value="n/a" if value is None else f"{value:.4f}",
                min="" if rule.min_value is None else rule.min_value,
                max="" if rule.max_value is None else rule.max_value,
                status=status,
            )
        )
    if suite.runbook:
        lines.append("")
        lines.append(f"- Runbook: {suite.runbook}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_pipeline_metric(path: Path, result: ValidationResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ts": _utcnow_iso(),
        "event": "research.validation.completed",
        "strategy_id": result.strategy_id,
        "window": result.window,
        "mode": result.mode,
        "status": result.status,
        "failures": list(result.failures.keys()),
        "report_path": str(result.report_path) if result.report_path else None,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _load_dataset_refs(strategy_id: str, path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    entry = (payload.get("strategies") or {}).get(strategy_id) or {}
    if not entry:
        return []
    return [
        {
            "id": strategy_id,
            "path": entry.get("dataset_path"),
            "sha256": entry.get("dataset_sha256"),
            "window": entry.get("dataset_window"),
        }
    ]


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _date_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _dump_yaml(payload: Mapping[str, Any]) -> str:
    dumper = getattr(yaml, "safe_dump", None)
    if dumper:
        return dumper(payload, sort_keys=False)
    return "# JSON\n" + json.dumps(payload, ensure_ascii=False, indent=2)


__all__ = [
    "ResearchPipelineService",
    "ResearchPipelineError",
    "ResearchDataError",
    "ValidationSuite",
    "ValidationResult",
    "GateEvaluationResult",
]
