# Acceptable Degradation Episode Report Template

- テンプレ更新日: 2025-03-05
- 運用責任: Opsリード（Data/Opsハブ）
- 保存先既定: `reports/ops/degradation/<window>.md`、個別エピソードは`reports/ops/degradation/episode_<id>.md`
- Evidence Graphノード: `degradation_episode/<id>`

## 0. メタデータ
| 項目 | 記入例 | 備考 |
| --- | --- | --- |
| Episode ID | `degrade-20250305-01` | `DegradationEpisode.id`と一致させる |
| 対象期間 | `2025-03-05T01:20Z – 2025-03-05T02:05Z` | UTC。Runbook `RUN-DATA-05`参照 |
| Board Mode推移 | `normal → guarded → normal` | `metrics/cli_perf.jsonl`より |
| Health Reasons | `data_latency_fetch`, `rate_limit_stage_2` | `DegradationEpisode.health_reasons` |
| 主要Runbook | `RUN-DATA-05#guarded`, `RUN-DATA-06#manual_csv` | チェック済みの節番号 |
| Change Ledger | `change-20250305-ops-001` | `ChangeLedger.category='degradation'` |
| Evidence Graph ID | `degradation_episode/degrade-20250305-01` | `tradectl degradation sync-evidence`後に決定 |

## 1. 概要
- 発生検知: `tradectl data health`の遅延検知ログ、関連メトリクス（p95/p99）。
- 影響シンボル: 主要4ペアと遅延秒数。
- 現在の解決状況: resolved|in_progress|pending_followup。

## 2. タイムライン
| 時刻 (UTC) | 操作 | Runbook節 | CLIコマンド | 所要時間 (分) | 証跡 |
| --- | --- | --- | --- | --- | --- |
| 01:20 | Degradation検知 | RUN-DATA-05#detect | `tradectl data health --symbol USDJPY` | 5 | `metrics/data_ingestion_sla.jsonl`抜粋 |
| 01:32 | 手動CSV投入 | RUN-DATA-06#manual_csv | `tradectl data jobs enqueue --task manual_csv ...` | 12 | `logs/ops/manual_csv.log` |
| 01:45 | Guard解除 | RUN-DATA-06#release | `tradectl board guard --release` | 3 | `reports/validation_log/AC-45_sla_20250305.md` |

## 3. 影響指標
| 指標 | 発生前 | 発生中 | 復旧後 | 出典 |
| --- | --- | --- | --- | --- |
| `catch_up_lag_minutes` | 6 | 42 | 9 | `metrics/data_ingestion_sla.jsonl` |
| `rate_limit_stage` | 0 | 2 | 1 | `metrics/rate_limit_window.jsonl` |
| `manual_hours` | 0 | 0.8 | 0.1 | `logs/ops/workload.log` |

## 4. 復旧アクション
- 実施手順: Runbookチェック項目を箇条書きで列挙。
- 未完了項目: `pending_followups`に残る作業と担当者。
- 自動化候補: `DegradationRecommendation`から抽出。

## 5. 監査用添付物
1. `metrics/data_ingestion_sla.jsonl`の該当行とSHA256。
2. `logs/audit/rate_limit.jsonl`のステージ移行ログ。
3. `docs/knowledge_packs/acceptable_degradation/case_<YYYYMMDD>.md`リンク。
4. `docs/templates/degradation_report.md`バージョン（このファイル）のハッシュ。

## 6. Runbook/Release連携
- `RUN-DATA-05`, `RUN-DATA-06`チェックボックスを更新し、署名者・時刻を記入。
- `tradectl release readiness --scope live --include-evidence`実行時、本レポートを`EvidencePointer(kind='runbook')`として参照させる。
- Opsレビュー（§19）へ`ActionItem`としてフォローアップを登録。

## 7. 追跡ログ
| 日付 | 更新者 | 変更概要 | Change Ledger |
| --- | --- | --- | --- |
| 2025-03-05 | Ops Lead | 初版作成 | `change-20250305-ops-001` |
| 2025-03-06 | QA Lead | KPI差分を更新、`mttr_minutes`を追記 | `change-20250306-qa-002` |

## Appendix A: CLI記録
```
tradectl degradation report --window 1d --format markdown --include-evidence
tradectl degradation episode show degrade-20250305-01 --include-actions --format table
```

## Appendix B: Evidence Graph 登録メモ
- `node_id`: `degradation_episode/<id>`
- `edges`: `('degradation_episode/<id>', 'runbook', 'docs/runbooks/RUN-DATA-05.md')`, `('degradation_episode/<id>', 'knowledge_pack', 'docs/knowledge_packs/acceptable_degradation/case_<YYYYMMDD>.md')`
- `qa_tags`: `['degradation','guarded','manual_csv']`

---

テンプレート更新時は`docs/ux_feedback.md`に更新日を記録し、Release ReadinessのEvidenceチェックに影響する場合は§30.4のGate Criterion定義を同時に更新すること。
