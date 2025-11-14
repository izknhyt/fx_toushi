# Knowledge Packs Operations Guide

- 最終更新日: 2025-03-05
- 運用責任: Opsリード / Knowledge Curator
- 対応詳細設計: §16, §22, §23, §92

## 1. 目的
- Acceptable DegradationやOps演習の知見を再利用可能な形で整理する。
- Evidence Graph、Release Readiness、Delivery Control Towerで参照できる命名規約とディレクトリ構成を定義する。

## 2. ディレクトリ構成
```
docs/knowledge_packs/
├── README.md                          # 本ガイド
├── acceptable_degradation/
│   ├── case_<YYYYMMDD>.md              # 個別ケース（テンプレ §3）
│   ├── metrics_snapshot_<id>.json      # メトリクス抽出
│   ├── prompt_context_<scenario>.md    # Codex向け文脈
│   ├── prompt_template.md              # Codex向けテンプレ（任意）
│   ├── checklist.yaml                  # 更新チェックリスト
│   └── index.json                      # ケースメタデータ
├── training/
│   └── case_<YYYYMMDD>.md              # GameEngine演習記録
└── archive/
    └── <YYYY>/...                      # アーカイブ済みケース
```

> **Note:** `acceptable_degradation/` 配下はM1 Coreで必須。その他のカテゴリは必要に応じて作成する。

## 3. ケースファイルテンプレ
`acceptable_degradation/case_<YYYYMMDD>.md` には以下を記載する。

```markdown
# Case <YYYYMMDD> - <slug>
- 作成日: <date>
- board_mode: normal|guarded|halted
- scenario_refs: ["OPS-DEG-01", "RISK-KS-05"]
- impact_score: 1-5
- recurrence: rare|occasional|frequent
- related_runbooks: ["RUN-DATA-05#guarded", "RUN-RISK-01#kill_switch"]
- evidence:
  - reports/validation_log/AC-45_sla_<date>.md
  - metrics/data_ingestion_sla.jsonl#<line>
  - docs/templates/degradation_report.md
- change_ids: ["change-20250305-ops-001"]

## Timeline
| 時刻 | 操作 | CLI | Runbook | 所要時間 |
| --- | --- | --- | --- | --- |
| 01:20 | Detect latency | `tradectl data health ...` | RUN-DATA-05#detect | 5 |

## Follow-ups
- [ ] Runbook更新（担当: Ops Lead, 2025-03-06）
- [ ] Prompt Bundle追記（担当: Product Owner, 2025-03-07）
```

## 4. 命名規則
| 種別 | 規約 | 例 |
| --- | --- | --- |
| ケースID | `case_<YYYYMMDD>_<slug>` | `case_20250305_data_latency` |
| メトリクススナップショット | `metrics_snapshot_<case_id>.json` | `metrics_snapshot_case_20250305_data_latency.json` |
| Prompt文脈 | `prompt_context_<scenario>.md` | `prompt_context_OPS-DEG-01.md` |
| Evidenceノード | `knowledge_pack/<category>/<case_id>` | `knowledge_pack/acceptable_degradation/case_20250305_data_latency` |

## 5. Evidence Graph連携
- `tradectl evidence link knowledge-pack --category acceptable_degradation --case case_20250305_data_latency`で登録。
- 付与タグ: `['knowledge_pack','degradation','ops_review']`。
- Edge例: `('knowledge_pack/...', 'degradation_episode', 'degradation_episode/<id>')`, `('knowledge_pack/...', 'runbook', 'docs/runbooks/RUN-DATA-05.md')`。
- `index.json` には `impact_score`, `recurrence`, `last_reviewed_at`, `evidence_hashes` を保持する。

## 6. 更新ワークフロー
1. Runbook/演習完了後24時間以内にケースファイルを作成。
2. `checklist.yaml` の全項目（Runbook更新、Change Ledger記録、Evidence Graph登録）を完了し、署名を追記。
3. `ChangeLedger.record_change(category='knowledge_pack', change_id=...)`で記録。
4. `tradectl review degraded --export` で生成したMarkdownに本ケースへのリンクを貼る。
5. Release Readiness評価時に`DegradationEpisodeRef`へケースIDを入力する。

## 7. 監査・棚卸し
- 四半期ごとに`index.json`の`impact_score>=3`ケースを棚卸しし、`docs/ux_feedback.md`と突合。
- アーカイブ基準: 最終更新から180日経過し、`recurrence='rare'`かつ未発生なら`archive/<YYYY>/`へ移動。
- 棚卸し結果は`reports/validation_log/AC-45_sla_<date>.md`へ記録し、Evidence Graphに`audit`タグを追加。

## 8. バージョン履歴
| 版 | 日付 | 概要 |
| --- | --- | --- |
| v1.0 | 2025-03-05 | 初版。詳細設計§16/§23の命名規則を明文化。 |

---

テンプレ更新時は`docs/templates/degradation_report.md`と整合すること。差異が生じた場合は§92のEvidence/Runbookトレーサビリティ表を同時更新する。
