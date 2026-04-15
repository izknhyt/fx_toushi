# FX Portfolio Completion Blueprint

Status: active delivery blueprint  
Last updated: 2026-03-21  
Parent architecture: [FX Portfolio Operating System](/Users/izumimotohayato/development/codex_invest/docs/architecture/fx_portfolio_operating_system.md)  
Implementation spec: [FX Portfolio Tool v2 Specification](/Users/izumimotohayato/development/codex_invest/docs/architecture/fx_portfolio_tool_v2_spec.md)

## 1. Why This Exists

この文書の目的は、`Mxx` や `Rxx` を増やすことではなく、  
`codex_invest` を **期待値が残り、実運用でも崩れにくい portfolio-first FX tool** として完成に近づけるための開発原則を固定することにある。

この repo の問題は「作るものが不明」ではない。  
問題は、設計・実装・評価・運用の各ループが分散すると、開発が milestone 消化や局所最適へ流れやすいことにある。

したがって、今後の開発はこの文書を基準に、

- 何を完成条件とみなすか
- 何を先に作るか
- 何を後回しにするか
- どの evidence が揃えば次へ進むか

を判断する。

## 2. North Star

この開発の北極星は次の 1 文に固定する。

`Build a portfolio-first FX operating tool that preserves positive expectancy under real operating constraints.`

日本語で言えば、

**実運用の制約を入れても期待値が残る portfolio-first FX tool を作る**

である。

ここで重要なのは、

- 単独戦略の見かけ上の PF を最大化すること
- マイルストーンの数を増やすこと
- UI や運用導線を増やすこと

ではない。

重要なのは、

- 実運用差で崩れないこと
- 悪化時に自動で止まれること
- 新しい candidate や新しい pair を安全に追加できること

である。

## 3. Completion Definition

このツールの「第一完成形」は次を満たした状態と定義する。

### 3.1 Baseline Completion

- `USDJPY baseline portfolio` が fixed され、baseline promotion は unresolved suppression / rollback / runtime drift がある間は block される
- `backtest / shadow / runtime` が同じ candidate / admission contract を使う
- `shadow feedback` が admission と runtime guardrail へ閉ループで返る
- `rollback / suppression / recovery` が automation と operator-facing surface の両方で機能する
- `candidate onboarding` が baseline-safe gate を通した時だけ実行できる

Baseline completion を `done` と判定するための minimum measurable gates:

- shadow soak:
  - `candidate_onboarding` 推奨は `3` 日連続
  - `multi_pair_preparation` 推奨は `5` 日連続
- rollout drift:
  - `mismatch_streak_days >= 2` で stronger freeze
  - `mismatch_streak_days >= 3` で rollback recommendation
- daily shadow alert:
  - `major drift >= 1` で critical
  - `missed fills >= 1` で warn
  - `missed fills >= 3` で critical
  - `shadow_action_required` 連続 `>= 2` 日で warn
  - `shadow_action_required` 連続 `>= 3` 日で critical
- candidate onboarding promotion gate:
  - `decision_status == promote`
  - `shadow_readiness_status in {ready, qualified, ok}`
  - `runtime_guardrail_status not in {blocked, manual_clear_required}`
  - `rollout_suppression_status != active`
  - `recovery_resolution_status in {resolved, not_required}`

### 3.2 Expansion Completion

- 最初の追加 pair が fixed baseline と同じ contract で評価できる
- cross-pair marginal contribution で追加 pair を採否判断できる
- multi-pair でも suppression / rollback / recovery が同じ surface で見える

Expansion completion を `done` と判定するための minimum measurable gates:

- first added pair decision:
  - full-history acceptance `pass`
  - recent acceptance `pass`
  - `delta_pf >= -0.01`
  - `delta_max_drawdown <= 0.03`
- first added pair reject threshold:
  - `delta_pf < -0.05` なら reject
- operator-facing gate:
  - latest pair result が `decision_status / promotion_gate / blockers / clear_conditions / pair_metadata` を GUI / shadow / ops で追える

### 3.3 Operational Completion

- daily automation が存在する
- operator-facing surface で `decision / discrepancy / drift / suppression / recovery` が追える
- unresolved drift や rollback が残る間、自動 promotion は止まる

Operational completion を `done` と判定するための minimum measurable gates:

- daily automation が `shadow-next-stage` と `shadow feedback validation` の両方で execution ledger を残す
- `validation-execution mismatch` は:
  - daily ops alert に昇格される
  - runtime guardrail で `blocked` か `degraded` になる
  - unresolved の間は next-stage / candidate onboarding / promotion を停止する
- rollback recovery は:
  - runbook packet
  - recovery checklist
  - execution ledger
  - resolution status
  を持つ

## 4. What Development Must Optimize For

開発は次の順で最適化する。

1. `Loss prevention`
   実運用の悪化時に自動で止まること
2. `Decision parity`
   backtest / shadow / runtime の判断差を減らすこと
