# Ops Workload Reports

月次ワークロード集計と付随するハッシュ/差分ログを保存するディレクトリ。

- [詳細設計 §18.3 Opsワークロードレポートテンプレ](../../../detailed_design_fx_signal_tool_v1.md#183-opsワークロードレポートテンプレ-toolsops_workload_reportpy)
- [詳細設計 §52.1 OpsWorklogService](../../../detailed_design_fx_signal_tool_v1.md#521-opsworklogservice-srcopsworklogpy)
- [詳細設計 §52.5 テレメトリ・監査・受入基準](../../../detailed_design_fx_signal_tool_v1.md#525-テレメトリ監査受入基準)
- [docs/templates/ops_workload_report.md](../../../docs/templates/ops_workload_report.md)
- [RUN-OPS-LOG-01](../../../docs/runbooks/RUN-OPS-LOG-01.md)

## 保管ルール
- レポート: `reports/ops/workload/<YYYYMM>.md` を[docs/templates/ops_workload_report.md](../../../docs/templates/ops_workload_report.md)から生成。
- メトリクス: `metrics/ops_workload.json`のスナップショットハッシュを`ops_worklog_<YYYYMMDD>.sha256`と同一ディレクトリへ保存。
- 変更履歴: 自動化施策などのコメントはMarkdown末尾の`Runbook Notes`セクションでトラッキング。
- Validation: `reports/validation_log/AC-51_ops_<YYYYMM>.md`で本ディレクトリのレポートとハッシュを参照。

## 推奨ファイル構成
```
reports/ops/workload/
  ├── 202502.md
  ├── metrics_ops_workload_202502.json  # オプション: 生成時点のコピー
  ├── ops_worklog_20250229.sha256
  └── ops_worklog_diff_20250229.json    # 改ざん検出時の差分
```

Opsレビュー会議やAutomation評価時には、[RUN-OPS-AGENDA-01](../../../docs/runbooks/RUN-OPS-AGENDA-01.md)で参照される日次アジェンダと照合し、フォローアップタスクを更新すること。
