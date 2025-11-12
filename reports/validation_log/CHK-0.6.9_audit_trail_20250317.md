# CHK-0.6.9 Audit Trail Evidence — 2025-03-17

| Artifact | Location | Description |
| --- | --- | --- |
| Audit log hub README | `logs/audit/README.md` | 定義済みRunbook（RUN-REC-02 / RUN-AUD-02 / RUN-ACC-01 / RUN-FUND-02）から参照する監査ログ集約ディレクトリの命名規約と保持方針を記載。 |
| Validation linkage | `reports/validation_log/AC-09_funding_20250317.md`, `reports/validation_log/AC-45_sla_20250220.md` | 監査証跡をValidation Data Playbook形式で残し、`logs/audit/`へのリンクをテンプレに記載。 |
| Ops Agenda reference | `docs/runbooks/daily_agenda/2025-03-17.md` | Opening Checks完了後、CHK-0.6.9-8を監査ログパス（`logs/audit/`) に集約する仕組みを説明。 |

## 手順サマリ
1. `logs/audit/README.md` を新設し、対象ドメインごとのログファイル命名規則・保存方針を明文化。
2. Funding Validation（AC-09）やSLA違反（AC-45）といった監査系Validation Logから `logs/audit/` を参照できるよう、該当ファイルに説明を追記。
3. Ops Agenda（2025-03-17）でCHK-0.6.9-8をPassに更新し、監査ログの保存先とValidation Logをクロスリンク。

## Notes
- Runbook `RUN-FUND-02` と `RUN-REC-02` から `logs/audit/` への参照を順次追加する予定。
- 今後の監査イベントは `logs/audit/<domain>_<timestamp>.jsonl` 形式で保存し、Validation Logから必ずハッシュとRunbook IDを参照する。
