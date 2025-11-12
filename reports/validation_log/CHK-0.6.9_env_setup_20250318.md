# CHK-0.6.9 Environment Setup Evidence — 2025-03-18

| Item | Command | Result | Notes |
| --- | --- | --- | --- |
| CHK-0.6.9-1 | `poetry install --no-root` | ✅ Exit 0（No dependency changes） | Poetry 2.2.1 / venv: `/Users/izumimotohayato/Library/Caches/pypoetry/virtualenvs/fx-toushi-pxo710jy-py3.12` |
|  | `poetry run python -m tradectl --help` | ✅ Exit 0 | Typer CLI起動画面を確認。 |
| CHK-0.6.9-2 | `poetry run pytest -k smoke` | ✅ 39 passed / 1 skipped / 77 deselected（0.68s） | Skip理由: `tests/smoke/test_spread_monitor_protocol.py`はSpread Monitor未配線のため`pytest.skip`。 |
| CHK-0.6.9-8 | `poetry run pytest tests/schema/test_json_schema_validation.py -k smoke` | N/A（covered above） |  | 

## Session Details
- Execution date: 2025-03-18 JST
- Operator: Ops Manager
- Python: 3.12.12 (`poetry env info --path` → `/Users/izumimotohayato/Library/Caches/pypoetry/virtualenvs/fx-toushi-pxo710jy-py3.12`)
- Related design refs: `detailed_design_fx_signal_tool_v1.md` §0.6.8, §0.6.9, §79.1

## Next Actions
- Ops Agenda `docs/runbooks/daily_agenda/2025-03-18.md#1-opening-checks` へ本証跡リンクを記載。
- Codex Issueテンプレ（`docs/templates/codex_issue.md`）のCHK欄に本ファイルを追記。

## CLI Output Snapshot
```
$ poetry install --no-root
Installing dependencies from lock file

No dependencies to install or update

$ poetry run python -m tradectl --help
(…output truncated; Typerヘルプを確認…)

$ poetry run pytest -k smoke
============================= test session starts ==============================
platform darwin -- Python 3.12.12, pytest-8.4.2, pluggy-1.6.0
rootdir: /Users/izumimotohayato/development/codex_invest
configfile: pytest.ini
testpaths: tests
plugins: mock-3.15.1, approvaltests-0.2.4, approvaltests-15.3.2, hypothesis-6.142.4
collected 117 items / 77 deselected / 40 selected

…
================= 39 passed, 1 skipped, 77 deselected in 0.68s =================
```
