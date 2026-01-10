# AC-06 Broker Manual Order & Emergency Stop Validation (2026-01-10)

## Scope
- M3 minimal: manual order path (HITL) and emergency stop evidence.
- Runbook: RUN-EMER-UNWIND-01 (manual unwind checklist).

## Evidence
| Artifact | SHA256 |
| --- | --- |
| src/interfaces/cli/broker.py | b2f7be64aa14826dd9086b46a129dd20dfeed32611e81530f97875be2897d648 |
| src/interfaces/cli/__init__.py | 214cee26f9b8c7f72902ab95356d931f7d7dca5089b3d0816e47b7db7e5180d4 |
| reports/validation_log/evidence/20260110/kill_switch_hard_stop.json | ca5e0718eddd83838109af78a242db2813c257ca6506f9db7a0d950126ddd268 |
| reports/validation_log/evidence/20260110/broker_order_reject.json | b088ba1060b93f10499d8e13029d2675154a205009de68e08f1836649e4982a1 |
| reports/validation_log/evidence/20260110/kill_switch_none.json | 083c90b27387ae9849f54247055660888fa08265516c93473ac9622855d1b0f4 |
| reports/validation_log/evidence/20260110/broker_order_submit.json | 05fe7a39695a15a251b84a0f3f69109b7281a3390a8ff8ca577112c570e2b5b4 |
| reports/validation_log/evidence/20260110/broker_emergency_stop.json | b76aa140f6bffc16ad1ab477c1460f0e3758fb4ace56fee9749ac13bb1fb74e9 |
| reports/audit/manual_unwind_20260110.md | 12b1a7eff977bf20c93f8a6597fbd25f88a6ba59109b8acbbc4baf54585b4923 |
| logs/audit/kill_switch.jsonl | 6831eb1aa9ccef4dbf9edbf13cf9cc426398d7367a023e94286b7aacebbcc266 |
| logs/audit/broker_orders.jsonl | 81cf802fbf74fd24a855841a6d5d3c3db1e33d5a6cdb295bc8999a1a96ad45b2 |
| ops_worklog.jsonl | 867079575e9ca3455b4687da2474c7ae26f69137ca344b41d582f87cec6b779f |
| reports/validation_log/evidence/20260110/pytest_broker_orders.log | af610cc8e890ce63e22765ff30834412f22dc2bb696f1a78eb95b1aa4fe4c4d8 |
| reports/validation_log/evidence/20260110/pytest_audit_ticket_action.log | 93650c865e49452bd0ab21e421ed91e66502ccc92ce5eedaacf11a2a5da81f8d |

## Notes
- Kill switch prevented order submission as expected.
- Manual order submission succeeded after kill switch reset.
- Emergency stop created manual unwind record and ops worklog entry.

## Sign-off
- Ops: hayato 2026-01-10
- Risk: hayato 2026-01-10
- PO: hayato 2026-01-10
