# Feature Flag Register

## 管理情報
- **目的**: プロダクトに導入されるFeature Flagのライフサイクルを可視化し、§5.15および§12.2で定義されたガバナンス手順に基づく承認・ロールバック記録を保持する。
- **更新頻度**: Flagの新設/更新/廃止時に即時、少なくとも週次Opsレビューで差分確認。
- **責任者**: Config Governance担当（定常更新）、Product Owner（有効化承認）、Risk Officer（リスク分類確認）。
- **記録フォーマット**: 下記テーブルに1Flag1行で記入し、詳細は`docs/implementation_packets/<date>_<packet>.md`とRunbook差分にリンクする。

## 登録テンプレート
| Flagキー | 導入日 | Packet/Issue | 目的/KPI | 実装対象 (ファイル/セクション) | 初期値 (Env別) | ロールバック手順 | メトリクス監視 | 最終レビュー |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| risk_disclosure_enforce | 2025-02-20 | EP04-P1 | TraderへRiskDisclosure必須化 | config/profile_live.yaml §5.15 | Live:true / Paper:false | `git checkout -- config/profile_live.yaml` | `metrics/risk_disclosure.jsonl` | 2025-02-21 Ops |

- 新規Flagを追加する際はRunbook更新のPull Requestと紐づけ、承認コメントに`Feature Flag Register updated`を記載する。
- 廃止済みFlagは別セクション「Retired Flags」に移動し、撤去日と削除コミットIDを必ず記録する。
- Flagのレビューサイクルは四半期ごとに実施し、非アクティブFlagが3ヶ月継続した場合は廃止検討を行う。

## Retired Flags
| Flagキー | 廃止日 | 由来Packet | 撤去理由 | 削除コミットID | 代替策 |
| --- | --- | --- | --- | --- | --- |
| <placeholder> | <YYYY-MM-DD> | <EPxx-Py> | <理由> | <commit sha> | <移行先> |
