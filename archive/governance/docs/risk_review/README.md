# リスクレビュー記録運用ガイド

## 管理情報
- **目的**: Packet導入後のリスクインパクトと暫定対応を時系列で記録し、§11.3のリスクログおよび週次レビューと突合する。
- **更新頻度**: 重要度Highのインシデントは発生当日中、それ以外は週次Opsレビュー（毎週月曜 09:00 JST）までに更新。
- **責任者**: Risk Officer（レビュー記録）、Ops Manager（暫定対応フォロー）、Product Owner（承認と優先度判断）。
- **記録フォーマット**: `docs/risk_review/<YYYYMMDD>_<packet_or_incident>.md`として保存し、過去分は`docs/archive/risk_review/`へ移動する。

## テンプレート
```
# リスクレビュー: <YYYY-MM-DD> <Packet/Incident>
- Packet/Change: <EPxx-Py or Incident ID>
- Reviewer: <Risk Officer Name>
- Runbook Reference: <RUN-RISK-xx>
- Related Feature Flags: <flag names or N/A>
- Evidence Folder: reports/risk/<YYYYMMDD>_<slug>/

## 1. 事象サマリ
- 発生トリガー:
- 影響評価 (顧客/運用/KPI):
- 現在のステータス (open/monitoring/closed):

## 2. リスク分析
- 根本原因:
- 制御の有効性 (Strong/Moderate/Weak):
- 未解決のリスク項目 (R-xx 参照):

## 3. 暫定対応と恒久対応
- 暫定対応:
- 恒久対応:
- 所要リードタイム:

## 4. フォローアップ
- チェックリスト:
  - [ ] Runbook改訂 (docs/runbooks/...)
  - [ ] Feature Flag登録/更新 (docs/governance/feature_flag_register.md)
  - [ ] Trader Sign-off取得 (docs/trader_signoff/<id>.md)
  - [ ] Packetテンプレ更新 (legacy: docs/archive/implementation_packets/<YYYYMMDD>_<id>.md)
- 次回レビュー予定日:
- Update履歴:
```

- Evidence Folder内にはスクリーンショット、ログ抜粋、メトリクスCSVを保存し、ファイル名にタイムスタンプを付与する。
- リスクレビュー完了後は`detailed_design_fx_signal_tool_v1.md` §11.3に必要な差分を反映し、改訂が不要な場合でもレビュー結果の要約を`docs/development_plan.md#update-log-utc`へリンクする。
