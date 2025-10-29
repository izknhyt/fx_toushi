# Ops Reports Repository

Ops関連のMarkdown/JSON成果物を集約するルートディレクトリ。詳細設計で定義されたOps Agenda/Worklog/Automationトラックの証跡をここに保管する。

- [詳細設計 §52.3 OpsAgendaService](../../detailed_design_fx_signal_tool_v1.md#523-opsagendaservice-srcopsagendapy)
- [詳細設計 §18.3 Opsワークロードレポートテンプレ](../../detailed_design_fx_signal_tool_v1.md#183-opsワークロードレポートテンプレ-toolsops_workload_reportpy)
- [詳細設計 §52.5 テレメトリ・監査・受入基準](../../detailed_design_fx_signal_tool_v1.md#525-テレメトリ監査受入基準)

## ディレクトリ構成
- `daily_agenda/`: `tradectl ops agenda`で生成された日次アジェンダMarkdown/JSON。
- `workload/`: `tradectl ops workload report`と`metrics/ops_workload.json`を根拠とする月次集計、ハッシュ、差分ログ。
- その他のOps証跡（例: `automation_effect`レポート）は将来的にサブディレクトリを追加し、本READMEへ追記する。

各サブディレクトリはValidation Data Playbook `AC-51`とリンクし、[RUN-OPS-AGENDA-01](../../docs/runbooks/RUN-OPS-AGENDA-01.md)および[RUN-OPS-LOG-01](../../docs/runbooks/RUN-OPS-LOG-01.md)で参照される。
