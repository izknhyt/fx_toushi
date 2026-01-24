from __future__ import annotations

import json
from pathlib import Path

from src.brokers.certification import BrokerCertificationSuite, CertificationPlan


def test_certification_suite_simulated(tmp_path: Path) -> None:
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
    plan = CertificationPlan.from_path(plan_path)
    suite = BrokerCertificationSuite()
    result = suite.run(plan)
    assert result.overall_status in {"pass", "pass_with_warning"}
    result_path = result.evidence_dir / "result.json"
    assert result_path.exists()
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["plan_id"] == "test_plan"
