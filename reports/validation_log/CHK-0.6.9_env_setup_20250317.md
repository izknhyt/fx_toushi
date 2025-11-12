# CHK-0.6.9 Environment Setup Evidence — 2025-03-17

| Item | Command | Result | Notes |
| --- | --- | --- | --- |
| CHK-0.6.9-1 | `poetry install --no-root` | ✅ Success（exit 0, Poetry 2.2.1） | 依存差分なし。仮想環境: `$(poetry env info --path)` |
|  | `poetry run python -m tradectl --help` | ✅ Success（exit 0） | `tradectl`パッケージを追加し、`python -m`経由でもTyper CLIが起動することを確認。 |
| CHK-0.6.9-2 | `poetry run pytest -k smoke` | ✅ 39 passed / 1 skipped / 75 deselected（0.53s, 3.12.12） | Skip理由: `tests/smoke/test_spread_monitor_protocol.py` が未配線スタブのため `pytest.skip`。 |
| Task #4 (§0.6.8) | `poetry run pytest tests/unit/test_broker_adapter_contracts.py` | ✅ 5 passed（0.08s） | `FieldMapping`必須キーと`RATE_LIMIT_SLA`閾値をfixtureと比較し、Broker Adapter契約逸脱がないことを証跡化。 |

## Session Details
- Execution date: 2025-03-17 JST
- Python: 3.12.12 (`poetry env info --path` → `/Users/izumimotohayato/Library/Caches/pypoetry/virtualenvs/fx-toushi-pxo710jy-py3.12`)
- Relevant design refs: `detailed_design_fx_signal_tool_v1.md` §0.6.8, §0.6.9, §79.1

## Next Actions
- `docs/prompt_packages/20250317_codex_kickoff.md` に本証跡パスを添付（Issueテンプレ「前提条件」欄）。
- Ops Agenda（`docs/runbooks/daily_agenda/TEMPLATE.md` → `ModeContext Startup Walkthrough`）へ `CHK-0.6.9-6/7` の実行計画リンクを追記。

## 2025-03-17 追試（Codex依頼対応）
| Command | Timestamp (JST) | Result | Notes |
| --- | --- | --- | --- |
| `poetry install --no-root` | 13:42 | ✅ Exit 0 | ローカル環境差分なし (`poetry` 2.2.1)。 |
| `poetry run python -m tradectl --help` | 13:43 | ✅ Exit 0 | Typer CLIのヘルプ表示を確認。 |
| `poetry run pytest -k smoke` | 13:44 | ✅ 39 passed / 1 skipped / 77 deselected | Spread monitorプロトコルは設計通り`pytest.skip`。 |
| `poetry run pytest -k feature_flags` | 13:45 | ✅ 4 passed / 113 deselected | `config/feature_flags.yaml` の定義とSchemaの乖離なし。 |
| `poetry run pytest tests/unit/test_broker_adapter_contracts.py` | 13:46 | ✅ 5 passed | Broker Adapter契約テスト（§79.1 Task #4）を再確認。 |

※ 最新ログはOps Agenda `docs/runbooks/daily_agenda/2025-03-17.md#1-opening-checks` にも追記済み。Codex Issueでは本表を引用し、追試時間帯を記載すること。
