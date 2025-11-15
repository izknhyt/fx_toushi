# RUN-REL-01: Release Readiness Go/No-Goレビュー手順

> **ACカバレッジ**: QA-01〜QA-05, OPS-REL
> **Runbook版数**: v1.0
> **最終更新日**: 2025-03-19
> **最終更新者**: Ops Manager (Doc Maintainer)

## 目的
- Release Readinessスコアカード（詳細設計 §30）を用いて、Backtest/Paper/Live/Hotfix各スコープのリリース可否を一貫した基準で判定する。
- Delivery Control Tower（詳細設計 §25）およびAcceptable Degradation対応Runbookの証跡を再利用し、Gate項目とEvidence Pointerの欠損を防止する。
- ChangeLedgerとEvidence GraphにGo/No-Go判定経緯を残し、監査・再演習時のトレーサビリティを確保する。

## トリガー
- スプリント末のリリースレビュー会議（定例：木曜 16:00）の前日までに1回実施。
- Hotfix/Feature Flag切替など臨時リリースの前、OpsマネージャまたはPOがGo判定を求めたとき。
- [RUN-OPS-05](docs/runbooks/RUN-OPS-05.md)で`severity='critical'`なDeliveryAlertを検知し、Release Readinessへの影響評価が必要になったとき。

## 事前準備
- [RUN-OPS-05](docs/runbooks/RUN-OPS-05.md)の最新記録（`reports/delivery/control_tower/<YYYYMMDD>/`）とChangeLedger IDを取得する。
- [docs/release_checklist.md](docs/release_checklist.md)のGate行をレビュー対象スコープで埋め、未入力のEvidence Pointer欄を確認する。
- Releaseスコープに応じたプロファイル（例: `live-core`, `paper-beta`, `hotfix-default`）を決定し、`reports/release/readiness/`配下に日付フォルダを作成する。
- `make ci-lite`がGREENで、`pytest -k release_readiness`を最新の状態で完了していることを確認する。

## 手順
1. **Readinessスナップショット取得**  
   `tradectl release readiness --scope <scope> --window 7d --format markdown --include-evidence > reports/release/readiness/<YYYYMMDD>/snapshot_<scope>.md`を実行し、スコア・Gate状況・Evidence一覧を取得する。  
   - `status`が`hold`/`no_go`の場合は次ステップで該当Gateを重点確認する。  
   - スナップショットをRunbookチケット（`tickets/runbooks/RUN-REL-01/<YYYYMMDD>_<scope>.md`）に添付する。
2. **Gate別詳細確認**  
   `tradectl release blockers --scope <scope> --severity warn --export --format markdown --out reports/release/readiness/<YYYYMMDD>/blockers_<scope>.md`を実行し、`warn`/`fail` Gateの詳細と推奨アクションを整理する。  
   - `--severity fail`でも再実行し、`no_go`要因を抽出する。  
   - `ChangeLedger.record_change(category='release_blocker_review', ...)`で確認結果を記録する。
3. **チェックリスト整合**  
   `tradectl release checklist --profile <profile> --diff --format markdown > reports/release/readiness/<YYYYMMDD>/checklist_<profile>.md`を実行し、[docs/release_checklist.md](docs/release_checklist.md)との整合を確認する。  
   - 実際の完了状況が更新された場合は`tradectl release checklist --profile <profile> --update-status`で差分を反映し、ChangeLedgerに`category='release_checklist'`として記録する。  
   - Evidence Pointer欄に不足がある場合は対応チームへフォローアップを割り当てる。
4. **Delivery/AD証跡突合**  
   - [RUN-OPS-05](docs/runbooks/RUN-OPS-05.md)で取得した`alerts_major.md`および`forecast.md`のハッシュを[docs/release_checklist.md](docs/release_checklist.md)の`Gate-Delivery-Alerts`, `Gate-OPS-MTTR`, `Gate-DATA-SLA`欄へ記入する。  
   - 直近30日の`DegradationEpisode`に未完了フォローアップがあれば[RUN-DATA-05](docs/runbooks/RUN-DATA-05.md)/[RUN-DATA-06](docs/runbooks/RUN-DATA-06.md)を参照し、Gate `Gate-AD-Clearance`へ状況を追記する。
5. **リリースパック生成**  
   `tradectl release export --scope <scope> --window 7d --include-ci --out reports/release/readiness/<YYYYMMDD>/package_<scope>.md`を実行し、会議配布用のパッケージを生成する。  
   - `EvidencePointer`のリンク切れが無いかチェックし、`reports/release/readiness/<YYYYMMDD>/`内のファイルをEvidence Graphへ登録する。  
   - 必要に応じて`tradectl release export --format json`でJSON版も生成し、CIへ添付する。
