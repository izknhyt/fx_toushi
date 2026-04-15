from __future__ import annotations

from pathlib import Path

from src.interfaces.cli.broker import certify


def test_broker_certify_writes_report(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.yaml"
    plan_path.write_text(
        """
plan_id: test_plan
adapter: sandbox
profile: paper
simulate: true
feature_flags: config/feature_flags.yaml
rate_limit_path: config/brokers/sandbox.yaml
slo_path: config/brokers/slo.yaml
evidence_root: {evidence}
metrics_path: {metrics}
scenarios:
  - name: sandbox_connectivity
    type: sandbox_connectivity
""".format(
            evidence=(tmp_path / "evidence"),
            metrics=(tmp_path / "metrics.jsonl"),
        ),
        encoding="utf-8",
    )

    payload = certify(plan_path=plan_path, report_dir=tmp_path / "reports")
    report_path = Path(payload["report_path"])
    assert report_path.exists()
