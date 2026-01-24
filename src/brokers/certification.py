"""Broker API certification suite and evidence writer."""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
import uuid

import yaml

from src.brokers.adapter import BrokerAdapterRegistry
from src.brokers.failover import ApiFailoverPlanner
from src.brokers.monitor import BrokerApiMonitor, BrokerSloConfig, load_rate_limit_window
from src.execution.order_router import OrderDispatchRejected, OrderRouter


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class CertificationScenario:
    name: str
    scenario_type: str
    status: str
    message: str | None
    attachments: list[str]
    metrics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "scenario_type": self.scenario_type,
            "status": self.status,
            "message": self.message,
            "attachments": list(self.attachments),
            "metrics": dict(self.metrics),
        }


@dataclass(slots=True)
class CertificationPlan:
    plan_id: str
    adapter: str
    profile: str
    principal_id: str | None
    device_id: str | None
    simulate: bool
    scenarios: list[dict[str, Any]]
    feature_flags_path: Path
    rate_limit_path: Path
    slo_path: Path
    evidence_root: Path
    metrics_path: Path

    @classmethod
    def from_path(cls, path: Path) -> CertificationPlan:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls(
            plan_id=str(payload.get("plan_id", "broker_certification")),
            adapter=str(payload.get("adapter", "sandbox")),
            profile=str(payload.get("profile", "paper")),
            principal_id=payload.get("principal_id"),
            device_id=payload.get("device_id"),
            simulate=bool(payload.get("simulate", False)),
            scenarios=list(payload.get("scenarios", [])),
            feature_flags_path=Path(payload.get("feature_flags", "config/feature_flags.yaml")),
            rate_limit_path=Path(payload.get("rate_limit_path", "config/brokers/sandbox.yaml")),
            slo_path=Path(payload.get("slo_path", "config/brokers/slo.yaml")),
            evidence_root=Path(payload.get("evidence_root", "evidence/broker_certification")),
            metrics_path=Path(payload.get("metrics_path", "metrics/broker_certification.jsonl")),
        )


@dataclass(slots=True)
class CertificationResult:
    run_id: str
    plan_id: str
    adapter: str
    profile: str
    overall_status: str
    started_at: str
    finished_at: str
    scenarios: list[CertificationScenario]
    evidence_dir: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "plan_id": self.plan_id,
            "adapter": self.adapter,
            "profile": self.profile,
            "overall_status": self.overall_status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "scenarios": [scenario.to_dict() for scenario in self.scenarios],
            "evidence_dir": str(self.evidence_dir),
        }


class EvidenceWriter:
    def __init__(self, *, evidence_dir: Path) -> None:
        self._evidence_dir = evidence_dir

    def write(self, result: CertificationResult) -> Path:
        self._evidence_dir.mkdir(parents=True, exist_ok=True)
        result_path = self._evidence_dir / "result.json"
        result_path.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        for scenario in result.scenarios:
            for attachment in scenario.attachments:
                src = Path(attachment)
                if not src.exists():
                    continue
                dest = self._evidence_dir / src.name
                if src.resolve() != dest.resolve():
                    shutil.copy2(src, dest)
        return result_path


