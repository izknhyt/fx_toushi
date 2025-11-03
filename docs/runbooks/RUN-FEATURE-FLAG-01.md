# RUN-FEATURE-FLAG-01: Feature Flag段階的有効化手順

> **ACカバレッジ**: AC-31, AC-34, AC-43, AC-45  
> **Runbook版数**: v1.0  
> **最終更新日**: 2025-03-20  
> **最終更新者**: Ops Manager (Doc Maintainer)  
> **関連設計**: `detailed_design_fx_signal_tool_v1.md §0.6.13`, `§3.5`, `§7.6`, `§8.6`  
> **関連CLI**: `poetry run pytest -k feature_flags`, `poetry run pytest -k config_schema_smoke`, `tradectl config flags --get`, `tradectl config flags --set <flag>=<value> --profile <mode>`, `tradectl restart --profile <mode>`（必要時）, `tradectl status --board --gates`  
> **イベントログ**: `logs/audit/config_flags_*.jsonl`, `logs/events/config_changes.jsonl`, `metrics/feature_flags.jsonl`, `reports/ops/feature_flag_changes.md`

## 目的
- Feature Flag の有効化/無効化をマイルストーン毎に安全に実施し、Backtest/Paper/Live それぞれのガードレールと整合させる。
- 変更前後で `config_schema_smoke` および Feature Flag 専用テスト (`pytest -k feature_flags`) が通過していることを保証し、監査証跡を残す。
- 危険度（safe/guarded/dangerous）に応じた承認フローとロールバック手順を標準化し、Ops/Risk/PO によるダブルサインを徹底する。

## 適用範囲・トリガー
- `config/feature_flags.yaml` の `defaults` または `definitions` を更新する場合。
- `tradectl config flags --set ...` で Paper/Live プロファイルの Flag を切り替える場合。
- マイルストーン到達に伴い、`detailed_design_fx_signal_tool_v1.md §0.6.13` のマトリクスで「有効条件」を満たしたと判断した場合。

## 事前準備 / 前提条件
- `poetry install --no-root` 完了済み。`pytest -k config_schema_smoke` と `pytest -k feature_flags` がローカルで 0 終了する。
- 変更対象フラグの Runbook セクション（本書 5章）を読み、必要メトリクスや CLI エビデンスの採取計画を立てている。
- `logs/audit/config_flags_<date>.jsonl` に追記可能であり、Ops Worklog (`reports/ops/worklog_<date>.md`) にサマリを残す準備ができている。
- Live で dangerous フラグを操作する場合、Risk Manager・Ops Manager・PO の連絡体制が即応可能である。
- Pull Request では `detailed_design_fx_signal_tool_v1.md §0.6.13` の参照IDと、テストログ（`pytest -k config_schema_smoke`, `pytest -k feature_flags`）を添付する。

## 変更承認マトリクス

| フラグ危険度 | 代表例 | 必須レビュー / 承認 | 追加要件 |
| --- | --- | --- | --- |
| safe | `reporter.enable_extended_blocks` | Ops Manager 単独 | CLIキャプチャをEvidenceへ保存 |
| guarded | `reduce_only_advisor`, `reports.performance.enable` | Ops Manager + Risk Manager | Paper soak (≥5取引日) レポート添付 |
| dangerous | `sprt_guard`, `risk_disclosure_enforce`, `data.paid_feed` | Ops Manager + Risk Manager + PO | ① Backtest再現ログ ② Paper 手動検証ログ ③ Rollbackリハーサル記録 |

## 標準フロー
1. `poetry run pytest -k config_schema_smoke` と `poetry run pytest -k feature_flags` を実行し、結果ログを `reports/validation_log/<date>_feature_flags.txt` に保存。
2. `tradectl config flags --get --profile <mode>` で現行値を取得し、Evidence（`reports/ops/feature_flag_changes.md`）へ貼り付ける。
3. `config/feature_flags.yaml` を更新し、Pull Request で Runbook参照ID・マイルストーン・承認者を明記。
4. Paper → Live の順で段階的に反映する（Live へ適用する前に Paper で 2 営業日 soak）。適用後は `tradectl status --board --gates` と `tradectl telemetry tail --subscription feature_flags`（予定）で挙動を確認。
5. `logs/audit/config_flags_<date>.jsonl` へ操作記録を追記し、Ops Worklog を更新。必要に応じて Slack #ops-alert へ通知。
6. ロールバックが不要と判断されたら、Evidence に承認者サインと検証結果を添付して完了。

## 監視指標
- `metrics/feature_flags.jsonl`：`event=flag_enabled/flag_disabled`, `mode`, `reason`, `milestone` を確認。
- `logs/events/config_changes.jsonl`：`flag_delta` に対象フラグが記録されていること。
- Spread/リスク系フラグでは `metrics/spread_guard.jsonl`, `metrics/risk_disclosure.jsonl` を併せてレビュー。

## 5. フラグ別手順

