# Threshold Configuration and Change Ledger Guidelines

## Planned configuration files

- `config/delivery/thresholds.yaml`: Codifies the Guard復旧MTTR、`data_ingestion_sla_p95`、`manual_hours`ベースラインを保持し、Delivery Control Tower（詳細設計 §25.9）のアラート閾値と同一値を参照できるようにする。Codex実装では`DeliveryAlert`種別（`guard_release_delay`/`data_sla_drift`/`manual_capacity_risk`）ごとに`warn`/`critical`の閾値をこのファイルから読み込む想定。既定値は実測値とRunbook条件に基づき25分/18分/0.8hを中心としたレンジを定義する。【F:detailed_design_fx_signal_tool_v1.md†L2149-L2163】
- `config/release/gates.yaml`: Release ReadinessのGateCriterion定義（`Gate-KPI-Sharpe`、`Gate-OPS-MTTR`、`Gate-DATA-SLA`、`Gate-FEEDBACK-Latency`）を保持し、CLI/サービスがGo/No-Go条件を一元参照する。Warn/Fail値は詳細設計 §30.4のテーブルと同一にし、スコープ別プロファイル（`backtest`/`paper`/`live`/`hotfix`）で上書きできるようにする。【F:detailed_design_fx_signal_tool_v1.md†L3515-L3526】
- `config/slippage.yaml`: Slippage Lab（§27.9）が利用する`bias_threshold`（既定0.5pips）、`critical_threshold`（0.8pips）、`stop_threshold`（1.2pips）、`drift_threshold`（warn:2.0, critical:3.0）を格納。Execution Modelの分位サンプル（基本設計 §4.9）に合わせ、シンボル/レジームごとの既定値を定義する。Emergency OrchestratorとRisk Managerが同じ値を参照し、閾値変更時に一括反映できるようにする。【F:detailed_design_fx_signal_tool_v1.md†L3278-L3281】【F:basic_design_fx_signal_tool_v1.md†L448-L466】

## Change Ledger categories

- `ChangeLedger.record_change(category='config_thresholds', ...)` を新設し、上記ファイルへの閾値変更時は必ずこのカテゴリで記録する。エントリには対象ファイルパス、変更前後の値、関連Runbook（例: `RUN-DATA-05`、`RUN-REL-01`）を必須項目として含める。Delivery Control Towerの`ChangeLedger`遅延検知（§25.4）と連携し、3日以内に記録が無い場合は`severity='major'`のアラートを上げる。【F:detailed_design_fx_signal_tool_v1.md†L2105-L2118】
- Release ReadinessのGate調整は`category='release_gate'`で記録し、`config/release/gates.yaml`のハッシュとEvidence Graph IDを添付する。`release.readiness` CLIは評価時に最新ハッシュを読み取り、Change Ledgerと乖離がある場合は`status='fail'`として`no_go`を返す。【F:detailed_design_fx_signal_tool_v1.md†L3495-L3526】

## Operational workflow

1. 閾値更新の提案時に`tradectl release simulate`または`tradectl delivery status --include-alerts`で影響をDry-runし、結果を`docs/change_requests/`に添付する。
2. 影響レビュー後、対象`config/*.yaml`を更新し、同じコミットで`ChangeLedger`記録ファイルを更新する。Evidence Graphへのリンクが必要な場合はRelease Readinessスナップショットに`EvidencePointer`を追加する。【F:detailed_design_fx_signal_tool_v1.md†L3475-L3526】
3. 更新後は`make ci-lite`およびGate対象の`pytest -k`フィルタを実行し、CIログを`reports/ci/`へ保存して`config_thresholds`エントリに追記する。