class BrokerCertificationSuite:
    def __init__(
        self,
        *,
        adapter_registry: BrokerAdapterRegistry | None = None,
        monitor: BrokerApiMonitor | None = None,
    ) -> None:
        self._registry = adapter_registry or BrokerAdapterRegistry()
        self._monitor = monitor or BrokerApiMonitor()

    def run(self, plan: CertificationPlan, *, outdir: Path | None = None) -> CertificationResult:
        started_at = _utcnow_iso()
        run_id = f"cert-{uuid.uuid4().hex[:12]}"
        evidence_dir = outdir or plan.evidence_root / run_id
        scenarios: list[CertificationScenario] = []

        if not _feature_enabled(
            flag="brokers.certification_required",
            profile=plan.profile,
            path=plan.feature_flags_path,
        ):
            scenarios.append(
                CertificationScenario(
                    name="certification_bypass",
                    scenario_type="feature_flag_bypass",
                    status="warning",
                    message="brokers.certification_required is false",
                    attachments=[],
                    metrics={},
                )
            )
            overall_status = _rollup_status(scenarios)
            finished_at = _utcnow_iso()
            result = CertificationResult(
                run_id=run_id,
                plan_id=plan.plan_id,
                adapter=plan.adapter,
                profile=plan.profile,
                overall_status=overall_status,
                started_at=started_at,
                finished_at=finished_at,
                scenarios=scenarios,
                evidence_dir=evidence_dir,
            )
            EvidenceWriter(evidence_dir=evidence_dir).write(result)
            self._append_metrics(plan, result)
            return result

        for scenario_def in plan.scenarios or _default_scenarios():
            scenario = self._execute_scenario(plan, scenario_def)
            scenarios.append(scenario)

        overall_status = _rollup_status(scenarios)
        finished_at = _utcnow_iso()
        result = CertificationResult(
            run_id=run_id,
            plan_id=plan.plan_id,
            adapter=plan.adapter,
            profile=plan.profile,
            overall_status=overall_status,
            started_at=started_at,
            finished_at=finished_at,
            scenarios=scenarios,
            evidence_dir=evidence_dir,
        )
        EvidenceWriter(evidence_dir=evidence_dir).write(result)
        self._append_metrics(plan, result)
        return result

    def _execute_scenario(
        self, plan: CertificationPlan, scenario_def: dict[str, Any]
    ) -> CertificationScenario:
        name = str(scenario_def.get("name") or scenario_def.get("scenario") or "unknown")
        scenario_type = str(scenario_def.get("type") or name)
        if plan.simulate:
            return CertificationScenario(
                name=name,
                scenario_type=scenario_type,
                status="pass",
                message="simulated",
                attachments=[],
                metrics={},
            )
        handler = getattr(self, f"_run_{scenario_type}", None)
        if handler is None:
            return CertificationScenario(
                name=name,
                scenario_type=scenario_type,
                status="skipped",
                message="unsupported scenario",
                attachments=[],
                metrics={},
            )
        return handler(plan, scenario_def)

    def _run_sandbox_connectivity(
        self, plan: CertificationPlan, scenario_def: dict[str, Any]
    ) -> CertificationScenario:
        adapter = self._registry.get_adapter(adapter=plan.adapter, profile=plan.profile)
        start = time.perf_counter()
        status = "pass"
        message = None
        try:
            adapter.fetch_positions()
            adapter.fetch_balances()
        except Exception as exc:  # pragma: no cover - defensive
            status = "fail"
            message = str(exc)
        latency_ms = (time.perf_counter() - start) * 1000
        self._monitor.record(
            adapter=plan.adapter, operation="cert_connectivity", latency_ms=latency_ms, status=status
        )
        return CertificationScenario(
            name="sandbox_connectivity",
            scenario_type="sandbox_connectivity",
            status=status,
            message=message,
            attachments=[],
            metrics={"latency_ms": round(latency_ms, 2)},
        )

    def _run_reduce_only_dispatch(
        self, plan: CertificationPlan, scenario_def: dict[str, Any]
    ) -> CertificationScenario:
        principal_id = scenario_def.get("principal_id") or plan.principal_id
        device_id = scenario_def.get("device_id") or plan.device_id
        if not principal_id or not device_id:
            return CertificationScenario(
                name="reduce_only_dispatch",
                scenario_type="reduce_only_dispatch",
                status="fail",
                message="principal_id/device_id required",
                attachments=[],
                metrics={},
            )
        order_router = OrderRouter.from_defaults()
        payload = {
            "ticket_id": f"cert-reduce-{datetime.now(timezone.utc):%Y%m%d%H%M%S}",
            "symbol": scenario_def.get("symbol", "EURUSD"),
            "side": scenario_def.get("side", "buy"),
            "quantity": float(scenario_def.get("quantity", 0.1)),
            "entry_type": "marketable_limit",
            "entry_price": scenario_def.get("entry_price", 1.1),
            "reduce_only": True,
            "adapter": plan.adapter,
            "profile": plan.profile,
            "principal_id": principal_id,
            "device_id": device_id,
        }
        try:
            order = order_router.submit(payload)
            status = "pass"
            message = None
            metrics = {"order_id": order.order_id}
        except OrderDispatchRejected as exc:
            status = "fail"
            message = exc.reason
            metrics = {}
        return CertificationScenario(
            name="reduce_only_dispatch",
            scenario_type="reduce_only_dispatch",
            status=status,
            message=message,
            attachments=[],
            metrics=metrics,
        )

    def _run_rate_limit_burst(
        self, plan: CertificationPlan, scenario_def: dict[str, Any]
    ) -> CertificationScenario:
        limiter = load_rate_limit_window(plan.rate_limit_path)
        slo = BrokerSloConfig.from_path(plan.slo_path)
        burst = int(scenario_def.get("burst", limiter._config.burst))
        deferred = 0
        for _ in range(burst + 1):
            reservation = limiter.reserve_detail(operation="order.place", priority="high")
            if not reservation.allowed:
                deferred += 1
        status = "pass" if deferred > 0 else "warning"
        message = None if deferred > 0 else "no throttle triggered"
        queue_ok = reservation.queue_wait_ms <= slo.queue_warn_sec * 1000
        if not queue_ok:
            status = "fail"
            message = "queue_wait_exceeded"
        return CertificationScenario(
            name="rate_limit_burst",
            scenario_type="rate_limit_burst",
            status=status,
            message=message,
            attachments=[],
            metrics={"deferred": deferred, "queue_wait_ms": reservation.queue_wait_ms},
        )

    def _run_failover_switch(
        self, plan: CertificationPlan, scenario_def: dict[str, Any]
    ) -> CertificationScenario:
        planner = ApiFailoverPlanner()
        plan_result = planner.plan(reason="certification_failover", dispatch=True)
        return CertificationScenario(
            name="failover_switch",
            scenario_type="failover_switch",
            status="pass",
            message=None,
            attachments=[],
            metrics={"plan_id": plan_result.plan_id},
        )

    def _append_metrics(self, plan: CertificationPlan, result: CertificationResult) -> None:
        payload = {
            "ts": _utcnow_iso(),
            "event": "broker_certification",
            "run_id": result.run_id,
            "plan_id": plan.plan_id,
            "adapter": plan.adapter,
            "profile": plan.profile,
            "status": result.overall_status,
            "scenario_count": len(result.scenarios),
        }
        plan.metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with plan.metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")


