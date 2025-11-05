# Validation Data Playbook Evidence Template

Codex／Opsが`reports/validation_log/AC-XX_<date>.md`を更新するときに参照する共通テンプレート。§0.6.11および§7.6で要求されたRunbook連携・CLI証跡の貼付欄を明示し、`RUN-DATA-05`（データ遅延対応）と`RUN-DATA-06`（手動補填・Resync）の整合を担保する。

## 0. CLI & Snapshot Evidence（§7.6 必須）
- [ ] `signal_cycle_snapshot`: `tradectl board --view strategy --save-snapshot reports/validation_log/evidence/<date>/board_snapshot.json`
- [ ] `status_snapshot`: `tradectl status --json > reports/validation_log/evidence/<date>/status.json`
- [ ] `data_health_snapshot`: `tradectl data health --format json --out reports/validation_log/evidence/<date>/data_health.json`
- [ ] `runbook_ack_log`: `tradectl data ack --dry-run --provider <provider> --save reports/validation_log/evidence/<date>/ack.log`
- [ ] `linked_runbooks`欄に`docs/runbooks/RUN-DATA-05.md`と`docs/runbooks/RUN-DATA-06.md`を記載し、証跡にハイパーリンクを残した
- [ ] EvidenceファイルのSHA256と保存先を「検証ログ」テーブルに追記した

| Artifact | コマンド／Runbook参照 | 保存パス | SHA256 | 確認者 | 確認日時 |
| --- | --- | --- | --- | --- | --- |
| signal_cycle_snapshot | `tradectl board --view strategy --save-snapshot ...`<br>Runbook: `RUN-DATA-05 §2` |  |  |  |  |
| status_snapshot | `tradectl status --json`<br>Runbook: `RUN-DATA-05 §2` |  |  |  |  |
| data_health_snapshot | `tradectl data health --format json`<br>Runbook: `RUN-DATA-06 §1` |  |  |  |  |
| runbook_ack_log | `tradectl data ack --dry-run --provider ...`<br>Runbook: `RUN-DATA-05 §6` |  |  |  |  |

## 1. メタデータ（PlaybookエントリFront Matter）
```
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
fallback_reason: <欠損補完理由 or `n/a`>
linked_runbooks:
  - docs/runbooks/RUN-DATA-05.md
  - docs/runbooks/RUN-DATA-06.md
signal_cycle_snapshot: reports/validation_log/evidence/<date>/board_snapshot.json
---
```
- `linked_runbooks`は手順変更時にもRunbook版数を突合できるよう複数指定可能。
- `signal_cycle_snapshot`は`reports/validation_log/templates/playbook_entry.md`と同じキーで保持する。

## 2. 受け入れ条件チェックリスト
- [ ] Runbook `RUN-DATA-05` §2のSignal Guard手順を完了し、CLIスナップショットを保存した
- [ ] Runbook `RUN-DATA-06` §2の手動補填チェックリストを完了し、`tradectl data verify`ログを添付した
- [ ] `tradectl data hash`結果と記録中の`hash`フィールドが一致した
- [ ] `fallback_applied=true`の場合、代替ソース導入と復旧条件をコメント欄に記載した
- [ ] Validation Data Playbook台帳（`docs/validation_playbook/index.md`）の該当行にRunbook版数と証跡URLを転記した

## 3. 検証ログ
| チェック | コマンド／Runbook参照 | 実施者 | 実施日時 | 結果 | 証跡パス／SHA256 |
| --- | --- | --- | --- | --- | --- |
| レコード件数検証 | `tradectl data health --format json`<br>`RUN-DATA-06 §1` |  |  |  |  |
| スキーマ検証 | `tools/validate_schema.py`<br>`RUN-DATA-06 §2` |  |  |  |  |
| ハッシュ再計算 | `tradectl data hash --path <dataset>` |  |  |  |  |
| signal_cycle_snapshot チェック | `tradectl board --view strategy --save-snapshot ...`<br>`RUN-DATA-05 §2` |  |  |  |  |
| Fallback完了ログ | `tradectl data jobs --pending` / `tradectl data ack`<br>`RUN-DATA-05 §3-6` |  |  |  |  |

## 4. コメント
- Ops所見:
- Risk所見:
- Trader所見:

## 5. サインオフ
| 役割 | イニシャル | サイン日時 | 備考 |
| --- | --- | --- | --- |
| Ops (準備) |  |  |  |
| Risk (レビュー) |  |  |  |
| Product Owner (承認) |  |  |  |

## 6. 更新履歴
- 2025-03-24: `DOC-RUNBOOK-ALIGN-02` 対応。`signal_cycle_snapshot`欄とRunbookリンク（`RUN-DATA-05`, `RUN-DATA-06`）を追加。
