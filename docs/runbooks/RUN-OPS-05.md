# RUN-OPS-05: Delivery Control Tower ステータスレビュー

> **ACカバレッジ**: QA-03, QA-05, OPS-DEL
> **Runbook版数**: v1.0
> **最終更新日**: 2025-03-19
> **最終更新者**: Ops Manager (Doc Maintainer)

## 目的
- Codexデリバリーコントロールタワー（詳細設計 §25）の最新スナップショットとアラートを日次で確認し、開発進捗・品質シグナル・Ops影響を共有する。
- Release Readinessスコアカード（詳細設計 §30）へ連携する証跡（DeliveryAlert、OpsImpactEstimate、Prompt Gap）を整理し、Go/No-Go判定で再利用可能にする。
- ChangeLedger記録、Evidence Graph、Prompt Bundleへの貼り付けを定型化し、監査・再現性を担保する。

## トリガー
- 平日デイリースタンドアップ（朝会）開始30分前。
- `tradectl delivery status --include-alerts`で`severity='major'`以上のアラートを検知したとき。
- Release Readiness演習（[RUN-REL-01](docs/runbooks/RUN-REL-01.md)）の事前準備としてOpsチームから依頼があったとき。

## 事前準備
- `make ci-lite`が直近実行済みで、Delivery/Release関連テストが最新であること。
- [docs/release_checklist.md](docs/release_checklist.md)のGate欄を最新化し、前回レビュー時の証跡ハッシュを確認しておく。
- `reports/delivery/control_tower/`配下に当日フォルダ（`<YYYYMMDD>/`）を作成し、CLI出力を保存する準備をする。

## 手順
1. **スナップショット取得**  
   `tradectl delivery status --window 7d --include-alerts --format markdown > reports/delivery/control_tower/<YYYYMMDD>/status.md`を実行し、`DeliverySnapshot`のテーブルとアラート一覧を取得する。  
   - `WorkPackageStatus`の`status`が`blocked`の場合は関連アラートIDをメモし、次ステップで優先調査する。  
   - 取得したMarkdownをRunbookチケット（`tickets/runbooks/RUN-OPS-05/<YYYYMMDD>.md`）へ貼り付ける。
2. **Ops影響予測の確認**  
   `tradectl delivery forecast --window 7d --include-degradation --format markdown > reports/delivery/control_tower/<YYYYMMDD>/forecast.md`を実行し、`expected_manual_minutes`, `guard_release_eta`, `kpi_at_risk`を確認する。  
   - `expected_manual_minutes>=120`または`guard_release_eta>=30`の場合は`DeliveryAlert.kind in {'manual_capacity_risk','guard_release_delay'}`を抽出し、[RUN-REL-01](docs/runbooks/RUN-REL-01.md)へ引き継ぐ。
3. **重大アラートのエクスポート**  
   `tradectl delivery alerts --severity major --export --format markdown --out reports/delivery/control_tower/<YYYYMMDD>/alerts_major.md`を実行する。必要に応じて`--severity critical`でも再実行する。  
   - エクスポート結果には`related_runbook_steps`が含まれるため、本Runbookの該当手順IDを確認してチェックリストを更新する。  
   - `ChangeLedger.record_change(category='delivery_alert_review', ...)`を実行し、エントリIDをRunbookチケットへ追記する。
4. **Prompt Gapの確認とエクスポート**  
   `tradectl delivery export --window 7d --format markdown --out reports/delivery/control_tower/<YYYYMMDD>/export.md`を実行し、Prompt Bundle向けサマリと不足チェックリストを生成する。  
   - `missing_sections`に`test_plan`が含まれる場合はRelease Readiness側の`Gate-QA-Completion`へ連携するタスクを起票する。  
   - `--push-to-bundle`フラグが必要な場合はOpsマネージャ承認後に追実行し、生成されたPromptファイルをEvidence Pointerとして記録する。
