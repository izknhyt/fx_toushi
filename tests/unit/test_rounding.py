from __future__ import annotations

import pytest

from src.sizing.rounding import round_lot


def test_round_lot_floors_to_step() -> None:
    assert round_lot(0.126, lot_step=0.01) == pytest.approx(0.12)
    assert round_lot(1.99, lot_step=0.1) == pytest.approx(1.9)


def test_round_lot_respects_positive_step() -> None:
    with pytest.raises(ValueError):
        round_lot(1.0, lot_step=0)
