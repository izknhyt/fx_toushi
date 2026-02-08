# Donchian Strategy Quality Filters (Change Design)

Updated: 2026-01-30

## 背景
- bidirectional（upper=long / lower=short）は現実コスト前提で優位性が弱い（PF<1 / AvgR<=0）。
- long-onlyは勝てたが、方向と表示の整合性が曖昧だったため、戦略としての明文化が必要。
- 現状ロジックは「ブレイクしたかどうか」だけで、環境認識や質の評価が不足している。

## 目的
- コスト込みでも期待値（AvgR）がプラスになる条件だけを採用する。
- 低ボラ・レンジのノイズを排除し、勝てる局面だけを取る。
- 戦略選択・復元を容易にする（複数戦略の共存を前提）。

## 非目的
- データ取得方式の変更（provider切替）は対象外。
- ML/AIによる予測モデルの導入は対象外。
- 自動売買の実装は対象外（シグナル提示まで）。

## 変更概要
1) トレンドフィルタ
- 上位足トレンドと方向が一致する場合のみシグナルを許可。

2) ボラティリティ（ATR）フィルタ
- ATRが一定以下の場合は取引しない。

3) ブレイク品質フィルタ（コスト勝ち条件）
- ブレイク幅がコスト（スプレッド+スリッページ）を十分上回る場合のみ有効。

4) ログとGUIの拡張
- フィルタ判定理由・品質スコア（任意）をログに残す。

## 推奨設定（コスト前提を固定）
- 評価・運用ともに「現実より少し厳しい」値を固定で使う。
  - spread: 0.005
  - slippage: 0.0015
  - slippage_std: 0.001
- これらは manifest で明示し、PoC/GUI/運用で同値を使う。

## 詳細仕様（案）

### 1. トレンドフィルタ
- 使用特徴量: regime_trend_1h
- 値の意味:
  - > 0: 上昇トレンド
  - < 0: 下降トレンド
  - = 0: 中立
- 判定:
  - long: regime_trend_1h > filters.trend_threshold
  - short: regime_trend_1h < -filters.trend_threshold
- パラメータ:
  - filters.trend_required: true
  - filters.trend_threshold: 0.0

### 2. ATRフィルタ
- 使用特徴量: atr_14_1h
- 判定:
  - atr_14_1h >= filters.atr_min
- 推奨値:
  - filters.atr_min: 0.08

### 3. ブレイク品質フィルタ
- ブレイク幅: abs(close - level)
- 判定:
  - breakout_width >= max(
      filters.min_breakout_abs,
      filters.breakout_min_atr_mult * atr_14_1h,
      filters.breakout_min_cost_mult * (spread + slippage)
    )
- 推奨値:
  - filters.min_breakout_abs: 0.05
  - filters.breakout_min_atr_mult: 0.3
  - filters.breakout_min_cost_mult: 3.0

### 4. 適用範囲
- 対象戦略: Donchian系 3バリアント
  - m1_baseline_donchian (bidirectional)
  - m1_baseline_donchian_long_only
  - m1_baseline_donchian_upper_only
- いずれも同じフィルタ判定を適用可能にする。

## パラメータ定義（manifest）
例:
```yaml
parameters:
  entry:
    filters:
      trend_required: true
      trend_threshold: 0.0
      atr_min: 0.08
      min_breakout_abs: 0.05
      breakout_min_atr_mult: 0.3
      breakout_min_cost_mult: 3.0
  execution:
    spread: 0.005
    slippage: 0.0015
    slippage_std: 0.001
```

## ログ/GUI出力
- signal payloadに以下を追加（任意）:
  - breakout_width
  - filter_flags
  - filter_block_reason
  - quality_score

## 評価基準（暫定）
- 現実スプレッド（0.005）で評価。
- AvgR > 0（必須）
- PF >= 1.1（推奨）
- MaxDD <= 0.30（推奨）

## 評価プロトコル
- 年別（2022/2023/2024/2025）+ 通年（2022-2025）を必須。
- spread 感度テスト（0.005 / 0.008 / 0.010）を必須。
- AvgRが0に近い戦略は採用しない。

## 移行方針
- 既存の挙動を壊さないため、フィルタはmanifestで明示的にON。
- 最初は upper-only / long-only で運用検証し、bidirectionalは検証後に判断。

## 依存/影響範囲
- src/strategies/donchian.py
- config/strategy_manifest.yaml
- tools/gui_ops_loop.py（ログ拡張）
- backtest/paper_poc.py（評価用）

