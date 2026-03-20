# Documentation Index

## Current Reference
- Start here: [FX Portfolio Operating System](architecture/fx_portfolio_operating_system.md) — 現行の設計方針。`USDJPY-first / multi-pair-ready / portfolio-first / personal-use` を定義する。
- Then fix v2 shape: [FX Portfolio Tool v2 Specification](architecture/fx_portfolio_tool_v2_spec.md) — 改良版ツールの candidate schema, admission contract, evaluation contract, GUI/CLI surface を定義する。
- Then execute with the default team: [FX Portfolio Development Team](architecture/fx_portfolio_development_team.md) — 現フェーズでの agent 役割分担、ownership 境界、並列開発ルール、bugcheck 完了条件を定義する。
- Then check current gaps: [FX Portfolio Tool v2 Gap Audit](architecture/fx_portfolio_tool_v2_gap_audit.md) — v2 spec と現行実装の差分、M2 の到達点、次に formalize すべき contract を整理する。
- Then read: [Development Plan & Task Tracker](development_plan.md) — 実装進捗、チェックリスト、証跡、backlog の管理台帳。

## Editing Policy
- Update task status and checklists only in `docs/development_plan.md`.
- Treat `docs/archive/` as read-only reference.
- Update runbooks/templates only when the active personal-use workflow changes.

## Personal-Use Defaults
- 単独オペレータ前提。細粒度の承認フロー、sign-off テンプレ、重い audit bundle は default path では使わない。
- 代わりに、設計書、テスト、PoC/shadow evidence、最小限の運用 runbook を維持する。

## Core Workflow Docs
- [Onboarding](onboarding.md) — 新しい開発者/将来の自分向けの最短導線。
- [Release Checklist](release_checklist.md) — 個人利用向けの簡素化された出荷確認。
- [Validation Data Playbook Index](validation_playbook/index.md) — 再現性確認や evidence 参照が必要な場合のみ使用。

## Legacy / Optional Docs
- `docs/governance/`, `docs/trader_signoff/`, `docs/legal/`, `docs/validation_playbook/` の一部は、過去の enterprise 寄り要件か将来の live/broker 拡張向け資産。個人利用の通常開発では必須ではない。
- `detailed_design_fx_signal_tool_v1.md` は既存実装の参照用。新規アーキテクチャ判断は [FX Portfolio Operating System](architecture/fx_portfolio_operating_system.md) を優先する。

## Archive
- `docs/archive/` — 過去の運用記録・プロンプト・パケット・リリース記録などを保管。

## Key Operational References
- [RUN-SHADOW-01](runbooks/RUN-SHADOW-01.md) — shadow 実行の基本導線。
- [RUN-RISK-01](runbooks/RUN-RISK-01.md) — kill switch とリスク制御の最小運用。
- [RUN-DATA-05](runbooks/RUN-DATA-05.md#手順) — データ遅延時の対応。
- [Offline Install Guide Template](templates/offline_install.md) — 必要な場合のみ参照。
