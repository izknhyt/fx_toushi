# Implementation Packet: PKG-TRADECTL-STATUS-RESYNC-01

## メタデータ
- Epic: EP-03 Guardrails / Data Reliability
- Packet範囲: `tradectl status` Acceptable Degradationバナー整備、`tradectl resync` Progressスタブ
- 参照セクション: detailed_design_fx_signal_tool_v1.md §17.3, §17.4
- 依頼Issue/PR: <TBD>
- 作成日: 2025-03-22
- 作成者: Codex Liaison
- エビデンス格納先: reports/implementation/20250322_pkg-tradectl-status-resync-01/

## 1. 目的と背景
- KPI/リスク影響: Acceptable Degradation運用時に`tradectl status`でRunbook参照とReduce-Only状態を即座に共有し、Ops意思決定を迅速化する。Resync指示では`SessionManager.catch_up`呼び出し有無を明示し、未配線環境でも進捗が把握できるようにする。
- ユーザストーリー/Runbook整合: `RUN-DATA-05`/`RUN-DATA-06`のチェックリストへCLI出力を貼付する要件を満たし、Codex実装時にKill Switch/Board操作フックを差し替え可能にする。

## 2. 変更サマリ
| コンポーネント | 変更内容 | テスト指示 | Feature Flag |
| --- | --- | --- | --- |
| src/interfaces/cli/status.py | Health/Gate/Snapshot集約・`ops.banner.kind=acceptable_degradation`の導入 | `pytest tests/unit/test_cli_status.py` | N/A |
| src/interfaces/cli/resync.py | Progress表示と`SessionManager.catch_up`ハンドオフの例外処理スタブ | `pytest -k "smoke and feature_context_contract"` | N/A |
| src/interfaces/cli/__init__.py<br>src/interfaces/cli/main.py | Typer/Rich構成の`tradectl`エントリーポイントを追加し、`--json`/`--verbose`をサポート | `python -m tradectl --help`（手動） | N/A |
| docs/runbooks/RUN-DATA-05.md<br>detailed_design_fx_signal_tool_v1.md | Acceptable DegradationバナーとResyncステータスのサンプル出力を追記 | N/A | N/A |

## 3. チェックリスト
- [ ] 設計整合: detailed_design_fx_signal_tool_v1.md §17.3/§17.4 を確認
- [ ] テスト実行: `poetry run pytest tests/unit/test_cli_status.py`、`poetry run pytest -k "smoke and feature_context_contract"`
- [ ] 監査ログ検証: Ops日誌に`tradectl status --json`抜粋を貼付し、`ops.banner.runbook`がRunbook IDを指していることを確認
- [ ] Rollback手順記載: docs/runbooks/RUN-DATA-05.md のバージョン差分をDocOpsへ通知
- [ ] Trader Sign-offテンプレ: docs/trader_signoff/TEMPLATE.md に`tradectl status --json`貼付欄を追加（別チケット）

## 4. エビデンス
- CLI/スクリーンショット: reports/implementation/20250322_pkg-tradectl-status-resync-01/cli/
- メトリクス: reports/implementation/20250322_pkg-tradectl-status-resync-01/metrics/
- ログ: reports/implementation/20250322_pkg-tradectl-status-resync-01/logs/

## 5. リスクと依存関係
- 依存Packet: PKG-DATA-STATUS-01（データSLA CLIスタブ）
- 懸念事項/Acceptable Degradationへの影響: バナーキーが欠落するとOpsがRunbook参照を見落とし、Guarded解除やKill Switch判断が遅延する恐れ。

## 6. アクションアイテム
- Runbook更新ID: RUN-DATA-05, RUN-DATA-06
- Follow-upチケット: CLI-OPS-ACTIONS（`ops.actions`をイベント実行へ昇格）

## 7. 更新履歴
| 日付 | 更新者 | 内容 |
| --- | --- | --- |
| 2025-03-22 | Codex Liaison | 初版作成 |
