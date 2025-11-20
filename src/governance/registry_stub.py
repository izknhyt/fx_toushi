"""Governance registry stub."""

from __future__ import annotations

from typing import Mapping


class GovernanceRegistryStub:
    def fetch(self, identifier: str) -> Mapping[str, object]:
        return {"id": identifier, "status": "draft"}


__all__ = ["GovernanceRegistryStub"]
