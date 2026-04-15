---
name: new-strategy
description: Scaffold a new strategy with the Candidate contract pre-wired. Use when starting a new alpha hypothesis that has already passed alpha-critic.
---

# /new-strategy

Scaffold a new strategy with the `Candidate` contract and its mandatory contract test already wired up. Intended to be run **after** `alpha-critic` has given a `proceed to PoC` verdict — not before.

## Arguments

- `$1` — `strategy_id` in snake_case (e.g. `tokyo_close_reversion`, `london_open_momentum`). Must match `^[a-z][a-z0-9_]*$`.

## Behavior

1. Refuse if `src/strategies/$1.py` or `tests/test_$1_contract.py` already exist.
2. Refuse if `$1` contains `ma_rsi`, `baseline`, `scaffolding`, or any string suggesting a placeholder. New strategies must carry their alpha hypothesis in the name.
3. Create `src/strategies/$1.py`:

```python
"""$1 strategy.

Market structure hypothesis: <fill in before implementing — must reference a
specific market behavior, not an indicator).
Edge source: <flow | calendar | session boundary | microstructure | cross-asset | regime transition>
Named failure modes: <at least two>
"""
from __future__ import annotations

from collections.abc import Iterable

from src.contract import Candidate
from src.strategies.base import Strategy, StrategyContext


class $1Strategy(Strategy):
    id = "$1"

    def generate(self, context: StrategyContext) -> Iterable[Candidate]:
        # TODO: implement the alpha hypothesis.
        # Every emitted Candidate must populate all 13 fields (see src/contract.py).
        # estimated_cost must come from config/execution.yaml, not a constant.
        return []
```

4. Create `tests/test_$1_contract.py`:

```python
"""Contract test for $1Strategy — enforces I1 from docs/invariants.md."""
from src.contract import validate_candidate
from src.strategies.$1 import $1Strategy


def test_$1_emits_valid_candidates(sample_context):
    strat = $1Strategy()
    for candidate in strat.generate(sample_context):
        validate_candidate(candidate)  # raises on any missing / invalid field
```

5. Do **not** register the new strategy in `config/strategy.yaml` yet. That only happens after the contract test passes on a real sample context.

## After scaffolding

Remind the user:

- Fill in the module-level docstring *before* writing any code. The hypothesis, edge source, and failure modes go there. If they can't be written concretely, stop and call `alpha-critic` again.
- Do not import from `archive/`. Do not import from `compliance/`, `audit/`, `governance/`, or any other retired module.
- `estimated_cost` must be derived from `config/execution.yaml` via the shared cost helper — not a constant or a guess.
- The strategy is not considered "done" until it passes `test_contract`, `test_parity`, and `test_cost`, and has a provenance sidecar for any emitted backtest metrics.
