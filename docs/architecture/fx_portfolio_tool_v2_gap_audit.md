# FX Portfolio Tool v2 Gap Audit

Status: implementation parity audit for v2 spec  
Last updated: 2026-03-16  
Spec reference: [FX Portfolio Tool v2 Specification](/Users/izumimotohayato/development/codex_invest/docs/architecture/fx_portfolio_tool_v2_spec.md)

## 1. Purpose

この文書は、v2 仕様と現行実装の差分を棚卸しし、M2 をどこまで閉じてよいかを明確にするための監査メモである。

見る対象は次の 5 点に絞る。

- candidate trade contract
- admission decision contract
- runtime / shadow / backtest parity
- evaluation contract
- GUI / CLI surface

## 2. Executive Summary

結論から言うと、v2 の中核である `admission decision contract` と `parity の観測面` はかなり揃った。

一方で、次の 3 点はまだ仕様先行である。

1. `candidate trade` が strategy 間で共通 object / schema として固定されていない
2. v2 の `portfolio` CLI surface は専用コマンドとして未実装
3. GUI は allocation summary を表示できるが、まだ strategy-list 中心の構造が残っている

したがって、M2 は「admission parity の基盤は成立」と判断してよいが、v2 roll-in の完了条件はまだ満たしていない。

## 3. Spec Coverage

### 3.1 Candidate Trade Contract

判定: `partial`

実装済み:

- signal log には `quality_score`, `atr_value` など一部の candidate-like metadata が出ている
  - [registry.py](/Users/izumimotohayato/development/codex_invest/src/strategies/registry.py)
- strategy ごとに `quality_score`, `atr_value`, `session_tag` 相当のフィールドは個別に保持している
  - [asia_compression_expansion_breakout.py](/Users/izumimotohayato/development/codex_invest/src/strategies/asia_compression_expansion_breakout.py)
  - [us_session_momentum.py](/Users/izumimotohayato/development/codex_invest/src/strategies/us_session_momentum.py)
  - [donchian.py](/Users/izumimotohayato/development/codex_invest/src/strategies/donchian.py)

未完:

- `candidate_id` の正式採番がない
- `expected_edge` が共通フィールドではない
- `expected_holding_minutes` は manifest/allocation 側にはあるが、candidate payload 自体には埋め込まれていない
- `metadata` を含む canonical schema/dataclass がない
- backtest / shadow / runtime で同じ candidate object を直接受け渡していない

評価:

現状は「signal object + strategy-specific fields + allocator 側の metadata 解決」で動いている。v2 spec が求める「共通 candidate contract」にはまだ届いていない。

### 3.2 Admission Decision Contract

判定: `mostly_done`

実装済み:

- allocator が `decision`, `reason_code`, `portfolio_group`, `exposure_bucket`, `estimated_cost`, `slot_cost` を返す
  - [allocation.py](/Users/izumimotohayato/development/codex_invest/src/strategies/allocation.py)
- `StrategyEngine` が allocation outcome を保持する
  - [registry.py](/Users/izumimotohayato/development/codex_invest/src/strategies/registry.py)
- `portfolio.admission` event として runtime log に記録する
  - [registry.py](/Users/izumimotohayato/development/codex_invest/src/strategies/registry.py)
- GUI / ops loop / shadow API が同じ contract を summary 表示できる
  - [web_server.py](/Users/izumimotohayato/development/codex_invest/src/interfaces/gui/web_server.py)
  - [gui_ops_loop.py](/Users/izumimotohayato/development/codex_invest/tools/gui_ops_loop.py)
  - [shadow_api.py](/Users/izumimotohayato/development/codex_invest/src/interfaces/gui/shadow_api.py)

未完:

- `score` が payload に含まれていない
- `replace` / `resize` は summary と contract 上は扱えるが、実 producer は未実装
- `replaced_candidate_id`, `blocked_by_position_id`, `notes` はまだ出していない

評価:

v2 の admission contract は「accept/reject/defer を共通 payload で流す」という意味では成立している。未実装なのは、より高度な decision variant と付加情報である。

### 3.3 Portfolio Metadata Contract

判定: `partial`

実装済み:

- allocation profile では `portfolio_group`, `role_priority`, `expected_holding_minutes`, `slot_cost`, `exposure_bucket`, `max_active_per_group`, `max_active_per_exposure_bucket` を扱う
  - [strategy_allocation.yaml](/Users/izumimotohayato/development/codex_invest/config/strategy_allocation.yaml)