3. `Evidence quality`
   candidate や pair の採否を evidence で決められること
4. `Safe extensibility`
   新戦略や新 pair を既存 baseline を壊さず追加できること
5. `Operator clarity`
   いま何が起きているか、なぜ止まっているかがわかること

逆に、次は最適化対象にしない。

- 似た戦略を先に大量追加すること
- 直近だけで良い PF を作ること
- マイルストーン粒度を細かくすること
- 実行頻度だけを上げること

## 5. Development Decision Rule

新しい作業は、次の順で判断する。

### 5.1 Step 1: Does it protect expectancy?

その変更は、

- 実運用差を減らすか
- 悪化時に止血できるか
- baseline の期待値を守るか

を最初に見る。

### 5.2 Step 2: Does it reduce uncertainty?

その変更は、

- 採用/保留/破棄の判断を evidence で出せるか
- operator の状況認識を改善するか
- feedback loop を閉じるか

を次に見る。

### 5.3 Step 3: Does it safely unlock growth?

最後に、

- 新戦略追加
- 新 pair 追加
- automation 拡張

のような拡張余地を安全に増やすかを見る。

この順を守る限り、開発は milestone 消化ではなく completion に近づく。

## 6. The Correct Development Loop

今後の開発ループは次に固定する。

1. `Define the operating risk or growth bottleneck`
2. `Implement the smallest contract or surface that resolves it`
3. `Run targeted regression + bugcheck`
4. `Capture evidence in docs/development_plan.md`
5. `Promote only if the evidence reduces operational uncertainty`

短く言えば、

`risk -> contract -> evidence -> promotion`

である。

このループから外れる変更は、基本的に優先しない。

## 7. Milestones Are Secondary

`Rxx` や `Mxx` は必要だが、役割は限定する。

- `Roadmap milestone`
  completion condition を分割するための管理単位
- `Task/M-step`
  実装を切るための作業単位

つまり、

- マイルストーンは **開発を助ける道具**
- 完成条件は **開発の目的**

である。

新しい `R` や `M` を追加するのは、completion condition をより明確にできる時だけにする。

## 8. Current Best Sequence

現時点で最善の開発順は次の通り。

1. `USDJPY baseline` を守る closed loop を完成させる
2. `candidate onboarding` を baseline-safe にする
3. `first additional pair` を evidence-first で追加する
4. `cross-pair portfolio contribution` を見る
5. `multi-pair pilot` を運用で安定させる
6. その後に次の pair や candidate を追加する

この順序を崩して、

- 先に戦略を大量追加する
- 先に pair を増やす
- 先に UI を広げる

のは避ける。

### 8.1 v2 Scope Boundary

ここで completion に含める `multi-pair` は限定的である。

- `v2 scope`
  - `USDJPY baseline`
  - `shadow feedback closed loop`
  - baseline-safe `candidate onboarding`
  - `first additional pair` の preparation と pilot-evaluation
- `post-v2 scope`
  - 複数 pair の本格 rollout
  - pair の継続追加と portfolio scaling
  - broker/live execution の高度最適化
  - ML selector

したがって、`first additional pair` は v2 completion への橋渡しであり、  
広い意味での multi-pair production scaling は post-v2 とする。

## 9. Team Optimization Rule

チームの目的も milestone を消化することではない。

各 role は次に集中する。

- `Core Integrator`
  completion condition と priority を守る
- `Allocator / Runtime`
  decision parity と safe guardrail
- `Validation / Evidence`
  adoption uncertainty の削減
- `GUI / Shadow Surface`
  operator clarity
- `Ops / Automation`
  suppression / recovery / promotion の安全運用

並列化は「人数を増やすため」に行うのではなく、  
**completion condition に対して独立な責務だけを速く回すため** に行う。

## 10. Immediate Rule For Future Work

次の作業に入る前に、毎回次を明確にする。

1. これは baseline の期待値を守る作業か
2. これは運用不確実性を減らす作業か
3. これは安全な拡張を解放する作業か
4. どの completion condition に効くのか
5. どの evidence が出たら done か

この 5 問に答えられない作業は、優先順位を下げる。

## 11. Immediate Highest-Priority Gap Rule

今後の next action は `R7 を定義する` のような milestone 命名ではなく、  
次の 1 問で決める。

`What is the highest-priority unresolved operating or expansion gap that blocks the completion definition?`

現時点の答えは次である。

- baseline / candidate onboarding / first-added-pair は揃っている
- 次に埋めるべきなのは `multi-pair pilot rollout` を実運用で安定化するための未解決 gap
- したがって、次の開発は `R7 の名前付け` ではなく `multi-pair pilot rollout の completion gate と operational evidence を固める作業` を優先する

## 12. Practical Consequence

今後、開発判断で迷った時の基準は単純である。

- milestone を増やすべきか、ではなく
- **この変更は完成に近づくか** を問う

その答えが弱いなら、やらない。

その答えが強いなら、small slice に切って実装する。

以上を、completion-first development の正式基準とする。
