"""Evidence hash stub."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class EvidenceDigest:
    artifact: str
    sha256: str


__all__ = ["EvidenceDigest"]