6. **シミュレーション（オプション）**  
   `tradectl release simulate --scenario <scenario_id> --with-delivery --with-ad --dry-run > reports/release/readiness/<YYYYMMDD>/simulate_<scenario_id>.md`を実行し、閾値変更や例外承認の影響を評価する。  
   - シミュレーション結果は`ChangeLedger.category='release_simulation'`として記録し、必要であれば`config/release/gates.yaml`更新のCRを起票する。
7. **Go/No-Go判定記録**  
   - レビュー参加者で最終判定（`go`/`hold`/`no_go`）と条件を合意し、Runbookチケットへ記録する。  
   - `ChangeLedger.record_change(category='release', status=<decision>, score=<score>, evidence=[...])`を実行し、エントリIDを[docs/release_checklist.md](docs/release_checklist.md)の`Gate-Checklist-Completion`欄へ追記する。  
   - 決定内容をSlack/メールで共有し、[RUN-OPS-05](docs/runbooks/RUN-OPS-05.md)当番へフィードバックを返す。

## KPI・判定基準メモ
| 指標 / Gate ID | Warn閾値 | Fail/No-Go閾値 | 参照コマンド | フォローアップ |
| --- | --- | --- | --- | --- |
| `score` (`ReleaseDecision.score`) | `<0.75`で注意 | `<0.6`で`hold/no_go`推奨 | `tradectl release readiness` | スコア低下の主要GateをBlockers出力で確認 |
| `Gate-QA-Completion` | QA項目未完了 | `QA-01〜05`の`pending/fail` | `release readiness` / `release checklist` | QAリーダーが完了期限を設定し、ChangeLedgerへ記録 |
| `Gate-AD-Clearance` | `pending_followups`あり | 未解決AD Episodeあり | `release readiness` (`ad_episodes`) | [RUN-DATA-05](docs/runbooks/RUN-DATA-05.md)/[RUN-DATA-06](docs/runbooks/RUN-DATA-06.md)で再確認 |
| `Gate-Delivery-Alerts` | `severity='major'`アラートあり | `severity='critical'`アラートあり | `tradectl delivery alerts --severity major|critical` | Opsが[RUN-OPS-05](docs/runbooks/RUN-OPS-05.md)でエスカレーション |
| `Gate-Checklist-Completion` | `completion_rate<0.95` | `completion_rate<0.9` | `tradectl release checklist --diff` | 各担当がEvidence Pointerを補完 |
| `residual_risk_score` (`ReleaseRiskEstimate`) | `>=40`で警戒 | `>=60`で`hold/no_go` | `tradectl release readiness --include-evidence` | リスク要因をBlockers表へ追記し改善策を割当 |

## 証跡貼付テンプレート
| ステップ | ファイル/リンク | Evidence Pointer摘要 | ハッシュ/バージョン |
| --- | --- | --- | --- |
| 1. Readinessスナップショット | `reports/release/readiness/<YYYYMMDD>/snapshot_<scope>.md` | Evidence Graph ID: `EG-release-snapshot-<scope>-<date>` | `sha256:` |
| 2. Blockers出力 | `reports/release/readiness/<YYYYMMDD>/blockers_<scope>.md` | ChangeLedger ID: `CL-release-blocker-<id>` | `sha256:` |
| 3. チェックリストdiff | `reports/release/readiness/<YYYYMMDD>/checklist_<profile>.md` | ChangeLedger ID: `CL-release-checklist-<id>` | `sha256:` |
| 4. リリースパック | `reports/release/readiness/<YYYYMMDD>/package_<scope>.md` | Evidence Graph ID: `EG-release-package-<scope>-<date>` | `sha256:` |
| 5. シミュレーション | `reports/release/readiness/<YYYYMMDD>/simulate_<scenario_id>.md` | ChangeLedger ID: `CL-release-simulation-<id>` | `sha256:` |
| 6. 決定ログ | `tickets/runbooks/RUN-REL-01/<YYYYMMDD>_<scope>.md` | ChangeLedger ID: `CL-release-decision-<id>` | - |

## 更新手順
- Runbook改訂時は版数・最終更新日を更新し、`reports/governance/runbook_changelog.md`へ追記する。
- [docs/release_checklist.md](docs/release_checklist.md)のテーブル構成やGate項目を変更した場合は本Runbookと同時に更新し、影響する設計書セクション（詳細設計 §30.3/30.4）へリンクを追加する。
- Release関連閾値（`config/release/gates.yaml`等）を変更した場合は`ChangeLedger.category='release_policy'`で記録し、[RUN-OPS-05](docs/runbooks/RUN-OPS-05.md)へも通知する。
