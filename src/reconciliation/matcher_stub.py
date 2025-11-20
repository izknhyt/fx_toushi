"""Matcher stub."""

from __future__ import annotations

from typing import Sequence


def match_entries(left: Sequence[str], right: Sequence[str]) -> bool:
    return len(left) == len(right)


__all__ = ["match_entries"]
