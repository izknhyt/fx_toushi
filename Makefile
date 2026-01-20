ARGS ?=

.PHONY: config-init schema-validate check-ops-readiness contract-performance-snapshot check-doc-sync check-doc-refs check-runbooks check-validation docs docs-serve config-evidence verify-config-evidence edge-watch-report check-profit-readiness check-alpha-profiles check-profit-readiness-hands-off check-profit-readiness-hands-off-all sla-report automation-report
.PHONY: regression-backtest
.PHONY: update-log

config-init:
	@if command -v poetry >/dev/null 2>&1; then \
		poetry run python tools/scripts/config_init.py $(ARGS); \
	else \
		python3 tools/scripts/config_init.py $(ARGS); \
	fi

clean-metrics:
	tools/cleanup_metrics.sh

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

check-doc-refs:
	@if command -v poetry >/dev/null 2>&1; then \
		poetry run python tools/check_doc_refs.py; \
	else \
		python3 tools/check_doc_refs.py; \
	fi

check-runbooks:
	@if command -v poetry >/dev/null 2>&1; then \
		poetry run python tools/check_runbooks.py $(ARGS); \
	else \
		PYTHONPATH=src python3 tools/check_runbooks.py $(ARGS); \
	fi

check-validation:
	@if command -v poetry >/dev/null 2>&1; then \
		poetry run python tools/check_validation_playbook.py $(ARGS); \
	else \
		python3 tools/check_validation_playbook.py $(ARGS); \
	fi

regression-backtest:
	@if command -v poetry >/dev/null 2>&1; then \
		poetry run python -m tools.regression.backtest $(ARGS); \
	else \
		PYTHONPATH=src python3 -m tools.regression.backtest $(ARGS); \
	fi

docs:
	@if command -v poetry >/dev/null 2>&1; then \
		poetry run python tools/docbuild.py build $(ARGS); \
	else \
		PYTHONPATH=src python3 tools/docbuild.py build $(ARGS); \
	fi

docs-serve:
	@if command -v poetry >/dev/null 2>&1; then \
		poetry run python tools/docbuild.py build --serve $(ARGS); \
	else \
		PYTHONPATH=src python3 tools/docbuild.py build --serve $(ARGS); \
	fi

update-log:
	@if [ -z "$(MSG)" ]; then \
		echo "MSG is required. Example: make update-log MSG=\"Did X\""; \
		exit 1; \
	fi
	@if command -v poetry >/dev/null 2>&1; then \
		poetry run python tools/update_log.py "$(MSG)"; \
	else \
		python3 tools/update_log.py "$(MSG)"; \
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

sla-report:
	@if command -v poetry >/dev/null 2>&1; then \
		poetry run python tools/sla_report.py $(ARGS); \
	else \
		python3 tools/sla_report.py $(ARGS); \
	fi

automation-report:
	@if command -v poetry >/dev/null 2>&1; then \
		poetry run python tools/automation_effect_report.py $(ARGS); \
	else \
		python3 tools/automation_effect_report.py $(ARGS); \
	fi

check-profit-readiness:
	@if command -v poetry >/dev/null 2>&1; then \
		poetry run tradectl ops readiness --profit --verify --json $(ARGS); \
	else \
		PYTHONPATH=src python3 -m src.interfaces.cli.main ops readiness --profit --verify --json $(ARGS); \
	fi

check-profit-readiness-hands-off:
	@if command -v poetry >/dev/null 2>&1; then \
		poetry run tradectl ops readiness --profit --verify --require-auto-execute --json $(ARGS); \
	else \
		PYTHONPATH=src python3 -m src.interfaces.cli.main ops readiness --profit --verify --require-auto-execute --json $(ARGS); \
	fi

# Note: Hands-off auto_execute remains default-off. Run `make check-profit-readiness-hands-off`
# before enabling, and ensure CR-20251122 is resolved or explicitly deferred in release notes.

check-profit-readiness-hands-off-all:
	$(MAKE) check-profit-readiness-hands-off ARGS="$(ARGS)"
	$(MAKE) check-alpha-profiles

check-alpha-profiles:
	@if command -v poetry >/dev/null 2>&1; then \
		poetry run schema-validate config/alpha_profiles.yaml --schema docs/schemas/alpha_profiles.schema.json; \
	else \
		PYTHONPATH=src python3 -m src.interfaces.cli.schema_validate config/alpha_profiles.yaml --schema docs/schemas/alpha_profiles.schema.json; \
	fi

report-weekly:
	@if command -v poetry >/dev/null 2>&1; then \
		poetry run tradectl report weekly --json; \
	else \
		PYTHONPATH=src python3 -m src.interfaces.cli.main report weekly --json; \
	fi

gate-persist:
	@if command -v poetry >/dev/null 2>&1; then \
		poetry run python tools/persist_gate_state.py $(ARGS); \
	else \
		PYTHONPATH=src python3 tools/persist_gate_state.py $(ARGS); \
	fi
