# CR-20251122-hands-off-auto-execute

- **Background**: detailed_design_fx_signal_tool_v1.md §0.6.14/§4.4.7/§88 でHands-offモード・動的サイジング・ロット階段を定義。実装差分をIssue/Packet化する。
- **Owner**: Dev Lead（実装）、Ops Manager（運用フロー確認）
- **Due**: 2025-11-27
- **Related Runbook/Evidence**: RUN-HITL-01, RUN-RISK-03, RUN-GOV-BOARD-01, metrics/profit_readiness.jsonl, tests to add below

## Tasks
- [ ] GateStateに`auto_execute: bool`を追加し、`docs/schemas/gate_state.sample.json`/`src/core/`系モデルを更新（schema_versionも更新）。
- [ ] TicketBuilder/board CLI/Auditに`auto_execute`を配線し、Guarded/Haltでは必ずfalseにフォールバック。CLI `tradectl board --json`出力を更新。
- [ ] `alpha.profit_loop_enabled`/`alpha.dynamic_sizing`/`alpha.auto_execute` Flagの昇格/降格ロジックを`tradectl ops readiness --profit --verify --require-auto-execute`へ実装し、`ops_worklog`と`metrics/profit_readiness.jsonl`にトグルイベントを書き込む。
- [ ] `config/alpha_profiles.yaml::max_dynamic_adjust_pct`を読み取り、`AlphaFeedbackJob`/`PnLFeedbackLoop`でConviction/size補正を±上限制約付きで適用。`alpha.dynamic_sizing=false`時は補正無効化。
- [ ] `config/risk_policy.yaml::lot_ladder`を実装し、`ExecutionAlphaOverlay`で`board_mode=normal && auto_execute`時のみロット階段を適用。Guarded/Haltでは係数を1.0/0へクリップ。
- [ ] スキーマ/設定: `docs/schemas/alpha_profiles.schema.json`/`risk_policy.schema.json`に新キーを追加し、`config/README.md`の表を同期。`make check-alpha-profiles`ターゲット追加。
- [ ] テスト追加: `tests/unit/test_execution_alpha_overlay.py`（auto_execute/lot_ladder適用とクリップ）、`tests/unit/test_pnl_feedback.py`（動的補正とrollback）、`tests/integration/test_profit_loop_flow.py`（auto_execute on/off経路）、`tests/approval/board/auto_execute_enabled.json`スナップショット。
- [ ] CI連携: `make check-profit-readiness`後に`make check-alpha-profiles`を実行するよう`Makefile`/CIジョブを更新。

## Notes
- Halt/HITL優先: Guarded/Haltでは自動約定を絶対に走らせない。降格時は即座に`auto_execute=false`へ書き戻す。
- Spread/Latency逸脱時は動的補正とロット階段をスキップし、監査ログに`overflow=true`を残す。*** End Patch
