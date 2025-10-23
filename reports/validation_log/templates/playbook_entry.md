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
linked_runbook: docs/runbooks/RUN-XXXX-YY.md
---

## 1. 受け入れ条件
- [ ] データ期間: <例: 2024-01-01〜2024-01-31>
- [ ] 欠損率 ≤ <閾値>
- [ ] 二重入力ハッシュ一致

## 2. 検証ログ
| チェック | 実施者 | 実施日時 | 結果 | 証跡 |
| --- | --- | --- | --- | --- |
| レコード件数検証 |  |  |  |  |
| スキーマ検証 (`tools/validate_schema.py`) |  |  |  |  |
| ハッシュ再計算 (`tradectl data hash`) |  |  |  |  |

## 3. コメント
-

## 4. サインオフ
- 運用者: <署名/日時>
- PO: <署名/日時>
