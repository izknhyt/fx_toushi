# Onboarding Checklist

最初に読む順番を固定する。

1. [ ] Read [FX Portfolio Operating System](architecture/fx_portfolio_operating_system.md).
2. [ ] Read [Development Plan](development_plan.md) and confirm the active task/backlog row.
3. [ ] Review the latest portfolio evidence under `reports/analysis/` and `reports/validation_log/`.

その上で、ローカル実行系を確認する。

4. [ ] Verify local tooling setup (`poetry`, `pytest`, `schema-validate`, `tradectl`).
5. [ ] Run one dry-run research or backtest flow and record the exact command.
6. [ ] Run one shadow/runtime status flow and confirm where logs, reports, and snapshots are written.

個人利用の運用前提もここで確認する。

7. [ ] Understand that multi-role approvals and heavy audit bundles are optional legacy flows, not the default path.
8. [ ] Know the minimum docs to keep current: architecture doc, `docs/development_plan.md`, relevant manifests/configs, and evidence paths.
