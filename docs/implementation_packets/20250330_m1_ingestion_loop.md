# Implementation Packet: EP01-ING-P1

## メタデータ
- Epic: EP-01 Data Ingestion
- Packet範囲: M1運用ループ（Dukascopy中心の5分足ポーリング）
- 参照セクション: §3.1.2, §17.6
- 依頼Issue/PR: docs/change_requests/20250318_packet_backlog.md
- 作成日: 2025-03-30
- 作成者: Codex Liaison
- エビデンス格納先: reports/implementation/20250330_m1_ingestion_loop/

## 1. 目的と背景
- KPI/リスク影響: 5分足の継続取得とbar_gap監視、データ遅延時のRunbook移行を確実化。
- ユーザストーリー/Runbook整合: RUN-DATA-05/06の手動運用を前提に、API連携なしでもPaper運用の足回りを回す。

## 2. 変更サマリ
| コンポーネント | 変更内容 | テスト指示 | Feature Flag |
| --- | --- | --- | --- |
| tools/ingestion_loop.py | Dukascopyポーリング・bar更新・SLAメトリクス記録 | `python tools/ingestion_loop.py --once` | N/A |
| src/data/providers/dukascopy.py | ProviderAdapterに実fetchを追加（最小） | `pytest -k dukascopy_provider` | N/A |
| src/interfaces/cli/__init__.py | `tradectl data loop`サブコマンド追加 | `pytest -k data_loop_cli` | N/A |
| metrics/data_ingestion_sla.jsonl | `last_bar_ts`/`bar_gap_minutes`追加 | `pytest -k ingestion_metrics` | N/A |

## 3. チェックリスト
- [ ] 設計整合: §3.1.2のM1運用ループと実装が一致
- [ ] テスト実行: `python tools/ingestion_loop.py --once`
- [ ] 監査ログ検証: metrics/data_ingestion_sla.jsonlにbar_gap/last_bar_tsが出力される
- [ ] Rollback手順記載: RUN-DATA-05/06の手動切替で復旧可能
- [ ] Trader Sign-offテンプレ発行: docs/trader_signoff/EP01-ING-P1.md

## 4. エビデンス
- CLI/スクリーンショット: docs/trader_signoff/EP01-ING-P1.md 参照
- メトリクス: reports/implementation/20250330_m1_ingestion_loop/metrics/
- ログ: reports/implementation/20250330_m1_ingestion_loop/logs/

## 5. リスクと依存関係
- 依存Packet: EP01-P2（DataLag Mitigation）, EP03-P1（HealthMonitor）
- 懸念事項/Acceptable Degradationへの影響: Dukascopy失敗時はRUN-DATA-05に従い手動フェイルオーバー。

## 6. アクションアイテム
- Runbook更新ID: RUN-DATA-05, RUN-DATA-06
- Follow-upチケット: EP01-ING-P2（yfinance実装・自動切替）

## 7. 更新履歴
| 日付 | 更新者 | 内容 |
| --- | --- | --- |
| 2025-03-30 | Codex Liaison | 初版作成 |
