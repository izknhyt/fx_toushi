# Validation Summary (2025-11-10T22:00:05Z)

- Strategy: `m1_baseline_ma_rsi`
- Dataset hash: `c2767c1b16d1ed5cde9dde93efa4309cf34f8ad53389cbeec0a8609cf1ca57d6`
- Config hash: `n/a`

## Threshold Checks
- [x] PF_all ≥ 1.18
- [x] Sharpe(OOS) ≥ 0.85
- [x] MaxDD(OOS) ≤ 0.13
- [x] BCa PF lower ≥ 1.12
- [x] BCa Sharpe lower ≥ 0.78

## Metric Comparison vs Baseline
| Metric | Current | Baseline | Δ |
| --- | --- | --- | --- |
| PF (All) | 1.2942 | 1.2100 | +0.0842 |
| Sharpe (All) | 1.8526 | 1.3100 | +0.5426 |
| MaxDD (All) | 0.0104 | 0.1400 | -0.1296 |
| PF (OOS) | 1.2200 | 1.1900 | +0.0300 |
| Sharpe (OOS) | 0.9200 | 0.8900 | +0.0300 |
| MaxDD (OOS) | 0.1100 | 0.1200 | -0.0100 |

### Dataset Hash Check (2025-11-10T22:00:09Z)
- Strategy: `m1_baseline_ma_rsi`
- Window: 2021-01-01 → 2024-12-31
- Manifest SHA: `c2767c1b16d1ed5cde9dde93efa4309cf34f8ad53389cbeec0a8609cf1ca57d6`
- Recomputed SHA: `c2767c1b16d1ed5cde9dde93efa4309cf34f8ad53389cbeec0a8609cf1ca57d6`
- Status: **MATCHED**

## Notes
- Cause: validation harness bootstrap. No upstream data changes; rerun triggered to establish AC-01/07 baseline with synthetic dataset.
- Data manifest commit: `1846744cb1bd2e4ff9fc98c8c58cc3d465553cc2`
- Logs: `reports/implementation/20251110_pkg-strat-validation-01/logs/backtest_full_20251111.log`