5. **Evidence Graph・ChangeLedger更新**  
   - `EvidenceGraphService.link_artifact`で上記ステップのMarkdown/JSON出力をノード登録する（ノード種別`delivery_snapshot`）。  
   - `ChangeLedger.record_change(category='delivery_snapshot', status='reviewed', evidence=['reports/delivery/control_tower/<YYYYMMDD>/status.md', ...])`を記録し、IDをRunbookチケットと[docs/release_checklist.md](docs/release_checklist.md)のGate欄へ追記する。
6. **Release Readiness連携タスクの確認**  
   - [docs/release_checklist.md](docs/release_checklist.md)の`Gate-Delivery-Alerts`, `Gate-OPS-MTTR`, `Gate-DATA-SLA`の欄に当日出力のリンクとハッシュを記入する。  
   - [RUN-REL-01](docs/runbooks/RUN-REL-01.md)当番にSlack/メールで主要アラートとフォローアップ担当者を共有する。

## KPI・アクションログ
| 指標 | 期待レンジ | 参照元 | 対応アクション |
| --- | --- | --- | --- |
| `guard_release_eta` | `<30`分（Warn）、`<45`分（No-Go回避） | `delivery forecast`出力 (`OpsImpactEstimate.guard_release_eta`) | Warn超過で[RUN-DATA-05](docs/runbooks/RUN-DATA-05.md)確認、No-Goで[RUN-REL-01](docs/runbooks/RUN-REL-01.md)へEscalate |
| `data_ingestion_sla_p95` | `<=24`分（Warn閾値）、`<=30`分（No-Go回避） | `DeliveryAlert.kind='data_sla_drift'`、`delivery forecast`メトリクス | Warnでデータチーム割当、Criticalで[RUN-DATA-05](docs/runbooks/RUN-DATA-05.md)発火 |
| `Sharpe_recent` | `>=0.85`（Warn閾値）、`>=0.80`（No-Go回避） | `delivery export`→`metrics`セクション、Release Readiness `Gate-KPI-Sharpe` | Warnでストラテジーチームへ調整依頼、Criticalで[RUN-REL-01](docs/runbooks/RUN-REL-01.md)Hold提案 |
| `manual_capacity_risk` | `<120`分 | `delivery forecast` (`expected_manual_minutes`) | 120分超過でOPS追加要員を調整しChangeLedgerに記録 |

## 証跡貼付テンプレート
| ステップ | ファイル/リンク | Evidence Pointer摘要 | ハッシュ/バージョン |
| --- | --- | --- | --- |
| 1. スナップショット取得 | `reports/delivery/control_tower/<YYYYMMDD>/status.md` | Evidence Graph ID: `EG-delivery-status-<date>` | `sha256:` |
| 2. Ops影響予測 | `reports/delivery/control_tower/<YYYYMMDD>/forecast.md` | Evidence Graph ID: `EG-delivery-forecast-<date>` | `sha256:` |
| 3. 重大アラート | `reports/delivery/control_tower/<YYYYMMDD>/alerts_major.md` | ChangeLedger ID: `CL-delivery-alert-<id>` | `sha256:` |
| 4. Prompt Gapエクスポート | `reports/delivery/control_tower/<YYYYMMDD>/export.md` | Prompt Bundle: `<bundle_id>` | `sha256:` |
| 5. ChangeLedger記録 | `ChangeLedger: delivery_snapshot` | エントリURL | - |
| 6. Release連携通知 | Slack/メールリンク | 通知スクリーンショット/ログ | - |

## 更新手順
- 本Runbookの改訂時は版数・最終更新日を更新し、`reports/governance/runbook_changelog.md`へ差分を記録する。
- 変更がRelease ReadinessのGateに影響する場合は[docs/release_checklist.md](docs/release_checklist.md)該当列を同時更新し、`ChangeLedger.category='runbook_update'`を記録する。
