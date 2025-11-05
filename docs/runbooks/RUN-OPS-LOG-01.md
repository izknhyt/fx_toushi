# RUN-OPS-LOG-01: Ops Worklog 記録・検証手順

> **参照**: [詳細設計 §52.1 OpsWorklogService](../../detailed_design_fx_signal_tool_v1.md#521-opsworklogservice-srcopsworklogpy), [§52.4 CLI & Workflow統合](../../detailed_design_fx_signal_tool_v1.md#524-cli--workflow統合-srcinterfacescliopspy), [§18.3 Opsワークロードレポートテンプレ](../../detailed_design_fx_signal_tool_v1.md#183-opsワークロードレポートテンプレ-toolsops_workload_reportpy)
> **関連テンプレート**: [docs/templates/ops_workload_report.md](../templates/ops_workload_report.md)
> **主な保管先**: `ops_worklog.jsonl`, `reports/ops/workload/`, `reports/validation_log/`

## 目的
- Ops作業時間・Runbook参照・健康状態を正規化し、月次ワークロードレポートと日次アジェンダへ反映する。
- `ops_worklog.jsonl`の完全性を担保し、改ざん検知用ハッシュとValidation Data Playbook証跡をセットで管理する。

## トリガー
- Ops/PO/DocOpsがRunbookタスクを実行した直後（5分以内）。
- 日次アジェンダ生成 (`RUN-OPS-AGENDA-01`) およびOpsレビュー会議の前後。

## 記録手順
1. CLIで記録: `tradectl ops log add --task <name> --duration <minutes> --notes "RUN-<ID>#<step>" --mode <profile> --health-state <status> --board-mode <mode>`。
   - `--artifact`がある場合は`reports/`配下のMarkdownまたはCSVパスを指定し、ハッシュが自動計算されるか確認。
2. 記録後にCLI出力内の`hash`を控え、`ops_worklog.jsonl`末尾に新規エントリが追加されたことを`tail -n 5 ops_worklog.jsonl`で確認。
3. `sha256sum ops_worklog.jsonl > reports/ops/workload/ops_worklog_<YYYYMMDD>.sha256`を作成し、Ops Managerが署名（イニシャル）を追記。
4. `tradectl ops log list --window 1d --summary`で日次集計を取得し、`reports/ops/workload/<YYYYMM>.md`作成時の差分確認に備えて保存。

## 検証・承認
| ステップ | ロール | 検証項目 |
| --- | --- | --- |
| エントリ入力 | 作業担当者 | CLI戻り値`RecordResult`が`status=ok`、Runbook参照を`notes`に含める |
| ハッシュ確認 | Ops Manager | `ops_worklog.jsonl`のSHA256が`reports/ops/workload/ops_worklog_<YYYYMMDD>.sha256`と一致 |
| 月次レビュー | PO | `reports/ops/workload/<YYYYMM>.md`に最新集計が反映されているか確認し、Automation候補にコメント |

## Validation & レポート連携
- Validation: `reports/validation_log/AC-51_ops_<YYYYMMDD>.md`へCLIコマンド、RecordResult、SHA256を貼付。
- レポート: 月次サイクルで[docs/templates/ops_workload_report.md](../templates/ops_workload_report.md)を使用し、`reports/ops/workload/<YYYYMM>.md`へ反映。
- アジェンダ: 日次アジェンダ生成時に最新ワークログを参照するため、`RUN-OPS-AGENDA-01`から本Runbookを引用。

## インシデント/改ざん検出時の対応
1. ハッシュ不一致を検知した場合は`tradectl ops log list --window 7d --json`で差分を抽出し、`reports/ops/workload/ops_worklog_diff_<timestamp>.json`として保存。
2. `AuditWriter`イベントを`grep 'ops_worklog' logs/audit/*.jsonl`で確認し、欠損があれば`RUN-INC-01`へエスカレーション。
3. 必要に応じて`ops_worklog.jsonl`をリストアし、再度ハッシュを計算。再発防止策は`automation_effect.jsonl`へ記録。

## 関連リンク
- [reports/ops/workload/README.md](../../reports/ops/workload/README.md)
- [RUN-OPS-AGENDA-01](RUN-OPS-AGENDA-01.md)
- [Validation Playbook テンプレ](../../reports/validation_log/templates/playbook_entry.md)
- [Validation Data Playbook Index](../validation_playbook/index.md)
