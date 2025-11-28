ARGS ?=

.PHONY: config-init schema-validate check-ops-readiness contract-performance-snapshot check-doc-sync config-evidence verify-config-evidence edge-watch-report check-profit-readiness check-alpha-profiles

config-init:
	@if command -v poetry >/dev/null 2>&1; then \
		poetry run python tools/scripts/config_init.py $(ARGS); \
	else \
		python3 tools/scripts/config_init.py $(ARGS); \
	fi

schema-validate:
	@if command -v poetry >/dev/null 2>&1; then \
		poetry run schema-validate config --schema docs/schemas/config_bundle.schema.json; \
	else \
		PYTHONPATH=src python3 -m src.interfaces.cli.schema_validate config --schema docs/schemas/config_bundle.schema.json; \
	fi

check-ops-readiness:
	@if command -v poetry >/dev/null 2>&1; then \
		poetry run python tools/check_ops_readiness.py $(ARGS); \
	else \
		PYTHONPATH=src python3 tools/check_ops_readiness.py $(ARGS); \
	fi

contract-performance-snapshot:
	@if command -v poetry >/dev/null 2>&1; then \
		poetry run pytest tests/contracts/test_performance_snapshot_schema.py -vv --maxfail=1; \
	else \
		python3 -m pytest tests/contracts/test_performance_snapshot_schema.py -vv --maxfail=1; \
	fi

check-doc-sync:
	@if command -v poetry >/dev/null 2>&1; then \
		poetry run python tools/verify_doc_updates.py $(ARGS); \
	else \
		python3 tools/verify_doc_updates.py $(ARGS); \
	fi

config-evidence:
	@if command -v poetry >/dev/null 2>&1; then \
		poetry run python tools/collect_config_evidence.py $(ARGS); \
	else \
		python3 tools/collect_config_evidence.py $(ARGS); \
	fi

verify-config-evidence:
	@if command -v poetry >/dev/null 2>&1; then \
		poetry run python tools/collect_config_evidence.py --verify-only $(ARGS); \
	else \
		python3 tools/collect_config_evidence.py --verify-only $(ARGS); \
	fi

edge-watch-report:
	@if command -v poetry >/dev/null 2>&1; then \
		poetry run python tools/generate_edge_watch_report.py $(ARGS); \
	else \
		python3 tools/generate_edge_watch_report.py $(ARGS); \
	fi

check-profit-readiness:
	@if command -v poetry >/dev/null 2>&1; then \
		poetry run tradectl ops readiness --profit --verify --json; \
	else \
		PYTHONPATH=src python3 -m src.interfaces.cli.main ops readiness --profit --verify --json; \
	fi

check-alpha-profiles:
	@if command -v poetry >/dev/null 2>&1; then \
		poetry run schema-validate config/alpha_profiles.yaml --schema docs/schemas/alpha_profiles.schema.json; \
	else \
		PYTHONPATH=src python3 -m src.interfaces.cli.schema_validate config/alpha_profiles.yaml --schema docs/schemas/alpha_profiles.schema.json; \
	fi
