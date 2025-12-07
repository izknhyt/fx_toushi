# Board Snapshot: hard_stop

- Mode: guarded
- Banner: Kill Switch HARD_STOP
- Guardrails: ks=hard_stop, spread=normal, ro=False, risk_disclosure=signed
- Tickets: 1 (TK-KILL-1)

```
| Ticket ID | Symbol | Action | Qty    | TTL(s) | Entry          | SL/TP           | Guardrails                   | Badges           | Checklist             | RiskDisclosure | Spread | Notes                     |
|-----------|--------|--------|--------|--------|----------------|-----------------|-----------------------------|------------------|-----------------------|----------------|--------|---------------------------|
| TK-KILL-1 | AUDJPY | sell   | 120000 | 300    | market @92.15  | SL=92.6 TP=91.2 | ks=hard_stop(health.halt),  | kill_switch_hard | 1/2 (pending:         | signed         | normal | Manual halt - liquidity   |
|           |        |        |        |        |                | TTL=300         | spread=normal, ro=True       | reduce_only_...  | kill_switch_ack)      |                |        | stress                    |
```
