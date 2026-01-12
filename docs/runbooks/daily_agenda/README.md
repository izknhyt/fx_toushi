# Daily Ops Agenda Templates

`docs/development_plan.md#update-log-utc`で参照する Ops Agenda を `docs/runbooks/daily_agenda/<YYYY-MM-DD>.md` 形式で管理するためのディレクトリ。日次レビュー前に Ops Manager がテンプレートを複製し、当日の手順・リスクレビュー・Codex連携項目を整理する。

- **テンプレート**: `docs/runbooks/daily_agenda/TEMPLATE.md`
- **命名規則**: `YYYY-MM-DD.md`（例: `2025-03-15.md`）
- **レビュー連携**: Update Logの該当エントリから該当日のファイルへリンクし、完了タスクは`docs/development_plan.md#update-log-utc`へ転記する。
- **履歴**: 過去のアジェンダは`docs/archive/daily_agenda/`へ移動済み。
- **Codexチェックリスト連携**: 詳細設計 §0.6.9 `CHK-0.6.9-6`/`CHK-0.6.9-7` の結果を本テンプレート内の「Codex Hand-off Items」に記録し、`docs/validation/ModeContext_startup.md`の該当行へ証跡リンクを貼る。
