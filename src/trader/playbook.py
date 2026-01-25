"""Trader playbook selection based on feedback history (detailed design §88)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(slots=True)
class FeedbackRecord:
    playbook_id: str
    realized_rr: float
    slippage_bp: float = 0.0
    max_adverse: float = 0.0

    def score(self) -> float:
        return self.realized_rr - (self.slippage_bp / 100.0) - (self.max_adverse * 0.01)


@dataclass(slots=True)
class PlaybookSelection:
    primary: str | None
    alternatives: tuple[str, ...]
    confidence: float

    def to_dict(self) -> dict[str, object]:
        return {
            "primary": self.primary,
            "alternatives": list(self.alternatives),
            "confidence": self.confidence,
        }


class TraderPlaybookService:
    def __init__(self, *, min_delta: float = 0.05) -> None:
        self._min_delta = min_delta

    def match(
        self,
        *,
        playbooks: Iterable[str],
        feedback: Iterable[FeedbackRecord],
        fallback: str | None = None,
    ) -> PlaybookSelection:
        scores: dict[str, list[float]] = {playbook: [] for playbook in playbooks}
        for record in feedback:
            if record.playbook_id in scores:
                scores[record.playbook_id].append(record.score())
        averages = {
            playbook: (sum(values) / len(values)) if values else None
            for playbook, values in scores.items()
        }
        ranked = [
            (playbook, avg)
            for playbook, avg in averages.items()
            if avg is not None
        ]
        ranked.sort(key=lambda item: item[1], reverse=True)
        if not ranked:
            return PlaybookSelection(primary=fallback, alternatives=(), confidence=0.0)

        primary, top_score = ranked[0]
        alternatives = []
        if len(ranked) > 1:
            second_score = ranked[1][1]
            if top_score - second_score < self._min_delta:
                alternatives = [playbook for playbook, _ in ranked[:2]]
        confidence = max(0.0, min(1.0, (top_score - (ranked[1][1] if len(ranked) > 1 else 0.0))))
        return PlaybookSelection(
            primary=primary,
            alternatives=tuple(alternatives),
            confidence=round(confidence, 4),
        )


__all__ = ["FeedbackRecord", "PlaybookSelection", "TraderPlaybookService"]
