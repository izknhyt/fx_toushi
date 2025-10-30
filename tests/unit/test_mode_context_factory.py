"""Unit tests for the ModeContextFactory scaffolding."""

from __future__ import annotations

import pytest

from src.app.mode_context import (
    AccountGateway,
    DataFeedBundle,
    ExecutionProfile,
    MarketClock,
    ModeContextFactory,
)
from src.core.session import SessionConfig, create_session_context


@pytest.mark.parametrize("profile_name", ["backtest", "paper", "live"])
def test_factory_produces_deterministic_mode_context(profile_name: str) -> None:
    factory = ModeContextFactory()
    session_id = "session-0001"

    context_first = factory.create(profile_name, session_id=session_id)
    context_second = factory.create(profile_name, session_id=session_id)

    assert context_first.mode == context_first.profile.mode
    assert context_first.profile.profile_id == profile_name
    assert context_first.deterministic_seed == context_second.deterministic_seed
    assert isinstance(context_first.clock, MarketClock)
    assert isinstance(context_first.data_feeds, DataFeedBundle)
    assert isinstance(context_first.execution_profile, ExecutionProfile)
    assert isinstance(context_first.account_gateway, AccountGateway)
    assert context_first.audit_channel.profile_id == profile_name
    assert context_first.data_feeds.primary


def test_create_session_context_validates_config_alignment() -> None:
    factory = ModeContextFactory()
    config = SessionConfig(
        mode="backtest",
        profile_name="backtest",
        mode_factory=factory,
    )

    session_context = create_session_context(
        profile_name="backtest",
        session_id="session-123",
        config=config,
    )

    assert session_context.mode_context is not None
    assert session_context.mode == "backtest"
    assert session_context.mode_context.profile.profile_id == "backtest"

    mismatched_config = SessionConfig(
        mode="paper",
        profile_name="paper",
        mode_factory=factory,
    )

    with pytest.raises(ValueError):
        create_session_context(
            profile_name="backtest",
            session_id="session-123",
            config=mismatched_config,
        )

    mismatched_profile = SessionConfig(
        mode="backtest",
        profile_name="paper",
        mode_factory=factory,
    )

    with pytest.raises(ValueError):
        create_session_context(
            profile_name="backtest",
            session_id="session-123",
            config=mismatched_profile,
        )
