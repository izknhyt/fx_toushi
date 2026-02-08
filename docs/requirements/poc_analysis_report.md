# PoC Analysis Report (Requirements)

Updated: 2026-01-30

## 目的
- PoC結果（トレード明細）から弱点を数値化し、改善の判断材料を提供する。
- 人間とAIがパラメータ/戦略方針を調整できるよう、分析軸を統一する。

## 対象
- `tradectl backtest poc-paper` の出力JSON（`trades`含む）。

## 出力（最小）
1. Summary
   - trades / win_rate / avg_r / pf / avg_hold_min
2. Economics / Cost
   - reward_risk_ratio
   - break_even_win_rate
   - actual_win_rate
   - win_rate_edge_vs_break_even
   - avg_cost_abs
   - avg_cost_r_estimate
3. Acceptance Gate（採用可否）
   - avg_r > 0
   - pf >= 1.10
   - max_drawdown <= 0.30
   - positive year ratio >= 0.75
   - trade count >= 300
   - pass/fail 判定
4. Breakdown
   - 方向別（long/short）
   - 年別
   - 年×方向
   - 時間帯（UTCセッション）
   - 曜日別
   - breakout別（upper/lower）
   - quality_score別（<1 / 1-2 / 2-3 / >=3 / missing）
   - trend帯域（< -0.3 / -0.3-0 / 0-0.3 / >=0.3 / missing）
   - ATR帯域（低/中/高：トレード分位）
   - breakout_width/(spread+slippage) 比率帯（<1 / 1-2 / 2-3 / >=3 / missing）
   - 連敗/連勝前のストリーク帯（0/1/2/3+）
5. Weak Points（弱点）
   - avg_r < 0 の領域を抽出（direction/year/quality/trend/ATR/cost ratio）
6. Opportunity Buckets（改善候補）
   - avg_r > 0 かつ一定件数以上のバケットを抽出
7. Next Actions（改善アクション）
   - Acceptance Gate失敗項目に紐づく推奨アクション

## 形式
- JSON（機械判定用）
- Markdown（レビュー用）

## CLI
- `tradectl backtest poc-report --input <poc.json> [--output <report.json>] [--export-md <report.md>]`

## 備考
- 追加の分析軸は初期実装で対応し、必要に応じて閾値や帯域を拡張する。
