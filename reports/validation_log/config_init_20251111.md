# CONFIG-SCAFF-01 Evidence — 2025-11-11

- Generated: 2025-11-11T23:16:56.944169+09:00

## Config Init (dry-run)
```
skipped config/ops_readiness.yaml (exists)
skipped config/risk_live_guard.yaml (exists)
skipped config/scoreboard.yaml (exists)
skipped config/scoring.yaml (exists)
```

## Config Init (apply)
```
skipped config/ops_readiness.yaml (exists)
skipped config/risk_live_guard.yaml (exists)
skipped config/scoreboard.yaml (exists)
skipped config/scoring.yaml (exists)
```

## Schema Validate
```
[schema-validate] Validation succeeded for /Users/izumimotohayato/development/codex_invest/config against config_bundle.schema.json
Warning: 'schema-validate' is an entry point defined in pyproject.toml, but it's not installed as a script. You may get improper `sys.argv[0]`.

The support to run uninstalled scripts will be removed in a future release.

Run `poetry install` to resolve and get rid of this message.
```

## pytest -k config_schema_smoke
```
============================= test session starts ==============================
platform darwin -- Python 3.12.12, pytest-8.4.2, pluggy-1.6.0
rootdir: /Users/izumimotohayato/development/codex_invest
configfile: pytest.ini
testpaths: tests
plugins: mock-3.15.1, approvaltests-0.2.4, approvaltests-15.3.2, hypothesis-6.142.4
collected 125 items / 106 deselected / 19 selected

tests/schema/test_json_schema_validation.py ...................          [100%]

====================== 19 passed, 106 deselected in 0.52s ======================
```
