# RUN-OPS-AGENDA-01: 日次Opsアジェンダ生成・承認手順

> **最終更新日**: 2026-01-12
> **最終更新者**: Codex (Doc Maintainer)

> **参照**: [詳細設計 §52.3 OpsAgendaService](../../detailed_design_fx_signal_tool_v1.md#523-opsagendaservice-srcopsagendapy), [§52.4 CLI & Workflow統合](../../detailed_design_fx_signal_tool_v1.md#524-cli--workflow統合-srcinterfacescliopspy), [§52.5 テレメトリ・監査・受入基準](../../detailed_design_fx_signal_tool_v1.md#525-テレメトリ監査受入基準)
> **関連テンプレート**: [docs/templates/daily_agenda.md](../templates/daily_agenda.md)
> **成果物保管先**: `reports/ops/daily_agenda/`

## 目的
- Acceptable DegradationやKill Switch判断を含む日次TODOを標準化し、Ops/POが共有する。
- `ops_worklog.jsonl`・`automation_effect.jsonl`・Runbookレビュー期限を統合したアジェンダを作成し、`AC-51`証跡と連動させる。

## トリガー
- 平日営業日の前営業日17:30 JSTまでにOps Managerが実施。
- Acceptable Degradation発生日および重大アラート(`health.status ∈ {guarded, hard_stop}`)発生後は当日中に再生成。

## 事前準備
1. 最新の`ops_worklog.jsonl`と`automation_effect.jsonl`をPullし、`sha256sum`を取得（Runbook `RUN-OPS-LOG-01`参照）。
2. `reports/governance/runbook_inventory_status.json`と`validation_playbook/`で期限切れエントリがないか確認。
3. 前回アジェンダ(`reports/ops/daily_agenda/<前日>.md`)の残タスクをレビューし、再掲が必要なものにチェック。

## 手順
1. CLI実行: `tradectl ops agenda --date <対象日> --export-md reports/ops/daily_agenda/<対象日>.md`。
   - 既存ファイルがある場合は`--force`で上書き前にOps Manager/POへ確認。
   - JSON出力は自動で`reports/ops/daily_agenda/agenda_<対象日>.json`へ保存されることを確認。
2. テンプレ反映: 生成されたMarkdownが[docs/templates/daily_agenda.md](../templates/daily_agenda.md)のセクション順を満たしているかチェックし、
   `Critical First`にはRunbookステップID（例: `RUN-DATA-05#step3`）を必ず記入。
3. レビュー: Ops Managerが`Summary`/`Critical First`の内容を確認し、必要に応じて`Operational Tasks`を追記。
4. 承認準備: `Runbook Reviews`と`Validation Pending`セクションをDocOps/Validation担当へ共有し、期限と担当を確定。
5. ダブルサイン: Ops Managerが`Ops Sign-off`欄、POが`PO Sign-off`欄へイニシャルとタイムスタンプを記入。
6. 公開: 完成したアジェンダをOpsチャンネルへ共有し、`docs/development_plan.md#update-log-utc`の該当週エントリへリンクを貼る。

## 承認フロー
| ロール | 責務 | 承認方法 |
| --- | --- | --- |
| Ops Manager | アジェンダ生成・内容レビュー | Markdown内の`Ops Sign-off`欄へ署名 |
| Product Owner | Kill Switch/Board Mode承認、翌営業日TODO合意 | Markdown内の`PO Sign-off`欄へ署名 |
| DocOps (任意) | Runbook更新・レビュー期日の確認 | `Runbook Reviews`欄にコメントを残し`docs/runbooks/`差分をPR化 |

## 記録と証跡
- Ops Worklog: `tradectl ops log add --task agenda_generation --duration <所要分> --notes "RUN-OPS-AGENDA-01#<対象日>"`。
- Validation: `reports/validation_log/AC-51_ops_<対象日>.md`へアジェンダファイルとCLI出力ハッシュを貼付。
- リンク更新: `docs/development_plan.md#update-log-utc`に`reports/ops/daily_agenda/<対象日>.md`を追記。

## Board Mode/Acceptable Degradation 解除チェック（手動）
- 解除条件: (1) 直近15分の`metrics/data_ingestion_sla.jsonl`と`metrics/spread_guard.jsonl`が正常ステータス、(2) `health.status ∈ {ok}`かつ`kill_switch_state != hard_stop`、(3) Runbook該当原因コードの解消を確認。
- 手順: `tradectl status --json`で`board_mode_suggestion`を確認→`tradectl board --normal`で解除→`ops_worklog.jsonl`に`task=board_mode_release`として記録し、`reports/validation_log/CHK-0.6.9_mode_context_*.md`へリンク。
- 監査: 解除時の`board_mode`, `kill_switch_state`, `spread_status`, `profit_readiness_status`, `risk_disclosure_state`, `cfg_hash`, `data_hash`, `consent_reference_id`を記録し、`audit.ticket_action.v2`スキーマで検証する。

## 関連リンク
- [詳細設計 §18.3 Opsワークロードレポートテンプレ](../../detailed_design_fx_signal_tool_v1.md#183-opsワークロードレポートテンプレ-toolsops_workload_reportpy)
- [reports/ops/daily_agenda/README.md](../../reports/ops/daily_agenda/README.md)
- [RUN-OPS-LOG-01](RUN-OPS-LOG-01.md)
