# FX Portfolio Operating System

Status: active architecture reference for new development  
Last updated: 2026-03-12

## 1. Purpose

このリポジトリの今後の主目的は、`USDJPY` の単独戦略集を増やすことではない。  
目指すのは、`USDJPY-first / multi-pair-ready` な `FX portfolio operating system` を作ること。

最適化対象は「各戦略の PF」ではなく、次の総合効用とする。

`portfolio_utility = expected_return - drawdown_penalty - trading_cost - slot_time_penalty - correlation_penalty`

このため、開発の主役は戦略そのものではなく、`portfolio admission` と `execution/risk` である。

## 2. Design Priorities

優先順位は次の通り。

1. `portfolio-first`
2. `shadow/live/backtest parity`
3. `cost-aware sparse trading`
4. `USDJPY-first, multi-pair-ready`
5. `strategy extensibility`

新しい戦略を増やすこと自体は目的ではない。  
既存ポートフォリオに対して `marginal contribution` が正である場合にのみ採用する。

## 3. Non-Goals

個人利用の現フェーズでは、次は主目的にしない。

- 多人数運用向けの細粒度承認フロー
- 重い監査バンドルや署名台帳の維持
- 単独戦略の PF だけを追う探索
- 同一通貨・同系統戦略の過剰な積み増し
- 常時売買を前提にした設計

必要なのは「たくさん打つこと」ではなく、「良い候補だけを残すこと」。

## 4. Architectural Principles

### 4.1 Strategy = Alpha Generator

各戦略は注文を直接決めるのではなく、`candidate trade` を返す。  
戦略の責務はシグナル候補の生成までに限定する。

各 candidate は少なくとも次を持つ。

- `strategy_id`
- `symbol`
- `side`
- `entry`, `stop`, `target`
- `expected_edge`
- `estimated_cost`
- `confidence`
- `expected_holding_minutes`
- `portfolio_group`
- `exposure_bucket`
- `regime_fit`
- `timestamp`

### 4.2 Portfolio Admission Is The Core

候補の採否は中央の admission layer が決める。  
意思決定は `accept / reject / defer / resize / replace` のいずれか。

判定入力は次を基本とする。

- 現在の open positions
- `portfolio_group`
- `exposure_bucket`
- `role_priority`
- `expected_holding_minutes`
- 想定コスト
- レジーム適合
- セッション価値
- 相関と重複

### 4.3 No-Trade Is A Valid Decision

候補が出ても、見送るのは正常な結果である。  
「常に何かを出す」より「価値が薄い候補を落とす」ことを優先する。

### 4.4 One Decision Path

`backtest`, `shadow`, `runtime/live` は同じ decision path を使う。  
研究時だけ都合のよい判定を許さない。

## 5. Target System Shape

### 5.1 Layered Model

1. `Data layer`
   Market data, provider health, spread/liquidity context
2. `Feature / regime layer`
   Trend/range/news/illiquid/chop 判定
3. `Strategy layer`
   Candidate generation only
4. `Portfolio admission layer`
   Candidate selection, rejection, defer, replace, resize
5. `Execution / risk layer`
   Fill assumptions, slippage control, kill switch, risk caps
6. `Feedback layer`
   Shadow drift, pnl feedback, decay, re-ranking

### 5.2 Core Portfolio Metadata

今後の戦略 manifest / allocation profile では、少なくとも次を正式メタデータとする。

- `portfolio_group`
- `role_priority`
- `expected_holding_minutes`
- `slot_cost`
- `exposure_bucket`
- `max_active_per_group`
- `replacement_policy`

### 5.3 Admission Scoring

初期のルールベース admission は、概ね次の考え方で十分。

`admission_score = expected_edge - estimated_cost - holding_penalty - correlation_penalty - conflict_penalty`

このスコアをもとに、

- 同じ `portfolio_group` では主力を優先
- 同じ `exposure_bucket` の重複を抑制
- 長く居座る候補は厳しく評価
- 既存ポジションを邪魔する候補は reject/defer

を実施する。

## 6. USDJPY-First Build Strategy

最初は `USDJPY` から始める。  
ただし、内部設計は最初から通貨ペア非依存にする。

理由は次の通り。

- 検証速度が高い
- データと流動性が比較的安定している
- 既存資産を再利用しやすい

ただし最終形は `USDJPY` 専用ツールではない。  
`EURUSD`, `GBPUSD`, `EURJPY`, `AUDUSD` へ自然に広げられる構造を維持する。

## 7. Evaluation Standard

戦略採用は 3 段階で評価する。

### 7.1 Standalone Gate

まず単独で最低限の quality を満たすかを見る。

- `avg_r`
- `pf`
- `max_dd`
- trades
- yearly stability

### 7.2 Marginal Contribution Gate

次に既存ポートフォリオへ足したときに価値が増えるかを見る。

- `delta_pf > 0`
- `delta_max_dd` が許容内
- `positive_year_ratio` を壊さない
- trade overlap / slot occupancy が悪化しすぎない

### 7.3 Shadow Gate

最後に shadow で乖離を見る。

- cost drift
- missed fills
- runtime stability
- data freshness

`standalone` が強くても `marginal contribution` が負なら採用しない。

## 8. Personal-Use Operating Model

このリポジトリは当面、個人利用を前提とする。  
そのため、旧来のエンタープライズ寄り運用は default から外す。

### 8.1 What We Keep

- deterministic backtest evidence
- shadow/live parity
- kill switch, spread guard, emergency unwind
- 最小限の runbook
- 再現に必要なログと設定履歴

### 8.2 What We Drop From The Default Path

- Product Owner / Ops Manager / Risk Officer の多段承認
- Trader sign-off テンプレ必須化
- 細粒度 audit bundle の常時生成
- 文書中心の promotion paperwork
- ガバナンスのためだけの doc 更新

### 8.3 Practical Rule

個人利用の通常開発では、

- `設計書`
- `development_plan`
- `テスト結果`
- `PoC / shadow evidence`

が揃っていれば進めてよい。  
追加の承認書類は不要。

## 9. Documentation Rules

今後の参照順は次の通り。

1. この設計書
2. `docs/development_plan.md`
3. 直近の validation / analysis evidence
4. 必要な runbook
5. `detailed_design_fx_signal_tool_v1.md` は legacy implementation reference

`detailed_design_fx_signal_tool_v1.md` と本書が衝突する場合、今後の新規開発方針については本書を優先する。  
既存モジュールの仕様確認だけ、旧詳細設計を参照する。

## 10. Near-Term Roadmap

次の優先順位で進める。

1. `portfolio_admission_v2`
   `replace/defer`, `slot_cost`, `exposure_bucket`, `max_active_per_group`
2. runtime / shadow / backtest の decision path 統一
3. candidate schema の明文化
4. USDJPY 上の主力 2-3 系統を安定運用
5. multi-pair expansion
6. data/execution quality の強化

## 11. Related Documents

- `docs/development_plan.md`
- `docs/release_checklist.md`
- `docs/onboarding.md`
- `docs/requirements/poc_analysis_report.md`
- `detailed_design_fx_signal_tool_v1.md` (legacy reference)
