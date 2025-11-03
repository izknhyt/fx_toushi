ARGS ?=

.PHONY: config-init schema-validate check-ops-readiness

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
