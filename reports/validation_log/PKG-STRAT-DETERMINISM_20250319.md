# PKG-STRAT-DETERMINISM Validation — 2025-03-19

| Command | Result | Notes |
| --- | --- | --- |
| `pytest tests/integration/test_strategy_engine.py tests/integration/test_strategy_determinism.py -vv` | ✅ 3 passed (0.05s) | Covers registry determinism fixture + new replay parity test. |
| `pytest tests/integration/test_strategy_determinism.py -vv` | ✅ 1 passed (0.04s) | Dedicated replay harness run for evidence capture. |

## Metrics
- `metrics/benchmark_replay.jsonl` updated with digest `b983fb3e4a67f17ba39d0f97` (seed `987654`, watchlist `["EURUSD","USDJPY"]`).

## Notes
- `pytest -k strategy_determinism` intermittently SIGSEGVs on macOS Python 3.10.9 when filtering tests. Executing explicit file targets (above) runs the same coverage without issue; retain this workaround until the upstream pytest filter bug is fixed.

## Sign-off
- Ops Manager (prep): 2025-03-19T10:55+09:00
