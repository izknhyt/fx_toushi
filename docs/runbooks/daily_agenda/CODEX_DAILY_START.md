# Daily Agenda - Codex Start Shift

- **目的**: Codexとの共同開発開始前に運用と開発の着手条件を揃え、チェックリスト§0.6.9（CHK-0.6.9-1〜7）を毎朝確認する。
- **頻度**: 平日 09:30 JST（マーケット前の30分）。
- **参加者**: Ops担当（リード）、プロダクトオーナー、Codex窓口エンジニア。

## 1. プレフライト確認（CHK-0.6.9-1,2）
1. `ci/templates/python_smoke.yml` が最新コミットに追従しているかをPR差分で確認し、変更がある場合はテンプレートのPull Request URLを共有する。
2. GitHub Actions `python_smoke` 呼び出しが前日成功しているかを`reports/ci/python_smoke.xml`で確認。失敗時は原因と再実行計画を`reports/validation_log/CHK-0.6.9-run.md`に記録。

## 2. Runbook & Agenda同期（CHK-0.6.9-3,4）
1. 当日対応予定のスプリント/Runbookを列挙し、該当手順の最新改訂日を確認。
2. `docs/runbooks/RUN-DATA-05.md`と`RUN-RISK-01.md`の該当セクションに未完了のチェックがないかを読み上げる。
3. Acceptable Degradation状態のペアがある場合は`reports/validation_log/AC-45_sla_20250220.md`と照合し、復旧担当をアサイン。

## 3. メトリクスとログ収集（CHK-0.6.9-5）
1. `metrics/data_ingestion_sla.jsonl` の最新24時間の`fetch_p95`が閾値（< 30分）内かを確認。
2. `logs/audit/ticket.jsonl`に未レビューの`ticket.edit`イベントが無いか集計し、該当チケット番号をIssueにリンク。

## 4. Codexワークリクエスト準備（CHK-0.6.9-6）
1. 当日Codexに依頼するワークパッケージの`docs/prompt_packages`ファイルを読み合わせ、関連Runbook/Validation Logへのリンクが揃っているかを確認。
2. 不足する証跡がある場合は`docs/runbooks/daily_agenda/notes/<YYYYMMDD>.md`を作成し、追補期限を明記。

## 5. クロージング（CHK-0.6.9-7）
1. 本日のHITLオペレーション責任者とCodexレビュワーを指名し、`reports/validation_log/CHK-0.6.9-run.md`へ署名（名前／時刻）を追記。
2. 未決事項を`docs/runbooks/daily_agenda/backlog.md`へ転記し、翌営業日のアジェンダへ引き継ぐ。

---
- **完了条件**: 参加者全員がチェックボックスを完了し、署名ログに記入したことをOpsリードが確認。
- **証跡**: `reports/validation_log/CHK-0.6.9-run.md`, `docs/runbooks/daily_agenda/notes/<date>.md`。
