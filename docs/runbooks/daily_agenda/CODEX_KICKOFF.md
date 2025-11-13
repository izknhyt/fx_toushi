# Codex開始日次アジェンダ（CHK-0.6.9連動）

Codexへ実装委譲を開始する前に、トレーダー/開発/運用の三者が最低限揃えておくべき証跡とアクションを日次アジェンダとして整備する。詳細設計書 §0.6.9 に定義されたチェックIDと一対一に対応しており、完了結果は `reports/validation_log/CHK-0.6.9_20250305.md` へ転記する。

## 1. 事前準備（08:30-08:45）
- [ ] **CHK-0.6.9-1**: `ci/templates/python_smoke.yml` を参照し、本日の開発ブランチを対象に GitHub Actions の Python Smoke を手動実行またはスケジュール設定する。
- [ ] **CHK-0.6.9-2**: `docs/prompt_packages` 内の最新プロンプト草案を確認し、差分概要と対象セクション引用が揃っているかチェックする。

## 2. 運用同期（08:45-09:00）
- [ ] **CHK-0.6.9-3**: `docs/runbooks/RUN-DATA-05.md` と `RUN-RISK-01.md` の更新履歴を確認し、Acceptable Degradation対応手順に差分がないかレビューする。
- [ ] **CHK-0.6.9-4**: `logs/ops/workload.log` の直近24時間分を確認し、Guard解除の pending 項目が無いことを口頭確認する。

## 3. Codexブリーフィング（09:00-09:20）
- [ ] **CHK-0.6.9-5**: `reports/validation_log/CHK-0.6.9_20250305.md` の前回記録を開き、未完了項目・フォローアップメモを更新する。
- [ ] **CHK-0.6.9-6**: `docs/runbooks/daily_agenda/CODEX_KICKOFF.md` 本ファイルを最新版へ diff チェックし、必要なら追加 TODO を追記する。

## 4. ブランチ着手宣言（09:20-09:30）
- [ ] **CHK-0.6.9-7**: `docs/review_log.md` にて着手予定チケットのレビュア/承認者を明記し、Codex へ共有するブリーフィングメモ（Issue/PRリンク）を貼付する。

## 5. 記録テンプレート
```
- 日付: <YYYY-MM-DD>
- 参加者: PO / Ops / Dev
- CHK-0.6.9-1: ✅/❌（補足: ...）
- CHK-0.6.9-2: ✅/❌（補足: ...）
- CHK-0.6.9-3: ✅/❌（補足: ...）
- CHK-0.6.9-4: ✅/❌（補足: ...）
- CHK-0.6.9-5: ✅/❌（補足: ...）
- CHK-0.6.9-6: ✅/❌（補足: ...）
- CHK-0.6.9-7: ✅/❌（補足: ...）
- 次アクション: ...
```

## 6. 参照資料
- `ci/templates/python_smoke.yml` — Codex開始前に最低限通すべき CI ワークフローテンプレート。
- `reports/validation_log/CHK-0.6.9_20250305.md` — 日次アジェンダ完了結果の証跡。
- `docs/runbooks/RUN-DATA-05.md`, `docs/runbooks/RUN-RISK-01.md` — Acceptable Degradation対応手順。
- `docs/review_log.md` — レビュー体制更新ログ。
