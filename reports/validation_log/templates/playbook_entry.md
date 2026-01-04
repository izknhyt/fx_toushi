---
id: AC-XX-<YYYYMMDD>
requirement: <FR/AC番号>
dataset: <データセット名 or ファイルパス>
hash: <SHA256>
source: <取得元URL/Runbook手順>
owner: <記録者>
reviewer: <サイン者>
due_date: <YYYY-MM-DD>
status: pending | provisional | confirmed
fallback_applied: true | false
fallback_reason: <欠損補完理由>
linked_runbooks:
  - docs/runbooks/RUN-DATA-05.md
  - docs/runbooks/RUN-DATA-06.md
signal_cycle_snapshot: reports/validation_log/evidence/<date>/board_snapshot.json
---

## 0. CLI & Snapshot Evidence（RUN-DATA-05 / RUN-DATA-06）
- [x] `tradectl board --view strategy --save-snapshot ...`実行、`signal_cycle_snapshot`にパスを記録（`RUN-DATA-05 §2`）
- [x] `tradectl status --json`保存（`RUN-DATA-05 §2`）
- [x] `tradectl data health --format json`保存（`RUN-DATA-06 §1`）
- [x] `tradectl data ack --dry-run --provider <provider>`ログ保存（`RUN-DATA-05 §6`）
- [x] 各証跡ファイルのSHA256を下表または検証ログに記載

| Artifact | コマンド / Runbook参照 | 保存パス | SHA256 | 確認者 | 確認日時 |
| --- | --- | --- | --- | --- | --- |
| signal_cycle_snapshot | `tradectl board --view strategy --save-snapshot ...`<br>`RUN-DATA-05 §2` | reports/validation_log/evidence/20251111/board_snapshot.json | 5b997687fb853d0c31408fb9786b3bbb4ad2a6f6d796840a3147de6a1b4e0742 | QL | 2025-11-11 22:00Z |
| status_snapshot | `tradectl status --json`<br>`RUN-DATA-05 §2` | reports/validation_log/evidence/20251111/status_snapshot.json | 9feceab56e517ac9f7e69194e03c02e352c57e83971cd85f27c05bc9fa955ce2 | OM | 2025-11-11 22:01Z |
| data_health_snapshot | `tradectl data health --format json`<br>`RUN-DATA-06 §1` | reports/validation_log/evidence/20251111/data_health_20251111.json | 6e27bb824874ec8246e373cecb3a4161ea60053c0ab7d0a85950323c6dc274d4 | QL | 2025-11-11 22:01Z |
| runbook_ack_log | `tradectl data ack --dry-run --provider ...`<br>`RUN-DATA-05 §6` | reports/validation_log/evidence/20251111/ack_log.txt | d44e578c52eeddc595d89f6a361d49ec877cb423e1bc70d79769906ffe42c421 | OM | 2025-11-11 22:02Z |

## 1. 受け入れ条件
- [ ] データ期間: <例: 2024-01-01〜2024-01-31>
- [ ] 欠損率 ≤ <閾値>
- [ ] 二重入力ハッシュ一致
- [ ] `signal_cycle_snapshot`をEvidenceに保存し、Runbookと整合
- [ ] `tradectl data status --auto-apply --log-stage-eval` の証跡を保存（`RUN-FEATURE-FLAG-01 §5.7`）
- [ ] `tradectl data status --suggest-guarded` の証跡を保存（`RUN-DATA-05 §2`）
- [ ] `tradectl compliance status --json` の証跡を保存（`RUN-RISK-01 §0`）

## 2. 検証ログ
| チェック | 実施者 | 実施日時 | 結果 | 証跡 |
| --- | --- | --- | --- | --- |
| レコード件数検証 |  |  |  |  |
| スキーマ検証 (`tools/validate_schema.py`) |  |  |  |  |
| ハッシュ再計算 (`tradectl data hash`) |  |  |  |  |
| Signal cycle snapshot 整合 |  |  |  | `signal_cycle_snapshot` |
| RateLimit自動適用ログ |  |  |  | `logs/ops/stage_change.log` |
| Guarded提案ログ |  |  |  | `logs/events/health_suggested.jsonl` |
| Risk disclosure 強制 |  |  |  | `logs/audit/risk_consent_*.jsonl` |

## 3. コメント
-

## 4. サインオフ
- 運用者: <署名/日時>
- PO: <署名/日時>
