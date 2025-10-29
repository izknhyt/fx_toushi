# Daily Ops Agenda Archive

`tradectl ops agenda`で生成する日次アジェンダとJSONエクスポートを格納するディレクトリ。

- [詳細設計 §52.3 OpsAgendaService](../../../detailed_design_fx_signal_tool_v1.md#523-opsagendaservice-srcopsagendapy)
- [詳細設計 §52.5 テレメトリ・監査・受入基準](../../../detailed_design_fx_signal_tool_v1.md#525-テレメトリ監査受入基準)
- [docs/templates/daily_agenda.md](../../../docs/templates/daily_agenda.md)
- [RUN-OPS-AGENDA-01](../../../docs/runbooks/RUN-OPS-AGENDA-01.md)

## 保管ルール
- ファイル形式: `reports/ops/daily_agenda/<YYYY-MM-DD>.md` と `agenda_<YYYY-MM-DD>.json`。
- 承認: Markdown末尾にOps Manager/POの署名欄を設け、Runbookに沿ってダブルサインを取得する。
- Validation: `reports/validation_log/AC-51_ops_<YYYYMMDD>.md`から本ディレクトリ内のファイルへリンクし、CLI出力ハッシュを残す。
- Worklog連携: 記録後に`tradectl ops log add --task agenda_generation ...`で所要時間を`ops_worklog.jsonl`へ追記。

## フォルダ構成例
```
reports/ops/daily_agenda/
  ├── 2025-03-03.md
  ├── agenda_2025-03-03.json
  └── ops_agenda_signoff_20250303.png  # オプション: 署名スクリーンショット
```

Evidence不足時は`RUN-OPS-AGENDA-01`の「記録と証跡」節を参照し、必要な追記を行うこと。
