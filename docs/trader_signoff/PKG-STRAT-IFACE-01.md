# Trader Sign-off: PKG-STRAT-IFACE-01

## メタデータ
- Packet: PKG-STRAT-IFACE-01 (Strategy Plugin Protocol整備)
- レビュアー: <Trader/Ops TBD>
- セッション日時: <YYYY-MM-DD HH:MM JST>
- 実施モード: <Backtest/Paper/Live>
- エビデンス格納先: docs/trader_signoff/PKG-STRAT-IFACE-01/assets/

## 1. チェックリスト (詳細は§12.3)
- [ ] A1 CLIレンダリング: `tradectl board --view strategy --strategy-id <id> --save-snapshot docs/trader_signoff/PKG-STRAT-IFACE-01/assets/board_<id>.json`
- [ ] A2 Ops Worklog連携確認（`ops_worklog`に`strategy_execution`レコードが生成されている）
- [ ] A3 メトリクス整合確認（`metrics/strategy_execution.jsonl`に`seed`/`duration_ms`が出力されている）
- [ ] A4 Rollback試行（Manifest `enabled`切替→`tradectl config sync`→CLI再起動）
- [ ] A5 Runbook更新差分確認（`GOV-STRAT-01`/`RUN-SIGNAL-02`）

## 2. 所要時間
- 操作開始: <HH:MM>
- 操作終了: <HH:MM>
- 実作業時間 (分): <value>

## 3. コメント
- Positive:
- Findings/Issues:
- Follow-up希望:

## 4. スクリーンショット/ログ
- CLIキャプチャ: assets/board_<id>.json
- メトリクス抜粋: assets/metrics_snapshot.md
- Rollbackログ: assets/rollback_log.txt

## 5. サインオフ
- 判定: <approve/hold/reject>
- 署名: <name>
- 更新履歴:
  - 2025-03-12 Codex Liaison 初版作成（SEレビュー#7フォロー）
