from __future__ import annotations

from pathlib import Path

import pytest

import smtplib

from src.infra.alert import AlertDispatcher


def test_alert_dispatcher_writes_log(tmp_path: Path) -> None:
    log_path = tmp_path / "alerts.jsonl"
    dispatcher = AlertDispatcher(log_path=log_path)
    dispatcher.dispatch(level="warn", message="Latency exceeded")

    payload = log_path.read_text(encoding="utf-8").strip().splitlines()[0]
    assert "Latency exceeded" in payload
    assert "warn" in payload


def test_alert_dispatcher_best_effort(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class _FailingSMTP:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def starttls(self) -> None:
            raise OSError("smtp fail")

        def login(self, *args: object, **kwargs: object) -> None:
            return None

        def send_message(self, *args: object, **kwargs: object) -> None:
            return None

        def __enter__(self) -> "_FailingSMTP":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    monkeypatch.setenv("ALERT_SMTP_HOST", "smtp.local")
    monkeypatch.setenv("ALERT_SMTP_TO", "ops@example.com")
    monkeypatch.setenv("ALERT_SMTP_FROM", "alerts@example.com")
    monkeypatch.setattr(smtplib, "SMTP", _FailingSMTP)

    dispatcher = AlertDispatcher(log_path=tmp_path / "alerts.jsonl")
    dispatcher.dispatch(level="error", message="SMTP down")
