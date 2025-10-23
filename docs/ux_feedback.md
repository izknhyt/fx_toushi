# UXフィードバック登録簿

本ファイルはHITLトレーダーおよび運用担当からのUX改善要求を一元的に管理し、Codexへの改善依頼テンプレート (§0.6.2) にリンクする。

## 管理情報
- **目的**: ユーザビリティ課題・改善要求を時系列で管理し、優先度付けとPacket化の判断に活用する。
- **更新頻度**: 週次Opsレビュー後24時間以内、臨時の重大UX障害は発生当日中に暫定記録。
- **責任者**: Ops Manager（初期記入）、Product Owner（優先度確定）、Codex Liaison（対応ステータス更新）。
- **記録フォーマット**: 下記テーブルに1行ずつ追加し、関連するエビデンスとテンプレ参照を必ず明記する。

## 記録テンプレート
| 記録日 | 事象カテゴリ | ペルソナ | シナリオ/Runbook | 課題概要 | Severity (S1-S4) | 推奨Packet | エビデンス | ステータス | 最終更新者 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2025-02-21 | <例: Board UX> | <Trader/Ops> | <RUN-SIGNAL-02> | <Ticket表示が遅い> | S2 | <EP04-P3案> | <screenshots/...> | logged | <名前> |

- エビデンスは`reports/ux/<YYYYMMDD>_<slug>/`配下に保存し、スクリーンショットは`docs/trader_signoff/`の該当Packet参照を追記する。
- ステータスは`logged → triaged → in_progress → validated → closed`を想定し、変更時はGit履歴に加えて末尾へ`Update:`行を追記する。
- Packet化された項目は`docs/prompt_packages/<YYYYMMDD>_<feature>.md`にリンクし、改善要望の優先度タグ（must/should/nice）を再掲する。