def _rollup_status(scenarios: Iterable[CertificationScenario]) -> str:
    statuses = {scenario.status for scenario in scenarios}
    if "fail" in statuses:
        return "fail"
    if "warning" in statuses:
        return "pass_with_warning"
    if "skipped" in statuses and len(statuses) == 1:
        return "skipped"
    return "pass"


def _default_scenarios() -> list[dict[str, Any]]:
    return [
        {"name": "sandbox_connectivity", "type": "sandbox_connectivity"},
        {"name": "reduce_only_dispatch", "type": "reduce_only_dispatch"},
        {"name": "rate_limit_burst", "type": "rate_limit_burst"},
        {"name": "failover_switch", "type": "failover_switch"},
    ]


def _feature_enabled(*, flag: str, profile: str, path: Path) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    defaults = payload.get("defaults") if isinstance(payload, dict) else {}
    profile_flags = defaults.get(profile) if isinstance(defaults, dict) else {}
    return bool(profile_flags.get(flag)) if isinstance(profile_flags, dict) else False


def load_result(path: Path) -> CertificationResult:
    payload = json.loads(path.read_text(encoding="utf-8"))
    scenarios = [
        CertificationScenario(
            name=str(item.get("name")),
            scenario_type=str(item.get("scenario_type")),
            status=str(item.get("status")),
            message=item.get("message"),
            attachments=list(item.get("attachments") or []),
            metrics=dict(item.get("metrics") or {}),
        )
        for item in payload.get("scenarios", [])
    ]
    return CertificationResult(
        run_id=str(payload.get("run_id")),
        plan_id=str(payload.get("plan_id")),
        adapter=str(payload.get("adapter")),
        profile=str(payload.get("profile")),
        overall_status=str(payload.get("overall_status")),
        started_at=str(payload.get("started_at")),
        finished_at=str(payload.get("finished_at")),
        scenarios=scenarios,
        evidence_dir=Path(payload.get("evidence_dir") or ""),
    )


def write_validation_report(result: CertificationResult, *, outdir: Path) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    date_label = datetime.now(timezone.utc).strftime("%Y%m%d")
    report_path = outdir / f"AC-06_broker_certification_{date_label}.md"
    lines = [
        f"# Broker Certification ({result.overall_status})",
        "",
        f"- Run ID: {result.run_id}",
        f"- Plan: {result.plan_id}",
        f"- Adapter: {result.adapter}",
        f"- Profile: {result.profile}",
        f"- Started: {result.started_at}",
        f"- Finished: {result.finished_at}",
        f"- Evidence Dir: {result.evidence_dir}",
        "",
        "## Scenario Results",
    ]
    for scenario in result.scenarios:
        lines.append(f"- {scenario.name}: {scenario.status} ({scenario.message or 'ok'})")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


__all__ = [
    "BrokerCertificationSuite",
    "CertificationPlan",
    "CertificationResult",
    "CertificationScenario",
    "EvidenceWriter",
    "load_result",
    "write_validation_report",
]
