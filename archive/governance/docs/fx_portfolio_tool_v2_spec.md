# FX Portfolio Tool v2 Specification

Status: draft implementation spec for the next major revision  
Last updated: 2026-03-20  
Parent architecture: [FX Portfolio Operating System](/Users/izumimotohayato/development/codex_invest/docs/architecture/fx_portfolio_operating_system.md)

## 1. Purpose

この仕様書は、現行の portfolio-first 方針を「実装可能な契約」に落とすための v2 仕様である。

v2 の目的は次の 3 点に絞る。

1. `strategy-first` ではなく `portfolio-first` の実行系を定義する
2. `backtest / shadow / runtime` で共通の decision path を使う
3. 新戦略の採用判断を `standalone` と `marginal contribution` の両方で行えるようにする

## 2. Scope

v2 が対象とする範囲:

- `USDJPY-first` の portfolio admission 実行系
- candidate trade schema
- admission decision contract
- evaluation contract
- runtime / shadow / backtest parity rules
- GUI / CLI の最小 surface

v2 で後回しにする範囲:

- multi-pair の broad production scaling
- ML ベースの selector
- broker/live execution 高度化
- enterprise 向け approval / audit workflow

補足:

- `first additional pair` の preparation と pilot-evaluation は v2 delivery path に含める
- 複数 pair を継続的に追加する本格運用は post-v2 とする

## 3. Product Principles

- `portfolio-first`
- `cost-aware sparse trading`
- `no-trade is valid`
- `single decision path`
- `shadow-feedback closed loop`
- `USDJPY-first, multi-pair-ready`
- `personal-use default`

## 4. System Shape

v2 は次の 6 層で構成する。

1. `data layer`
2. `feature / regime layer`
3. `strategy layer`
4. `portfolio admission layer`
5. `execution / risk layer`
6. `feedback / evaluation layer`

主役は `portfolio admission layer` であり、strategy は candidate を生成するだけに留める。

## 5. Candidate Trade Contract

各 strategy は、注文ではなく `candidate trade` を返す。

必須フィールド:

- `candidate_id`
- `strategy_id`
- `symbol`
- `side`
- `timestamp`
- `entry`
- `stop`
- `target`
- `confidence`
- `expected_holding_minutes`
- `portfolio_group`
- `exposure_bucket`

推奨フィールド:

- `expected_edge`
- `estimated_cost`
- `quality_score`
- `regime_fit`
- `session_tag`
- `atr_value`
- `trend_value`
- `cost_ratio`
- `metadata`

型の原則:

- 数値は float/int で保持する
- strategy 固有の補助情報は `metadata` に逃がす
- runtime / shadow / backtest で同じ field 名を使う

## 6. Admission Contract

admission layer は candidate を受け取り、次のいずれかを返す。

- `accept`
- `reject`
- `defer`
- `resize`
- `replace`

decision payload 必須フィールド:

- `decision`
- `reason_code`
- `strategy_id`
- `symbol`
- `portfolio_group`
- `exposure_bucket`
- `score`
- `estimated_cost`
- `slot_cost`

推奨フィールド:

- `replaced_candidate_id`
- `blocked_by_position_id`
- `notes`

### 6.1 Admission Inputs

判定には少なくとも次を使う。

- active positions
- open candidate set
- `portfolio_group`
- `exposure_bucket`
- `role_priority`
- `expected_holding_minutes`
- `estimated_cost`
- regime fit
- session value
- group / exposure capacity

### 6.2 Initial Scoring Rule

v2 の基準スコアは rule-based でよい。

`admission_score = expected_edge - estimated_cost - slot_cost - holding_penalty - conflict_penalty`

補足:

- `expected_edge` が無い戦略は、`confidence` と signal metadata から暫定スコアを作ってよい
- 同じ `portfolio_group` では主力を優先する
- 同じ `exposure_bucket` の重複は厳しく落とす

## 7. Portfolio Metadata Contract

各 strategy manifest で v2 の必須 metadata とする:

- `portfolio_group`
- `role_priority`
- `expected_holding_minutes`
- `slot_cost`
- `exposure_bucket`
- `max_active_per_group`
- `replacement_policy`

意味:

- `portfolio_group`: 同系統候補の競争単位
- `role_priority`: 主力 / 補完 / 研究枠の序列
- `expected_holding_minutes`: 機会コスト計算用
- `slot_cost`: ポジション枠の使用コスト
- `exposure_bucket`: 実質的な同一エクスポージャー判定
- `max_active_per_group`: 同時採用上限
- `replacement_policy`: 既存候補や既存ポジションを差し替えるか

## 8. Evaluation Contract

v2 では戦略採用を 3 段階で判断する。

### 8.1 Standalone Gate

必須評価項目:

- `pf`
- `avg_r`
- `max_drawdown`
- `trades`
- `positive_year_ratio`

### 8.2 Marginal Contribution Gate

