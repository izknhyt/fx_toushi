---
id: AC-09-<YYYYMMDD>
requirement: FR-28
runbook: docs/runbooks/RUN-FUND-01.md
fallback_runbook: docs/runbooks/RUN-FUND-02.md
dataset: config/swap_rates.csv
shadow_dataset: reports/funding/swap_rates_shadow.csv
hash: <sha256(config/swap_rates.csv)>
shadow_hash: <sha256(reports/funding/swap_rates_shadow.csv)>
source: Broker portal download + Ops adjustment (see RUN-FUND-01 §1)
ops_owner: <Ops initials>
risk_reviewer: <Risk initials>
po_approver: <PO initials>
due_date: <YYYY-MM-DD>
status: pending | provisional | confirmed
fallback_applied: true | false
fallback_reason: <欠損補完理由 or `n/a`>
linked_validation_playbook: reports/validation_log/templates/playbook_entry.md
---

## 1. 受け入れ条件チェックリスト
- [ ] CSV更新: <YYYY-MM-DD>
- [ ] Ops/Riskダブルエントリ一致 (hash == shadow_hash)
- [ ] `tradectl funding sync` 成功ログ保存
- [ ] `tradectl funding status --json` 保存 (`funding_state.json`と整合)
- [ ] Validation Data Playbookエントリ更新 (`reports/validation_log/AC-09_funding_<date>.md`)
- [ ] `reports/funding/daily_hash_log.md` へハッシュと証跡リンクを追記

## 2. CLI証跡
| コマンド | 実行者 | 実行日時 | 出力保存先 (`evidence/` 推奨) | 出力SHA256 |
| --- | --- | --- | --- | --- |
| `tradectl funding sync --shadow reports/funding/swap_rates_shadow.csv` |  |  |  |  |
| `tradectl funding status --json` |  |  |  |  |

## 3. ファイルハッシュ
| ファイル | パス | SHA256 | 計測者 | 計測日時 |
| --- | --- | --- | --- | --- |
| Main CSV | `config/swap_rates.csv` |  |  |  |
| Shadow CSV | `reports/funding/swap_rates_shadow.csv` |  |  |  |
| `funding_state.json` | `data/state/funding_state.json` |  |  |  |

## 4. コメント
- 

## 5. サインオフ
| 役割 | イニシャル | サイン日時 | 備考 |
| --- | --- | --- | --- |
| Ops (準備) |  |  |  |
| Risk (レビュー) |  |  |  |
| Product Owner (承認) |  |  |  |
