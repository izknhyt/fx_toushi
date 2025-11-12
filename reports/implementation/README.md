# Implementation Evidence Buckets

Implementation Packetの証跡はすべて本ディレクトリ直下の`<YYYYMMDD>_pkg-<slug>-<nn>/`配下に保管する。詳細設計 §0.6.6〜§0.6.8 および`docs/implementation_packets/TEMPLATE.md`に従い、各サブディレクトリは以下を必須構成とする。

| サブディレクトリ | 用途 | 代表的な格納物 |
| --- | --- | --- |
| `logs/` | `poetry run pytest ...` や `tradectl ...` のCLI出力、`run.log` 等 | `logs/test_run_<timestamp>.txt` |
| `metrics/` | Packet実装で得られた計測データ、メトリクスJSON/CSV | `metrics/backtest_seed_*.json` |
| `cli/` | スクリーンショットやTyperヘルプのサマリなど、UI証跡 | `cli/tradectl_board_snapshot.md` |
| `evidence/` | その他Runbookに添付するファイルや参考資料 | `evidence/screenshot.png`, `evidence/config_diff.md` |

> **運用ノート**: サブディレクトリ内にファイルが無い場合でもGit追跡のため`.gitkeep`を配置している。Packet完了後は実際の成果物へ差し替え、不要な`.gitkeep`は削除して良い。

### 命名規則
- `<YYYYMMDD>`: Packet着手日
- `<slug>`: `docs/implementation_packets/`ファイル名に対応（例: `strat-iface`、`ticket-builder`）
- `<nn>`: 将来バージョンを見越した通し番号。初版は`01`を使用し、追補する際は`02`以降を追加する。

### 追記フロー
1. Packet作成時に該当ディレクトリを用意し、`README.md`や`docs/trader_signoff/<packet>.md`から参照する。
2. Codex作業完了時にCLIログ・検証結果を各サブディレクトリへアップロードし、`docs/review_log.md`の対象行へリンクする。
3. 週次Opsレビューでは`reports/implementation/<packet>/`の更新時刻を確認し、欠落があれば`ops_worklog.jsonl`へTODO登録する。
