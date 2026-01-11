from __future__ import annotations

import json
from pathlib import Path

from src.compliance import RiskDisclosureService
from src.core.gate import GateAggregator, GateState


def test_gate_state_hashes_can_be_set_and_serialised() -> None:
    agg = GateAggregator()
    agg.set_hashes(cfg_hash="sha256:cfg-abc", data_hash="sha256:data-xyz")
    snapshot = agg.snapshot()
    assert snapshot.cfg_hash == "sha256:cfg-abc"
    assert snapshot.data_hash == "sha256:data-xyz"
    payload = snapshot.to_dict()
    assert payload["cfg_hash"] == "sha256:cfg-abc"
    assert payload["data_hash"] == "sha256:data-xyz"


def test_gate_state_hashes_used_in_cli_actions(tmp_path: Path, monkeypatch) -> None:
    # Ensure Ticket CLI can ingest GateState hashes when guardrails overrides are absent.
    from src.interfaces.cli import tickets

    monkeypatch.setattr(tickets, "TICKET_STORE_PATH", tickets.Path("ignored.jsonl"))
    monkeypatch.setattr(tickets, "OPS_WORKLOG_PATH", tickets.Path("ops_worklog.jsonl"))
    monkeypatch.setattr(tickets, "AUDIT_PATH", tickets.Path("audit.jsonl"))
    monkeypatch.setattr(
        tickets,
        "RiskDisclosureService",
        lambda: RiskDisclosureService(
            state_path=tmp_path / "risk_state.json", audit_dir=tmp_path / "audit_dir"
        ),
    )

    gate_state = GateState(
        cfg_hash="sha256:" + "c" * 64,
        data_hash="sha256:" + "d" * 64,
    )
    result = tickets.approve("t-hash", user="alice", gate_state=gate_state)
    assert result["status"] == "ok"
    audit_text = tickets.Path("audit.jsonl").read_text(encoding="utf-8").strip().splitlines()[-1]
    audit = tickets.json.loads(audit_text)
    assert audit["cfg_hash"] == "sha256:" + "c" * 64
    assert audit["data_hash"] == "sha256:" + "d" * 64


def test_persist_latest_resolves_hashes_from_env_and_manifest(tmp_path: Path, monkeypatch) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("dummy", encoding="utf-8")
    manifest_dir = tmp_path / "reports"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "data_manifest.json").write_text(
        json.dumps(
            {"strategies": {"m1_baseline_ma_rsi": {"dataset_sha256": "sha256:data-manifest"}}}
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("TRADECTL_CFG_PATH", str(cfg_path))
    monkeypatch.chdir(tmp_path)
    agg = GateAggregator()
    out = agg.persist_latest(tmp_path / "gate.json")
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["cfg_hash"].startswith("sha256:")
    assert payload["data_hash"] == "sha256:data-manifest"
