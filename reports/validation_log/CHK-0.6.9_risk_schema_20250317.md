# CHK-0.6.9 Risk Schema Evidence — 2025-03-17

| Target | Schema | Command | Result | Notes |
| --- | --- | --- | --- | --- |
| `config/risk_policy.yaml` | `docs/schemas/risk_policy.schema.json` | `poetry run schema-validate config/risk_policy.yaml --schema docs/schemas/risk_policy.schema.json` | ✅ Success（exit 0） | Matches GateState構造（`market.news.blocked`, `risk.reduce_only`, `human.double_entry_required`） |
| `config/risk_live_guard.yaml` | `docs/schemas/risk_live_guard.schema.json` | `poetry run schema-validate config/risk_live_guard.yaml --schema docs/schemas/risk_live_guard.schema.json` | ✅ Success（exit 0） | Window/閾値が §3.5 GateState と整合 |

## Session Details
- Execution date: 2025-03-17 JST
- Operator: Ops Manager
- Python: 3.12.12 (`poetry env info --path` → `/Users/izumimotohayato/Library/Caches/pypoetry/virtualenvs/fx-toushi-pxo710jy-py3.12`)
- Related design refs: `detailed_design_fx_signal_tool_v1.md` §0.6.9-4, §3.5.4, §4.4, GateState表

## Follow-up
- Evidence linked from Ops Agenda `docs/runbooks/daily_agenda/2025-03-17.md`（Opening Checks、CHK-0.6.9-4）
- Codex Issueテンプレートの `CHK-0.6.9-4` 欄には本ファイルを貼り付けること

## 2025-03-17 スキーマ再検証ログ
| Target | Schema | Command | Timestamp (JST) | Result |
| --- | --- | --- | --- | --- |
| `config/` バンドル | `docs/schemas/config_bundle.schema.json` | `poetry run schema-validate config --schema docs/schemas/config_bundle.schema.json` | 13:48 | ✅ Exit 0 |
| `config/scoring.yaml` | `docs/schemas/scoring_config.schema.json` | `poetry run schema-validate config/scoring.yaml --schema docs/schemas/scoring_config.schema.json` | 13:49 | ✅ Exit 0 |
| `config/risk_live_guard.yaml` | `docs/schemas/risk_live_guard.schema.json` | `poetry run schema-validate config/risk_live_guard.yaml --schema docs/schemas/risk_live_guard.schema.json` | 13:50 | ✅ Exit 0 |
| `config/scoreboard.yaml` | `docs/schemas/scoreboard.schema.json` | `poetry run schema-validate config/scoreboard.yaml --schema docs/schemas/scoreboard.schema.json` | 13:50 | ✅ Exit 0 |
| `config/ops_readiness.yaml` | `docs/schemas/ops_readiness.schema.json` | `poetry run schema-validate config/ops_readiness.yaml --schema docs/schemas/ops_readiness.schema.json` | 13:51 | ✅ Exit 0 |

各コマンドの出力ログは`reports/validation_log/CHK-0.6.9_risk_schema_20250317.md`に集約し、Ops AgendaとCodex Issueから参照する。GateState/Feature Flag更新時は本節を再実行し、タイムスタンプ列を追記すること。
