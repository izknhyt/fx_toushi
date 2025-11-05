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
- [ ] `tradectl board --view strategy --save-snapshot ...`実行、`signal_cycle_snapshot`にパスを記録（`RUN-DATA-05 §2`）
- [ ] `tradectl status --json`保存（`RUN-DATA-05 §2`）
- [ ] `tradectl data health --format json`保存（`RUN-DATA-06 §1`）
- [ ] `tradectl data ack --dry-run --provider <provider>`ログ保存（`RUN-DATA-05 §6`）
- [ ] 各証跡ファイルのSHA256を下表または検証ログに記載

| Artifact | コマンド / Runbook参照 | 保存パス | SHA256 | 確認者 | 確認日時 |
| --- | --- | --- | --- | --- | --- |
| signal_cycle_snapshot | `tradectl board --view strategy --save-snapshot ...`<br>`RUN-DATA-05 §2` |  |  |  |  |
| status_snapshot | `tradectl status --json`<br>`RUN-DATA-05 §2` |  |  |  |  |
| data_health_snapshot | `tradectl data health --format json`<br>`RUN-DATA-06 §1` |  |  |  |  |
| runbook_ack_log | `tradectl data ack --dry-run --provider ...`<br>`RUN-DATA-05 §6` |  |  |  |  |

## 1. 受け入れ条件
- [ ] データ期間: <例: 2024-01-01〜2024-01-31>
- [ ] 欠損率 ≤ <閾値>
- [ ] 二重入力ハッシュ一致
- [ ] `signal_cycle_snapshot`をEvidenceに保存し、Runbookと整合

## 2. 検証ログ
| チェック | 実施者 | 実施日時 | 結果 | 証跡 |
| --- | --- | --- | --- | --- |
| レコード件数検証 |  |  |  |  |
| スキーマ検証 (`tools/validate_schema.py`) |  |  |  |  |
| ハッシュ再計算 (`tradectl data hash`) |  |  |  |  |
| Signal cycle snapshot 整合 |  |  |  | `signal_cycle_snapshot` |

## 3. コメント
-

## 4. サインオフ
- 運用者: <署名/日時>
- PO: <署名/日時>
