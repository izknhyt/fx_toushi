# Daily Ops Agenda Templates

`docs/review_log.md`で参照している Ops Agenda を `docs/runbooks/daily_agenda/<YYYY-MM-DD>.md` 形式で管理するためのディレクトリ。日次レビュー前に Ops Manager がテンプレートを複製し、当日の手順・リスクレビュー・Codex連携項目を整理する。

- **テンプレート**: `docs/runbooks/daily_agenda/TEMPLATE.md`
- **命名規則**: `YYYY-MM-DD.md`（例: `2025-03-15.md`）
- **レビュー連携**: 週次レビュー記録の「Ops Agenda Export」欄から該当日のファイルへリンクし、完了タスクは`docs/review_log.md`の`Next Review Gate`または`Follow-up Tickets`へ転記する。
- **Codexチェックリスト連携**: 詳細設計 §0.6.9 `CHK-0.6.9-6`/`CHK-0.6.9-7` の結果を本テンプレート内の「Codex Hand-off Items」に記録し、`docs/validation/ModeContext_startup.md`の該当行へ証跡リンクを貼る。
