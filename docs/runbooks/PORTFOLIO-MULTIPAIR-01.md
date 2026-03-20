---
id: PORTFOLIO-MULTIPAIR-01
title: Multi-pair Preparation from Shadow Gate
owners:
  - Portfolio Integrator
review_cycle_days: 30
linked_fr:
  - FR-55
  - FR-62
docops:
  related_commands:
    - tradectl portfolio next-stage --phase multi_pair_preparation
    - tradectl portfolio candidates
    - tradectl portfolio admit
---

# PORTFOLIO-MULTIPAIR-01: Shadow soak後のmulti-pair preparation実行

> **Runbook版数**: v0.1  
> **最終更新日**: 2026-03-19  
> **最終更新者**: Portfolio Integrator

## 目的
- shadow soak gate が `multi_pair_preparation` を返したときに、次の通貨ペア導入準備を packet 化して実行する。
- validation、candidate snapshot、admission snapshot を同じ packet にまとめる。

## トリガー
- `daily_shadow_review_summary.soak_summary.ready_for_transition=true`
- `qualified_next_phase=multi_pair_preparation`

## 事前準備
1. 次に試す `next_symbol` を決める。
2. その通貨ペアの merged parquet を用意する。
3. `profile / data_dir / feature_config / data_manifest` が現行 baseline と互換であることを確認する。

## 実行
1. packet を生成する。  
   `tradectl portfolio next-stage --phase multi_pair_preparation --next-symbol <symbol> --data-path <merged_parquet>`
2. 実行する。  
   `tradectl portfolio next-stage --phase multi_pair_preparation --next-symbol <symbol> --data-path <merged_parquet> --run`
3. validation、candidate snapshot、admit snapshot を見て pair 追加の前提が崩れていないか確認する。

## 証跡
- `reports/analysis/shadow/shadow_multi_pair_preparation_<stamp>.json`
- `reports/analysis/shadow/shadow_multi_pair_preparation_<stamp>.md`
- `reports/analysis/shadow/shadow_multi_pair_<pair>_validation.json`
- `reports/analysis/shadow/portfolio_candidates_snapshot.json`
- `reports/analysis/shadow/portfolio_admit_snapshot.json`

## 判定
- validation で baseline kernel が極端に崩れる pair は保留。
- candidate/admit snapshot で exposure bucket や slot conflict が不自然なら保留。
- 最初の有効化は baseline 直接昇格ではなく shadow-first。

## 変更履歴
| 日付 | 変更内容 | 変更者 |
| --- | --- | --- |
| 2026-03-19 | 初版作成 | Portfolio Integrator |