既存 portfolio に足した時に次を見る。

- `delta_pf`
- `delta_avg_r`
- `delta_max_drawdown`
- `delta_positive_year_ratio`
- `delta_trades`

採用原則:

- `standalone` が強くても `marginal contribution` が負なら採用しない
- `marginal contribution` が window によって正負で割れる場合は保留または regime 限定とする

### 8.3 Shadow Gate

最終確認:

- cost drift
- missed fills
- runtime stability
- data freshness

### 8.4 Feedback-To-Admission Loop

v2 では `shadow gate` を pass/fail 判定だけで終わらせない。  
shadow で観測した discrepancy は admission layer へ戻す。

minimum actionable outputs:

- `admission_penalty`
- `role_priority_override`
- `session_block_recommendation`
- `execution_mode_override`

適用原則:

1. まず `penalty / resize / defer` で edge を削らずに悪化を抑える
2. 継続的な discrepancy がある場合に `session` や `portfolio_group` を block する
3. それでも安定しない場合に candidate demotion / replacement を行う

つまり、v2 の主眼は「見つけて止める」ではなく  
`shadow -> feedback -> admission adjustment`
の閉ループを作ることにある。

## 9. Runtime / Shadow / Backtest Parity

v2 の最重要ルールは parity である。

共通化するもの:

- candidate schema
- admission decision contract
- hard filters
- active position conflict rules
- portfolio group / exposure bucket handling

研究専用に分岐してよいもの:

- report rendering
- exploratory diagnostics
- optional sensitivity runs

## 10. CLI Surface

v2 で最低限必要な CLI は次の通り。

- `tradectl portfolio candidates`
  現在の candidate 一覧
- `tradectl portfolio admit`
  admission decision を出す
- `tradectl portfolio evaluate`
  standalone + marginal contribution を比較する
- `tradectl portfolio review`
  failed window / drag / next action を出す

当面は既存 tool 群の wrapper でもよい。

## 11. GUI Surface

v2 GUI は strategy 一覧を主役にしない。

主表示は次:

- active slots
- accepted candidates
- rejected / deferred candidates
- reason codes
- portfolio group occupancy
- exposure bucket occupancy

補助表示:

- strategy status
- recommended / excluded badge
- latest evaluation summary

## 12. Initial Baseline Portfolio

v2 初期基準 portfolio は、現時点では次を baseline として扱う。

- `m1_asia_compression_expansion_breakout`
- `m1_us_session_trend_pullback`

`m1_baseline_donchian_upper_only` は candidate 扱いとし、`marginal contribution` で昇格可否を判断する。

理由:

- baseline としては `Asia + US Pullback` が `2016_2025` と `2016_2021` の両方で長期 gate を通しやすい
- `upper_only` は直近寄りでは有効だが、pre-recent regimes では baseline を悪化させる window がある

## 13. Migration From Current State

### Phase 1

- current strategy manifests を v2 metadata 準拠へ寄せる
- candidate evaluation runner を標準採用にする
- review runner を evidence-first 運用にする

### Phase 2

- runtime / shadow で admission contract を共通化する
- GUI を candidate / admission 中心に組み替える

### Phase 3

- new strategy onboarding を `standalone + marginal contribution` 必須へ切り替える
- first additional pair の preparation / pilot-evaluation へ進む

### Resolved Rollout Order

現時点での最善の rollout order は次の通りに固定する。

1. `USDJPY baseline` を固定する
2. `shadow-feedback closed loop` を admission へ接続する
3. execution / cost 差を calibration する
4. その baseline に対して `candidate onboarding` を行う
5. baseline が壊れないことを確認してから `multi-pair preparation` へ進む

この順序より先に multi-pair broad rollout や strategy count を広げることは、v2 では推奨しない。

## 14. Acceptance For v2 Roll-In

v2 を実運用の既定に切り替える条件:

- candidate schema が strategy 間で揃う
- admission decision payload が backtest / shadow / runtime で同型
- baseline portfolio が long-horizon で安定
- candidate evaluation runner が新戦略採用の標準手順になる
- GUI / CLI で accepted / rejected reasons が追える
- first additional pair の preparation / pilot-evaluation が既存 contract 上で評価できる

## 15. Open Decisions

まだ決め切っていない点:

- `expected_edge` を strategy 側で必須にするか、admission 側で近似生成するか
- `replace` を v2 初期から有効にするか
- GUI の v2 を既存 GUI の拡張で済ませるか、別 view にするか
- multi-pair 移行時の `exposure_bucket` 命名規則

## 16. Canonical References

- [FX Portfolio Operating System](/Users/izumimotohayato/development/codex_invest/docs/architecture/fx_portfolio_operating_system.md)
- [Development Plan](/Users/izumimotohayato/development/codex_invest/docs/development_plan.md)
- [PoC Analysis Report Requirements](/Users/izumimotohayato/development/codex_invest/docs/requirements/poc_analysis_report.md)
