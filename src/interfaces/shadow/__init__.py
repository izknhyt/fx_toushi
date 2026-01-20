"""Shadow interface adapters."""

from .slack_bridge import (
    AckReceipt,
    ShadowChannelConfig,
    ShadowPayload,
    SlackAction,
    SlackShadowBridge,
)

__all__ = [
    "AckReceipt",
    "ShadowChannelConfig",
    "ShadowPayload",
    "SlackAction",
    "SlackShadowBridge",
]
