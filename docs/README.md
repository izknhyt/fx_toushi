# Documentation Index

## Development Plan
- Start here: [Development Plan & Task Tracker](development_plan.md) — 開発方針、M1の完了状況、チェックリスト、バックログを一本化した管理ドキュメント。

## Editing Policy
- Update task status and checklists only in `docs/development_plan.md`.
- Treat `docs/archive/` as read-only reference.
- Update runbooks/templates only when operational procedures change.

## Release
- [Release Checklist](release_checklist.md) — リリース時の署名・証跡チェックリスト。

## Archive
- `docs/archive/` — 過去の運用記録・プロンプト・パケット・リリース記録などを保管。

## Trader Sign-off Templates
- [OPS-P4 Ops Readiness Evidence Reset](trader_signoff/OPS-P4.md#1-目的) — 対応シナリオ: [詳細設計 §45](../detailed_design_fx_signal_tool_v1.md#45-ops証跡ガバナンス--スコアリセット制御設計nfr-28-fr-63-ac-51) / [付録D.1 TR-30](../detailed_design_fx_signal_tool_v1.md#付録d1-トレーダー受入チェックシナリオ)。`RUN-DATA-05`、`RUN-POST-03`、`OPS-READINESS-01`の各節と連携し、`reports/validation_log/ops_readiness_<YYYYWW>.md`および`reports/ops/evidence_audit/<YYYYMMDD>.md`を更新する受入テンプレート。
- [TEMPLATE (汎用雛形)](trader_signoff/TEMPLATE.md) — 新規Packet向けの基本構成。

## Runbook Inventory
- `reports/governance/runbook_inventory_status.json` — `OPS-READINESS-01`エントリに`signoff_templates`として`docs/trader_signoff/OPS-P4.md#1-目的`を登録。CI (`make check-ops-readiness`) が存在確認を行い、欠落時は`OpsEvidenceMissing`イベントを発火する。

## Key Operational References
- [OPS-READINESS-01](runbooks/OPS-READINESS-01.md#sign-off) — Ops Readiness評価とエビデンス復旧フロー。`OPS-P4`の受入時に必須。
- [RUN-DATA-05](runbooks/RUN-DATA-05.md#手順) — データ遅延時のReduce-Only運用と証跡収集。
- [`RUN-POST-03`](runbooks/RUN-POST-03.md) — 事後レビュー/フォローアップテンプレ。`OPS-P4`テンプレートでは`#postmortem`節を参照し、`logs/ops/review.log`へ記録する。
- [Offline Install Guide Template](templates/offline_install.md) — `render_install_doc()`が生成するオフラインバンドル向けインストール/検証手順。添付例は[`templates/examples/offline_install_sample.md`](templates/examples/offline_install_sample.md)を参照。

## Validation Playbook
- [Validation Data Playbook Index](validation_playbook/index.md) — クリティカルデータセットの所在・責任者・レビュー頻度を集約。`tradectl data hash` や `make check-validation` で参照するテンプレート (`dataset_template.md`, `review_log_template.md`) も収録。
