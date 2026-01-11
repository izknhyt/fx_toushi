# Design Alignment Backlog

Source: detailed_design_fx_signal_tool_v1.md

| EP ID | Context | Design Ref | Status | Notes |
| --- | --- | --- | --- | --- |
| `EP-01 DataLag Mitigation` | 0.6.3 実装優先度マトリクス（M1） | detailed_design_fx_signal_tool_v1.md:170 | in_progress | SLAログ/手動CSV/Resyncは実装済（`src/data/service.py`, `src/interfaces/cli/data.py`, `src/interfaces/cli/resync.py`）。`FallbackRetryTask`/`ManualCsvReconciler`は実装済（`src/data/fallback.py`, `src/data/manual_csv.py`）。`tools/sla_report.py`/`make sla-report`を追加済（Resync表形式は要補完）。 |
| `EP-02 Strategy Determinism` | 0.6.3 実装優先度マトリクス（M1） | detailed_design_fx_signal_tool_v1.md:171 | done | Feature determinism/registry/replayは実装済（`src/features/pipeline.py`, `src/strategies/registry.py`, `src/interfaces/cli/determinism.py`）。`board_diagnostics` CLIは実装済（`src/interfaces/cli/board_diagnostics.py`）。`metrics/determinism.jsonl`/`metrics/replay_jobs.jsonl`/Diffスナップショットまで整備済み。 |
| `EP-03 Guardrails` | 0.6.3 実装優先度マトリクス（M1） | detailed_design_fx_signal_tool_v1.md:172 | in_progress | Health/Spread/Kill Switchは実装済（`src/core/health.py`, `src/interfaces/cli/status.py`, `src/interfaces/cli/spread.py`）。RiskDisclosure強制/CLI更新は整備済、流動性/ダッシュボード系は未完。 |
| `EP-04 Ticket Clarity` | 0.6.3 実装優先度マトリクス（M1） | detailed_design_fx_signal_tool_v1.md:173 | done | TicketRecord v2/Board/Ticket CLI/Auditは実装済（`src/ticket/models.py`, `src/interfaces/cli/board.py`, `src/persistence/audit.py`）。GUI連携/監査統合テストも追加済。 |
| `EP-05 Weekly Review` | 0.6.3 実装優先度マトリクス（M1） | detailed_design_fx_signal_tool_v1.md:174 | done | 週次レポート/テンプレは実装済（`src/interfaces/cli/report.py`, `src/reporter/templates/weekly_m1_core.md`）。RiskDisclosure/Benchmark統合も完了済。 |
| `EP03-P4` | 22.5 テスト & Codex Packet計画 | detailed_design_fx_signal_tool_v1.md:5508 | done | `RiskDisclosureService`拡張、状態更新/監査/ops_worklog/refresh_from_profileを追加済。 |
| `EP03-P5` | 22.5 テスト & Codex Packet計画 | detailed_design_fx_signal_tool_v1.md:5509 | done | `tradectl compliance`拡張とRiskDisclosureロック/exit code/承認テストを追加済。 |
| `EP05-P2` | 22.5 テスト & Codex Packet計画 | detailed_design_fx_signal_tool_v1.md:5510 | done | DataManifest/Validation Playbook同期のスタブ実装を追加済。 |
| `EP04-P1` | 23.4 テスト & Codex Packet計画 | detailed_design_fx_signal_tool_v1.md:5586 | todo |  |
| `EP04-P2` | 23.4 テスト & Codex Packet計画 | detailed_design_fx_signal_tool_v1.md:5587 | todo |  |
| `EP04-P3` | 23.4 テスト & Codex Packet計画 | detailed_design_fx_signal_tool_v1.md:5588 | done | GUIイベント連携と監査統合テストを追加済。 |
| `EP03-P6` | 24.4 テスト & Codex Packet計画 | detailed_design_fx_signal_tool_v1.md:5648 | todo |  |
| `EP03-P7` | 24.4 テスト & Codex Packet計画 | detailed_design_fx_signal_tool_v1.md:5649 | todo |  |
| `EP03-P8` | 24.4 テスト & Codex Packet計画 | detailed_design_fx_signal_tool_v1.md:5650 | todo |  |
| `EP05-P3` | 25.4 テスト & Codex Packet計画 | detailed_design_fx_signal_tool_v1.md:5707 | done | Statementパーサ/設定テンプレ/単体テストを追加済（`src/reconciliation/statements.py`）。 |
| `EP05-P4` | 25.4 テスト & Codex Packet計画 | detailed_design_fx_signal_tool_v1.md:5708 | done | `tradectl reconcile statements/preview/scaffold`とCLI統合テストを追加済。 |
| `EP05-P5` | 25.4 テスト & Codex Packet計画 | detailed_design_fx_signal_tool_v1.md:5709 | done | Validation Playbook同期（スタブ）を追加済。 |
| `EP06-P1` | 26.4 Codex Packet計画 & テレメトリ | detailed_design_fx_signal_tool_v1.md:5772 | todo |  |
| `EP06-P2` | 26.4 Codex Packet計画 & テレメトリ | detailed_design_fx_signal_tool_v1.md:5773 | todo |  |
| `EP06-P3` | 26.4 Codex Packet計画 & テレメトリ | detailed_design_fx_signal_tool_v1.md:5774 | todo |  |
| `EP04-P1` | 34.4 テスト & Codex Packet | detailed_design_fx_signal_tool_v1.md:6095 | todo |  |
| `EP04-P2` | 34.4 テスト & Codex Packet | detailed_design_fx_signal_tool_v1.md:6096 | todo |  |
| `EP04-P3` | 34.4 テスト & Codex Packet | detailed_design_fx_signal_tool_v1.md:6097 | done | GUIイベント連携/監査統合テストを反映済。 |
| `EP06-P1` | 35.3 テスト & Codex Packet | detailed_design_fx_signal_tool_v1.md:6151 | todo |  |
| `EP06-P2` | 35.3 テスト & Codex Packet | detailed_design_fx_signal_tool_v1.md:6152 | todo |  |
| `EP05-P1` | 36.3 テスト & Codex Packet | detailed_design_fx_signal_tool_v1.md:6201 | todo |  |
| `EP05-P2` | 36.3 テスト & Codex Packet | detailed_design_fx_signal_tool_v1.md:6202 | done | Data manifest CLI/検証フローを追加済。 |
| `EP05-P3` | 36.3 テスト & Codex Packet | detailed_design_fx_signal_tool_v1.md:6203 | done | Statement reconciliation CLI/テストを反映済。 |
| `EP03-P7` | 37.4 テスト & Codex Packet | detailed_design_fx_signal_tool_v1.md:6258 | todo |  |
| `EP03-P8` | 37.4 テスト & Codex Packet | detailed_design_fx_signal_tool_v1.md:6259 | todo |  |
| `EP06-MR-P1` | 46.5 Codex Packet計画（Model Risk Track） | detailed_design_fx_signal_tool_v1.md:6747 | todo |  |
| `EP06-MR-P2` | 46.5 Codex Packet計画（Model Risk Track） | detailed_design_fx_signal_tool_v1.md:6748 | todo |  |
| `EP06-MR-P3` | 46.5 Codex Packet計画（Model Risk Track） | detailed_design_fx_signal_tool_v1.md:6749 | todo |  |
| `EP06-MR-P4` | 46.5 Codex Packet計画（Model Risk Track） | detailed_design_fx_signal_tool_v1.md:6750 | todo |  |
| `EP07-BO-P1` | 47.5 Codex Packet計画（BackOffice/Tax Track） | detailed_design_fx_signal_tool_v1.md:6841 | todo |  |
| `EP07-BO-P2` | 47.5 Codex Packet計画（BackOffice/Tax Track） | detailed_design_fx_signal_tool_v1.md:6842 | todo |  |
| `EP07-BO-P3` | 47.5 Codex Packet計画（BackOffice/Tax Track） | detailed_design_fx_signal_tool_v1.md:6843 | todo |  |
| `EP08-SS-P1` | 48.5 Codex Packet計画（Secure Sharing Track） | detailed_design_fx_signal_tool_v1.md:6914 | todo |  |
| `EP08-SS-P2` | 48.5 Codex Packet計画（Secure Sharing Track） | detailed_design_fx_signal_tool_v1.md:6915 | todo |  |
| `EP08-SS-P3` | 48.5 Codex Packet計画（Secure Sharing Track） | detailed_design_fx_signal_tool_v1.md:6916 | todo |  |
| `EP09-RTF-P1` | 49.4 Codex Packet計画（Real-time Feed Track） | detailed_design_fx_signal_tool_v1.md:6972 | todo |  |
| `EP09-RTF-P2` | 49.4 Codex Packet計画（Real-time Feed Track） | detailed_design_fx_signal_tool_v1.md:6973 | todo |  |
| `EP09-RTF-P3` | 49.4 Codex Packet計画（Real-time Feed Track） | detailed_design_fx_signal_tool_v1.md:6974 | todo |  |
| `EP09-LIC-P1` | 50.3 テスト & Codex Packet計画（Licensing Track） | detailed_design_fx_signal_tool_v1.md:7028 | todo |  |
| `EP09-LIC-P2` | 50.3 テスト & Codex Packet計画（Licensing Track） | detailed_design_fx_signal_tool_v1.md:7029 | todo |  |
| `EP09-LIC-P3` | 50.3 テスト & Codex Packet計画（Licensing Track） | detailed_design_fx_signal_tool_v1.md:7030 | todo |  |
| `EP10-ACC-P1` | 51.6 Codex Packet計画（Multi-Account Track） | detailed_design_fx_signal_tool_v1.md:7132 | todo |  |
| `EP10-ACC-P2` | 51.6 Codex Packet計画（Multi-Account Track） | detailed_design_fx_signal_tool_v1.md:7133 | todo |  |
| `EP10-ACC-P3` | 51.6 Codex Packet計画（Multi-Account Track） | detailed_design_fx_signal_tool_v1.md:7134 | todo |  |
| `EP11-OPS-P1` | 52.6 Codex Packet計画（Ops Automation Track） | detailed_design_fx_signal_tool_v1.md:7259 | todo |  |
| `EP11-OPS-P2` | 52.6 Codex Packet計画（Ops Automation Track） | detailed_design_fx_signal_tool_v1.md:7260 | todo |  |
| `EP11-OPS-P3` | 52.6 Codex Packet計画（Ops Automation Track） | detailed_design_fx_signal_tool_v1.md:7261 | todo |  |
| `EP11-DRILL-P1` | 53.4 テスト・Codex Packet | detailed_design_fx_signal_tool_v1.md:7342 | todo |  |
| `EP11-DRILL-P2` | 53.4 テスト・Codex Packet | detailed_design_fx_signal_tool_v1.md:7343 | todo |  |
| `EP11-DRILL-P3` | 53.4 テスト・Codex Packet | detailed_design_fx_signal_tool_v1.md:7344 | todo |  |
| `EP06-IDEA-P1` | 54.5 テスト戦略とCodex Packet | detailed_design_fx_signal_tool_v1.md:7436 | todo |  |
| `EP06-IDEA-P2` | 54.5 テスト戦略とCodex Packet | detailed_design_fx_signal_tool_v1.md:7437 | todo |  |
| `EP06-IDEA-P3` | 54.5 テスト戦略とCodex Packet | detailed_design_fx_signal_tool_v1.md:7438 | todo |  |
| `EP07-RSCH-P1` | 55.5 Codex Packet計画（Research Workspace Track） | detailed_design_fx_signal_tool_v1.md:7519 | todo |  |
| `EP07-RSCH-P2` | 55.5 Codex Packet計画（Research Workspace Track） | detailed_design_fx_signal_tool_v1.md:7520 | todo |  |
| `EP07-RSCH-P3` | 55.5 Codex Packet計画（Research Workspace Track） | detailed_design_fx_signal_tool_v1.md:7521 | todo |  |
| `EP09-BRD-P1` | 56.5 Codex Packet計画（Strategy Board Track） | detailed_design_fx_signal_tool_v1.md:7587 | todo |  |
| `EP09-BRD-P2` | 56.5 Codex Packet計画（Strategy Board Track） | detailed_design_fx_signal_tool_v1.md:7588 | todo |  |
| `EP09-BRD-P3` | 56.5 Codex Packet計画（Strategy Board Track） | detailed_design_fx_signal_tool_v1.md:7589 | todo |  |
| `EP09-LIFE-P1` | 57.4 テスト・Codex Packet・移行方針 | detailed_design_fx_signal_tool_v1.md:7672 | todo |  |
| `EP09-LIFE-P2` | 57.4 テスト・Codex Packet・移行方針 | detailed_design_fx_signal_tool_v1.md:7673 | todo |  |
| `EP09-LIFE-P3` | 57.4 テスト・Codex Packet・移行方針 | detailed_design_fx_signal_tool_v1.md:7674 | todo |  |
| `EP12-DOC-P1` | 58.5 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:7746 | todo |  |
| `EP12-DOC-P2` | 58.5 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:7747 | todo |  |
| `EP12-DOC-P3` | 58.5 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:7748 | todo |  |
| `EP12-DOC-P4` | 59.3 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:7790 | todo |  |
| `EP12-DOC-P5` | 59.3 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:7791 | todo |  |
| `EP13-SHADOW-P1` | 60.3 テレメトリ・テスト・Codex Packet | detailed_design_fx_signal_tool_v1.md:7869 | todo |  |
| `EP13-SHADOW-P2` | 60.3 テレメトリ・テスト・Codex Packet | detailed_design_fx_signal_tool_v1.md:7870 | todo |  |
| `EP13-SHADOW-P3` | 60.3 テレメトリ・テスト・Codex Packet | detailed_design_fx_signal_tool_v1.md:7871 | todo |  |
| `EP10-COMP-P1` | 61.4 テスト戦略・Codex Packet | detailed_design_fx_signal_tool_v1.md:7960 | todo |  |
| `EP10-COMP-P2` | 61.4 テスト戦略・Codex Packet | detailed_design_fx_signal_tool_v1.md:7961 | todo |  |
| `EP10-COMP-P3` | 61.4 テスト戦略・Codex Packet | detailed_design_fx_signal_tool_v1.md:7962 | todo |  |
| `EP08-EXP-P1` | 62.4 テスト戦略・Codex Packet | detailed_design_fx_signal_tool_v1.md:8032 | todo |  |
| `EP08-EXP-P2` | 62.4 テスト戦略・Codex Packet | detailed_design_fx_signal_tool_v1.md:8033 | todo |  |
| `EP08-EXP-P3` | 62.4 テスト戦略・Codex Packet | detailed_design_fx_signal_tool_v1.md:8034 | todo |  |
| `EP11-INC-P1` | 63.4 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:8102 | todo |  |
| `EP11-INC-P2` | 63.4 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:8103 | todo |  |
| `EP11-INC-P3` | 63.4 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:8104 | todo |  |
| `EP12-STRESS-P1` | 64.3 テレメトリ・監査・Codex Packet | detailed_design_fx_signal_tool_v1.md:8164 | todo |  |
| `EP12-STRESS-P2` | 64.3 テレメトリ・監査・Codex Packet | detailed_design_fx_signal_tool_v1.md:8165 | todo |  |
| `EP12-STRESS-P3` | 64.3 テレメトリ・監査・Codex Packet | detailed_design_fx_signal_tool_v1.md:8166 | todo |  |
| `EP13-COACH-P1` | 65.3 テレメトリ・ダッシュボード統合・Codex Packet | detailed_design_fx_signal_tool_v1.md:8223 | todo |  |
| `EP13-COACH-P2` | 65.3 テレメトリ・ダッシュボード統合・Codex Packet | detailed_design_fx_signal_tool_v1.md:8224 | todo |  |
| `EP13-COACH-P3` | 65.3 テレメトリ・ダッシュボード統合・Codex Packet | detailed_design_fx_signal_tool_v1.md:8225 | todo |  |
| `EP14-DEGRADE-P1` | 66.3 テレメトリ・監査・Codex Packet | detailed_design_fx_signal_tool_v1.md:8278 | todo |  |
| `EP14-DEGRADE-P2` | 66.3 テレメトリ・監査・Codex Packet | detailed_design_fx_signal_tool_v1.md:8279 | todo |  |
| `EP14-DEGRADE-P3` | 66.3 テレメトリ・監査・Codex Packet | detailed_design_fx_signal_tool_v1.md:8280 | todo |  |
| `EP11-RISKCONSENT-P1` | 67.5 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:8357 | todo |  |
| `EP11-RISKCONSENT-P2` | 67.5 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:8358 | todo |  |
| `EP11-RISKCONSENT-P3` | 67.5 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:8359 | todo |  |
| `EP12-PROMO-P1` | 68.4 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:8422 | todo |  |
| `EP12-PROMO-P2` | 68.4 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:8423 | todo |  |
| `EP12-PROMO-P3` | 68.4 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:8424 | todo |  |
| `EP14-SUNSET-P1` | 69.4 テレメトリ・監査・Codex Packet | detailed_design_fx_signal_tool_v1.md:8505 | todo |  |
| `EP14-SUNSET-P2` | 69.4 テレメトリ・監査・Codex Packet | detailed_design_fx_signal_tool_v1.md:8506 | todo |  |
| `EP14-SUNSET-P3` | 69.4 テレメトリ・監査・Codex Packet | detailed_design_fx_signal_tool_v1.md:8507 | todo |  |
| `EP15-ACCESS-P1` | 70.4 Codex Packet・テスト・受入条件 | detailed_design_fx_signal_tool_v1.md:8575 | todo |  |
| `EP15-ACCESS-P2` | 70.4 Codex Packet・テスト・受入条件 | detailed_design_fx_signal_tool_v1.md:8576 | todo |  |
| `EP15-ACCESS-P3` | 70.4 Codex Packet・テスト・受入条件 | detailed_design_fx_signal_tool_v1.md:8577 | todo |  |
| `EP16-REG-P1` | 78.4 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:8738 | todo |  |
| `EP16-REG-P2` | 78.4 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:8739 | todo |  |
| `EP16-REG-P3` | 78.4 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:8740 | todo |  |
| `EP17-BROKER-P1` | 79.4 Runbook・Feature Flag・受入テスト | detailed_design_fx_signal_tool_v1.md:8778 | todo |  |
| `EP17-BROKER-P2` | 79.4 Runbook・Feature Flag・受入テスト | detailed_design_fx_signal_tool_v1.md:8779 | todo |  |
| `EP17-BROKER-P3` | 79.4 Runbook・Feature Flag・受入テスト | detailed_design_fx_signal_tool_v1.md:8780 | todo |  |
| `EP17-BROKER-P4` | 80.6 Codex実装パケット | detailed_design_fx_signal_tool_v1.md:8929 | todo |  |
| `EP17-BROKER-P5` | 80.6 Codex実装パケット | detailed_design_fx_signal_tool_v1.md:8930 | todo |  |
| `EP17-BROKER-P6` | 80.6 Codex実装パケット | detailed_design_fx_signal_tool_v1.md:8931 | todo |  |
| `EP17-BROKER-P7` | 81.6 Codex実装パケット | detailed_design_fx_signal_tool_v1.md:8990 | todo |  |
| `EP17-BROKER-P8` | 81.6 Codex実装パケット | detailed_design_fx_signal_tool_v1.md:8991 | todo |  |
| `EP17-BROKER-P9` | 81.6 Codex実装パケット | detailed_design_fx_signal_tool_v1.md:8992 | todo |  |
| `EP17-BROKER-P10` | 82.5 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:9058 | todo |  |
| `EP17-BROKER-P11` | 82.5 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:9059 | todo |  |
| `EP17-BROKER-P12` | 82.5 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:9060 | todo |  |
| `EP17-BROKER-P13` | 83.5 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:9110 | todo |  |
| `EP17-BROKER-P14` | 83.5 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:9111 | todo |  |
| `EP17-BROKER-P15` | 83.5 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:9112 | todo |  |
| `EP17-BROKER-P16` | 84.6 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:9257 | todo |  |
| `EP17-BROKER-P17` | 84.6 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:9258 | todo |  |
| `EP17-BROKER-P18` | 84.6 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:9259 | todo |  |
| `EP17-BROKER-P19` | 85.4 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:9314 | todo |  |
| `EP17-BROKER-P20` | 85.4 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:9315 | todo |  |
| `EP17-BROKER-P21` | 85.4 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:9316 | todo |  |
| `EP18-GUI-P1` | 86.5 Codex実装パケットとテスト計画 | detailed_design_fx_signal_tool_v1.md:9392 | todo |  |
| `EP18-GUI-P2` | 86.5 Codex実装パケットとテスト計画 | detailed_design_fx_signal_tool_v1.md:9393 | todo |  |
| `EP18-GUI-P3` | 86.5 Codex実装パケットとテスト計画 | detailed_design_fx_signal_tool_v1.md:9394 | todo |  |
| `EP20-SHADOW-GW-P1` | 87.3 Codexテスト指針とFeature Flag運用 | detailed_design_fx_signal_tool_v1.md:9474 | todo |  |
| `EP20-SHADOW-GW-P2` | 87.3 Codexテスト指針とFeature Flag運用 | detailed_design_fx_signal_tool_v1.md:9475 | todo |  |
| `EP20-SHADOW-GW-P3` | 87.3 Codexテスト指針とFeature Flag運用 | detailed_design_fx_signal_tool_v1.md:9476 | todo |  |
| `EP21-ALPHA-P1` | 88.6 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:9624 | todo |  |
| `EP21-ALPHA-P2` | 88.6 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:9625 | todo |  |
| `EP21-ALPHA-P3` | 88.6 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:9626 | todo |  |
| `EP01-P1` | 89.5 Codex Packet & テスト計画（EP01-P1/P2/P3） | detailed_design_fx_signal_tool_v1.md:9706 | done | `FallbackRetryTask`イベント化を実装済（`src/data/fallback.py`, `src/data/service.py`, `tests/unit/test_data_ingestion_delays.py`）。 |
| `EP01-P2` | 89.5 Codex Packet & テスト計画（EP01-P1/P2/P3） | detailed_design_fx_signal_tool_v1.md:9707 | done | `ManualCsvReconciler`/監査ログを実装済（`src/data/manual_csv.py`, `src/interfaces/cli/data.py`, `tests/unit/test_manual_csv_reconciler.py`）。 |
| `EP01-P3` | 89.5 Codex Packet & テスト計画（EP01-P1/P2/P3） | detailed_design_fx_signal_tool_v1.md:9708 | in_progress | Resync CLI/Evidence/`health.suggest_resume`は実装済（`src/interfaces/cli/resync.py`）。`tools/sla_report.py`/`make sla-report`を実装済。Resync進捗テーブルを追加済。 |
| `EP03-P1` | 90.6 Codex Packet & テスト計画（EP03-P1/P2/P3） | detailed_design_fx_signal_tool_v1.md:9864 | done | `HealthMonitor`のアクションキューと監査ログを実装済（`src/core/health.py`, `src/interfaces/cli/status.py`, `tests/unit/test_health_state.py`）。 |
| `EP03-P2` | 90.6 Codex Packet & テスト計画（EP03-P1/P2/P3） | detailed_design_fx_signal_tool_v1.md:9865 | done | Spread/NTP/News統合とCLIを実装済（`src/execution/spread.py`, `src/interfaces/cli/spread.py`, `tests/unit/test_spread_monitor.py`）。 |
| `EP03-P3` | 90.6 Codex Packet & テスト計画（EP03-P1/P2/P3） | detailed_design_fx_signal_tool_v1.md:9866 | done | Kill Switch/Board連携は実装済（`src/interfaces/cli/kill_switch.py`, `src/risk/manager.py`, `tests/cli/test_tradectl_board_kill_switch.py`）。 |
| `EP02-P1` | 91.7 Codex Packet & テスト計画（EP02-P1/P2/P3） | detailed_design_fx_signal_tool_v1.md:9941 | done | Feature determinism/キャッシュキー/バージョニング実装済（`src/features/pipeline.py`, `src/features/cache.py`, `tests/unit/test_feature_pipeline_determinism.py`）。 |
| `EP02-P2` | 91.7 Codex Packet & テスト計画（EP02-P1/P2/P3） | detailed_design_fx_signal_tool_v1.md:9942 | done | `board_diagnostics` CLIを実装済（`src/interfaces/cli/board_diagnostics.py`, `tests/cli/test_board_diagnostics.py`）。 |
| `EP02-P3` | 91.7 Codex Packet & テスト計画（EP02-P1/P2/P3） | detailed_design_fx_signal_tool_v1.md:9943 | done | Execution determinism/Replay CLIは実装済（`src/execution/model.py`, `src/interfaces/cli/determinism.py`）。`metrics/replay_jobs.jsonl`とDiffレポート/JSON/スナップショットまで整備済。 |
| `EP04-P1` | 92.7 Codex Packet & テスト計画（EP04-P1/P2/P3） | detailed_design_fx_signal_tool_v1.md:10064 | done | TicketRecord v2とTicketBuilderは実装済（`src/ticket/models.py`, `src/ticket/builder.py`, `tests/unit/test_ticket_builder.py`）。 |
| `EP04-P2` | 92.7 Codex Packet & テスト計画（EP04-P1/P2/P3） | detailed_design_fx_signal_tool_v1.md:10065 | done | Board/Ticket CLI更新とSnapshotは実装済（`src/interfaces/cli/board.py`, `src/interfaces/cli/tickets.py`, `tests/approval/board/`）。 |
| `EP04-P3` | 92.7 Codex Packet & テスト計画（EP04-P1/P2/P3） | detailed_design_fx_signal_tool_v1.md:10066 | done | Audit Logger + GUI連携の統合テストを追加済。 |
| `EP-00 Config Foundations` | 12.1 Packetバックログ概要 | detailed_design_fx_signal_tool_v1.md:4023 | done | `make config-init`/`schema-validate`/`config/README.md`/`tradectl config ls`整備は完了済。 |
| `EP00-P1` | 12.1 Packetバックログ概要 | detailed_design_fx_signal_tool_v1.md:4023 | done | `make config-init`/`schema-validate`/`config/README.md`/`tradectl config ls`整備は完了済。 |
| `EP01-T1` | 15.1 EP-01 DataLag Mitigation（データSLA） | detailed_design_fx_signal_tool_v1.md:4520 | done | provider優先度のper_symbol override/`FallbackRetryTask`キュー連携/`data.fetch`ログを実装済。 |
| `EP01-T2` | 15.1 EP-01 DataLag Mitigation（データSLA） | detailed_design_fx_signal_tool_v1.md:4521 | done | NTPドリフト・欠損比率評価と`DataLatencyAlert`追加、Manual CSVブロック条件をprimary限定で整備。 |
| `EP01-T3` | 15.1 EP-01 DataLag Mitigation（データSLA） | detailed_design_fx_signal_tool_v1.md:4522 | done | Resync failover report表形式/`health.suggest_resume`連携を実装済。 |
| `EP02-T1` | 15.2 EP-02 Strategy Determinism（シグナル決定論） | detailed_design_fx_signal_tool_v1.md:4533 | done | FeaturePipeline RNG決定論化と`metrics/feature_cache.jsonl`を実装済。 |
| `EP02-T2` | 15.2 EP-02 Strategy Determinism（シグナル決定論） | detailed_design_fx_signal_tool_v1.md:4534 | done | `strategy.determinism`イベント出力と`tradectl board --view diagnostics`対応済。 |
| `EP02-T3` | 15.2 EP-02 Strategy Determinism（シグナル決定論） | detailed_design_fx_signal_tool_v1.md:4535 | done | Human delay三角分布/seed_offset設定とPaper/Live丸めを実装済。 |
| `EP03-T1` | 15.3 EP-03 Guardrails（リスク/ヘルス） | detailed_design_fx_signal_tool_v1.md:4544 | done | Health action監査ログ強化と`auto_ack_required`をkill switch stateへ追加済。 |
| `EP03-T2` | 15.3 EP-03 Guardrails（リスク/ヘルス） | detailed_design_fx_signal_tool_v1.md:4545 | done | `cooldown_reason`と`metrics/network.jsonl`滞留時間ログをSpreadMonitorへ実装済。 |
| `EP03-T3` | 15.3 EP-03 Guardrails（リスク/ヘルス） | detailed_design_fx_signal_tool_v1.md:4546 | done | reduce_only推奨フックをRiskManagerへ追加済。 |
| `EP04-T1` | 15.4 EP-04 Ticket Clarity（HITL UX） | detailed_design_fx_signal_tool_v1.md:4555 | done | TicketBuilderの構造化/TTL委譲を反映済み。 |
| `EP04-T2` | 15.4 EP-04 Ticket Clarity（HITL UX） | detailed_design_fx_signal_tool_v1.md:4556 | done | Boardバナー表示と承認確認ダイアログを追加済み。 |
| `EP04-T3` | 15.4 EP-04 Ticket Clarity（HITL UX） | detailed_design_fx_signal_tool_v1.md:4557 | done | 監査delta/consent_reference_id/health/spread情報を追加済み。 |
| `EP05-T1` | 15.5 EP-05 Weekly Review（レポート/監査） | detailed_design_fx_signal_tool_v1.md:4566 | done | 週次テンプレへManual CSV/RiskSummary/ops_worklogを統合済み。 |
| `EP05-T2` | 15.5 EP-05 Weekly Review（レポート/監査） | detailed_design_fx_signal_tool_v1.md:4567 | done | Benchmark欠損率判定と`benchmark_gap`イベントを実装済み。 |
| `EP05-T3` | 15.5 EP-05 Weekly Review（レポート/監査） | detailed_design_fx_signal_tool_v1.md:4568 | done | 週次テンプレに署名欄/Manual CSV/Guardrails節を追加済み。 |
| `EP04-P4` | 57.4 テスト・Codex Packet・移行方針 | detailed_design_fx_signal_tool_v1.md:5878 | todo |  |
| `EP05-P6` | 57.4 テスト・Codex Packet・移行方針 | detailed_design_fx_signal_tool_v1.md:5840 | todo |  |
| `EP05-P7` | 57.4 テスト・Codex Packet・移行方針 | detailed_design_fx_signal_tool_v1.md:5926 | todo |  |
| `EP06-P4` | 57.4 テスト・Codex Packet・移行方針 | detailed_design_fx_signal_tool_v1.md:5805 | todo |  |
| `EP06-P5` | 57.4 テスト・Codex Packet・移行方針 | detailed_design_fx_signal_tool_v1.md:5990 | todo |  |
| `EP07-P1` | 57.4 テスト・Codex Packet・移行方針 | detailed_design_fx_signal_tool_v1.md:5967 | todo |  |
| `EP07-P2` | 57.4 テスト・Codex Packet・移行方針 | detailed_design_fx_signal_tool_v1.md:6018 | todo |  |