### 5.1 `sprt_guard`（M2, dangerous）
1. Runbook: 本節と `detailed_design_fx_signal_tool_v1.md §45.2` を参照。
2. Paper soak 条件: `metrics/sprt_health.jsonl` で `warning_rate<=0.05`, `false_positive=0` を 10 取引日継続。
3. `config/feature_flags.yaml` の `defaults.paper.sprt_guard` を `true` に変更 → soak 実施 → Evidence に結果追記。
4. Live で有効化する際は `defaults.live.sprt_guard` を `true` にし、`tradectl config flags --set sprt_guard=true --profile live` で反映。即時に `NextBarChangeQueue` の出力と `GateState.market.sprt_guard` を確認。
5. **Rollback**: `tradectl config flags --set sprt_guard=false --profile live`, `git revert` 等で設定戻し → `pytest -k feature_flags` 再実行 → 監視指標が基準値へ戻ったことを確認。

### 5.2 `reduce_only_advisor`（M1.1, guarded）
1. Spread訓練完了チェック: `RUN-SPREAD-03` のチェックリストが最新であること。
2. Paper soak: `reports/ops/degradation_log/<date>.md` に 5 取引日分の Reduce-Only 提案ログを添付。
3. `defaults.paper.reduce_only_advisor` を `true` に設定し、`tradectl status --board` で提案カードが表示されるか確認。
4. Live 適用は M1.1 終了後。`defaults.live.reduce_only_advisor=true` に変更し、`risk_manager` がダブルサイン。
5. **Rollback**: `tradectl config flags --set reduce_only_advisor=false --profile <mode>`。Paper/Live 双方で提案が消えることを確認。

### 5.3 `risk_disclosure_enforce`（M1.1, dangerous）
1. 事前条件: `docs/runbooks/RUN-RISK-01.md` と `GOV-AUD-01` の手順を完了。`risk_disclosure_state` が最新バージョン。
2. Paper soak: `tradectl risk disclosure prompt --profile paper` を 3 連続セッションで実施し、`ConsentRequiredError` が想定通り出ることを Evidence に記録。
3. `defaults.paper.risk_disclosure_enforce=true` に変更後、`pytest -k feature_flags` と `pytest -k strategy_manifest` を再実行（相互依存確認）。
4. Live 適用は PO 承認後、`tradectl kill-switch review --recommendation guarded` が WARN 以上でないことを確認してから `defaults.live.risk_disclosure_enforce=true` に更新。
5. **Rollback**: `defaults.live.risk_disclosure_enforce=false`、CLI でも `tradectl config flags --set ...` を実施。`risk_consent` 監査ファイルへの追記が継続できるか確認。

### 5.4 `reporter.enable_extended_blocks`（M1.1, safe）
1. `reports/weekly/templates/m1_core.md` に extended ブロックが空であることを確認。
2. `defaults.backtest.reporter.enable_extended_blocks=true` で雛形を生成し、`make reports-weekly --dry-run`（予定）で差分が出るか検証。
3. 問題が無ければ Paper/Live も `true` に設定。Slack 共有テンプレートでレイアウト崩れが無いことをスクリーンショットで証跡化。
4. **Rollback**: `defaults.<mode>.reporter.enable_extended_blocks=false` に戻すだけで良い。監査ログとテンプレートの差分を削除。

### 5.5 `reports.performance.enable`（M1.2, guarded）
1. `metrics/performance_snapshot.jsonl` の生成パイプが完成し、`reports/performance/latest.md` が 3 回連続で生成されていること。
2. Backtest/Paper で `defaults.<mode>.reports.performance.enable=true` に切り替え `tradectl reports performance --profile <mode>` を実行。
3. Live 適用前に Storage コスト評価（`AC-45`）を実施し、`ops_automation_writers` チームへ共有。
4. **Rollback**: `defaults.<mode>.reports.performance.enable=false` へ戻し、レポート生成ジョブを停止。`reports/performance/` の不要ファイルをアーカイブ。

### 5.6 `data.paid_feed`（M1.2, dangerous）
1. `basic_design_fx_signal_tool_v1.md §1.4` の公式API移行計画を完了。ライセンス契約書とコスト承認を Evidence に添付。
2. Backtest 用に Paid Feed シミュレータ（`tools/paid_feed_stub.py` 予定）が動作することを `pytest -k data_status_cli` で確認。
3. Paper 適用時は `defaults.paper.data.paid_feed=true` とし、`tradectl data status --profile paper` で SLA 指標が閾値内に収まるか確認。
4. Live 適用は PO/Compliance ダブルサイン必須。`defaults.live.data.paid_feed=true` に更新後、`RUN-DATA-05` と `RUN-DATA-06` を再実施。
5. **Rollback**: `defaults.live.data.paid_feed=false`。代替データソースへ即時フェイルバックし、`metrics/data_ingestion_sla.jsonl` が回復したことを確認。

## ロールバック共通手順
1. `tradectl config flags --set <flag>=false --profile <mode>` を即時実行し、`metrics/feature_flags.jsonl` に `flag_disabled` が記録されたことを確認。
2. `git checkout -- config/feature_flags.yaml` ではなく、必ず PR で差分を戻しレビューを受ける。
3. `pytest -k feature_flags` と関連スモークテストを再実行。
4. Ops Worklog と監査ログへロールバック理由と結果を追記し、承認者サインを取得。
