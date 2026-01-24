from __future__ import annotations

import json
from pathlib import Path

from src.brokers.monitor import BrokerAlertSink, BrokerApiMonitor


def test_broker_api_monitor_records_metrics(tmp_path: Path) -> None:
    metrics_path = tmp_path / "broker_api.jsonl"
    monitor = BrokerApiMonitor(metrics_path=metrics_path)
    monitor.record(adapter="sandbox", operation="heartbeat", latency_ms=100.0, status="ok")

    lines = metrics_path.read_text(encoding="utf-8").splitlines()
    assert lines
    payload = json.loads(lines[-1])
    assert payload["adapter"] == "sandbox"
    assert payload["operation"] == "heartbeat"


def test_broker_api_monitor_emits_alerts(tmp_path: Path) -> None:
    metrics_path = tmp_path / "broker_api.jsonl"
    alert_log = tmp_path / "broker_alerts.jsonl"
    alert_sink = BrokerAlertSink(log_path=alert_log)
    monitor = BrokerApiMonitor(metrics_path=metrics_path, alert_sink=alert_sink)
    monitor.record(adapter="sandbox", operation="heartbeat", latency_ms=2000.0, status="ok")
    alerts = alert_log.read_text(encoding="utf-8").splitlines()
    assert alerts
