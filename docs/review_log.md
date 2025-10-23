# Review Log

週次・月次・四半期レビューの記録と、コメント欄責務/締切の証跡を管理する。記載内容は週次レポート`reports/weekly/<YYYY-WW>.md`およびOpsアジェンダと双方向に同期する。

## 記録ルール
- **更新タイミング**:
  - 週次レビュー: 毎週月曜 09:00 JST 開催前までに最新週のエントリを作成する。
  - 月次レビュー: 第1営業日夜のレビュー完了後24時間以内。
  - 四半期レビュー: 最終営業週のセッション当日中。
- **記入権限**:
  - Quant Lead: A/Bテスト結果、研究関連のインサイト。
  - Ops Manager: Opsアジェンダ、次週ToDo、Runbookの実行状況。
  - Product Owner: 決裁コメントとKPI評価サイン。
- **差分管理**: 締切後の修正は`Update:`エントリとして追記し、誰がいつ修正したかを明記する。Gitログと併せて監査する。

## 週次レビューエントリ テンプレート
```
### <YYYY-WW> Weekly KPI Review
- Reporter: Ops Manager
- Report Source: reports/weekly/<YYYY-WW>.md (generated <YYYY-MM-DD HH:MM JST>)
- A/Bテスト結果 (Quant Lead, due Sun 18:00 JST)
  - Summary: <必須>
  - Evidence: <link to experiment artifacts>
  - Review Log ID: AB-<YYYY-WW>
- 次週ToDo (Ops Manager, due Mon 08:30 JST)
  - Priority Items: <必須>
  - Linked Runbooks: <RUN-PERF-01 / RUN-RISK-01 / others>
  - Ops Agenda Export: docs/runbooks/daily_agenda/<YYYY-MM-DD>.md
- KPI Sign-off (Product Owner, due Mon 12:00 JST)
  - Decision: <approve / hold / escalate>
  - Notes: <optional>
- Follow-up Tickets
  - [ ] <ticket placeholder>
  - [ ] <ticket placeholder>
```

## 月次・四半期エントリ
- 月次: `### <YYYY-MM> Monthly KPI Review`を見出しにして週次テンプレートの`A/Bテスト結果`欄を「主要改善テーマ」に置き換える。
- 四半期: `### <YYYY-Q> Quarterly KPI Review`としてBacktest/SLA結果、SLAプロファイル更新状況、Runbookサイン記録を追記する。

## Opsアジェンダ連携
1. Ops Managerは`tradectl ops agenda --date <YYYY-MM-DD>`を実行し、生成されたMarkdownを`docs/runbooks/daily_agenda/`へ保存する。
2. 保存したファイルを上記テンプレートの「Ops Agenda Export」にリンクし、ToDo欄と整合させる。
3. Agendaに未完了タスクがあれば次週ToDo欄へ転記し、完了済みタスクはOps Worklogへログする。

## 監査リンク
- 週次コメント締切超過時は`reports/validation_log/AC-45_sla_<date>.md`に遅延理由を記録する。
- 実験結果が承認されなかった場合は`reports/research/m1_baseline/validation_<date>.md`に原因を追記し、次週のレビューでフォローアップする。