- allocator がこれらを active position conflict と score penalty に反映する
  - [allocation.py](/Users/izumimotohayato/development/codex_invest/src/strategies/allocation.py)

未完:

- strategy manifest 側の必須 schema としてはまだ強制されていない
- `replacement_policy` は contract にあるが未実装
- metadata の canonical validator がない

評価:

metadata は実用上かなり使えているが、まだ「config convention」であって「強制契約」ではない。

### 3.4 Evaluation Contract

判定: `mostly_done`

実装済み:

- standalone gate 相当の long-horizon validation がある
  - [run_long_horizon_portfolio_validation.py](/Users/izumimotohayato/development/codex_invest/tools/run_long_horizon_portfolio_validation.py)
- failed window の drag review がある
  - [review_long_horizon_validation.py](/Users/izumimotohayato/development/codex_invest/tools/review_long_horizon_validation.py)
- baseline vs candidate の marginal contribution 比較がある
  - [evaluate_portfolio_candidates.py](/Users/izumimotohayato/development/codex_invest/tools/evaluate_portfolio_candidates.py)

未完:

- shadow gate は summary 化の観測面はあるが、採用フロー上の正式 gate にはまだなっていない
- evaluation result schema の canonical 型はない
- candidate onboarding をこの runner 群へ必須接続する CLI workflow はまだ弱い

評価:

研究評価の中核は揃っている。残るのは「標準採用フローとして固定すること」と「shadow gate を昇格条件に組み込むこと」である。

### 3.5 Runtime / Shadow / Backtest Parity

判定: `mostly_done`

実装済み:

- allocator payload が runtime / shadow 観測面で共通
- allocation event が `portfolio.admission` に分離され、signal event と契約が分かれた
- GUI / ops / shadow が同じ summary source を読める

未完:

- backtest 側も candidate schema まで含めて runtime と同型、とはまだ言えない
- shadow/runtime が admission payload を first-class input/output とする dedicated API にはまだなっていない

評価:

M2 の狙いだった parity groundwork は成立している。未完なのは、candidate layer と operational workflow の完全一致である。

### 3.6 GUI / CLI Surface

判定: `partial`

実装済み:

- GUI は accepted / rejected / deferred の recent summary を見せられる
- excluded strategy の灰色表示はすでにある

未完:

- spec 記載の `tradectl portfolio candidates/admit/evaluate/review` は未実装
- GUI はまだ `active slots`, `group occupancy`, `bucket occupancy` を主役にした画面ではない
- admission-first UI への再設計は未着手

評価:

read surface は増えたが、v2 の interface redesign はまだ始まったばかりである。

## 4. M2 Closure Verdict

M2 を「admission parity groundwork」と定義するなら、閉じてよい。

理由:

- admission payload は共通化された
- runtime / shadow / GUI で同じ decision summary を見られる
- signal と admission の log contract も分離できた

ただし、次のものは M3 ではなく「M2の残余ではなく v2 roll-in 条件」として扱うのがよい。

- canonical candidate schema
- dedicated portfolio CLI surface
- candidate/admission 中心の GUI surface

## 5. Recommended Next Sequence

次の順番がもっとも自然である。

1. `candidate trade` の canonical dataclass/schema を作る
2. allocator input を `signal object` 依存から `candidate payload` 寄りへ寄せる
3. `tradectl portfolio evaluate` と `tradectl portfolio review` を wrapper CLI として正式化する
4. GUI に `active slots` / `group occupancy` / `recent admission reasons` を主表示する view を足す
5. shadow gate を candidate promotion flow に組み込む

## 6. Open Questions Carried Forward

- `expected_edge` を strategy 側必須にするか
- `replace` を v2 初期 rollout に含めるか
- `resize` を admission contract に含めたまま先送りするか
- GUI を既存 panel 拡張で済ませるか、portfolio 専用 view を分けるか

## 7. Bottom Line

いまの実装は「portfolio-first の研究と観測」ができる状態までは来ている。

まだ足りないのは、「candidate を共通 schema で運ぶこと」と「portfolio UX/CLI を first-class にすること」である。

したがって、次フェーズでは戦略チューニングより、candidate/admission contract の formalization を優先するのが正しい。
