# Release Readiness Checklist (詳細設計 §30.3/§30.4 対応)

Release ReadinessスコアカードのGate項目を運用でダブルチェックするための統合チェックリスト。[RUN-OPS-05](docs/runbooks/RUN-OPS-05.md)および[RUN-REL-01](docs/runbooks/RUN-REL-01.md)と併用し、Evidence Pointer・ChangeLedger記録を欠かさず更新する。CLIコマンドは詳細設計 §25.5 / §30.5 の仕様に準拠する。

| Gate ID | Checklist Item | CLI Validation (参照コマンド) | Evidence Pointer欄 | ChangeLedgerリンク |
| --- | --- | --- | --- | --- |
| `Gate-QA-Completion` | QA-01〜QA-05が全て`pass`または承認済み例外になっているか。 | `tradectl release readiness --scope <scope> --include-evidence`<br>`tradectl release checklist --profile <profile> --diff` | Evidence: ____________________<br>EG ID: ____________________ | CL-`release_checklist`: ____________________ |
| `Gate-AD-Clearance` | 直近30日の`DegradationEpisode`に`pending_followups`が無いか。 | `tradectl release readiness --scope <scope> --include-evidence`<br>`tradectl release simulate --with-ad --dry-run` (必要時) | Evidence: ____________________<br>EG ID: ____________________ | CL-`ad_followup`: ____________________ |
| `Gate-Delivery-Alerts` | `severity>='major'`のDeliveryAlertが残っていないか。 | `tradectl delivery alerts --severity major --export`<br>`tradectl release readiness --include-evidence` | Evidence: ____________________<br>EG ID: ____________________ | CL-`delivery_alert_review`: ____________________ |
| `Gate-OPS-MTTR` | Guard復旧`MTTR`がWarn/No-Go閾値内か。 | `tradectl delivery forecast --include-degradation`<br>`tradectl release readiness --include-evidence` | Evidence: ____________________<br>EG ID: ____________________ | CL-`delivery_snapshot`: ____________________ |
| `Gate-DATA-SLA` | `data_ingestion_sla_p95`が閾値内 (`<=24` Warn, `<=30` No-Go)。 | `tradectl delivery forecast --include-degradation`<br>`tradectl release readiness` (`metrics`セクション) | Evidence: ____________________<br>EG ID: ____________________ | CL-`data_sla`: ____________________ |
| `Gate-KPI-Sharpe` | `Sharpe_recent` (90d) が`>=0.85` (Warn) / `>=0.80` (No-Go) を満たすか。 | `tradectl release readiness --include-evidence`<br>`tradectl delivery export --window 7d` | Evidence: ____________________<br>EG ID: ____________________ | CL-`strategy_kpi`: ____________________ |
| `Gate-FEEDBACK-Latency` | `avg_time_to_decision`/`reject_rate`が基準内 (`<90s`/`<=0.52`, Fail `>=120s`/`>0.55`)。 | `tradectl release readiness --include-evidence`<br>`tradectl feedback summarize --window 7d` | Evidence: ____________________<br>EG ID: ____________________ | CL-`feedback`: ____________________ |
| `Gate-Checklist-Completion` | チェックリスト完了率`>=0.95`（Fail閾値`>=0.9`未満でNo-Go）。 | `tradectl release checklist --profile <profile> --diff`<br>`tradectl release checklist --profile <profile> --update-status` | Evidence: ____________________<br>EG ID: ____________________ | CL-`release_checklist`: ____________________ |
| `Gate-Manual-Capacity` (補助) | `expected_manual_minutes<120`か。閾値超過時はOps要員を追加。 | `tradectl delivery forecast --include-degradation` | Evidence: ____________________<br>EG ID: ____________________ | CL-`manual_capacity`: ____________________ |

## 運用メモ
- 上表は[RUN-REL-01](docs/runbooks/RUN-REL-01.md)手順3〜7で逐次更新する。空欄が残った場合はその場で担当者を割り当て、完了期限と証跡ファイル名をRunbookチケットに記録する。
- Evidence Pointerは`reports/release/readiness/<YYYYMMDD>/`および`reports/delivery/control_tower/<YYYYMMDD>/`配下のMarkdown/JSONを基本とし、Evidence Graph ID（`EG-...`）を併記する。
- ChangeLedgerリンクは該当カテゴリ（例: `release`, `delivery_snapshot`, `ad_followup`等）のエントリURLまたはIDを記入する。未登録の場合はRunbook完了前に記録を作成する。
- Gate基準や列の追加・削除を行った場合は[RUN-REL-01](docs/runbooks/RUN-REL-01.md)と詳細設計 §30.3/§30.4を同時に更新し、`ChangeLedger.category='release_policy'`で改訂履歴を残す。
