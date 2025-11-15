---
id: CR-20250318-PACKET-BACKLOG
status: draft
created: 2025-03-18
owner: Ops PMO
reviewers:
  - Quant Lead
  - Ops Lead
summary: >-
  Inventory of Packet backlog (EP00-P1〜EP05-P1) aligned to the epic deliverable matrix,
  with execution evidence links and log placeholders for absorbing follow-up diffs.
---

# Packetバックログ棚卸し（EP00-P1〜EP05-P1）

## 1. 概要
- エピック別成果物マトリクスに紐づいたPacketの目的・範囲・テストを整理し、`basic_design_fx_signal_tool_v1.md §12.1`へ反映した。
- 各Packetの進捗・担当・証跡リンク・テスト結果を明示し、未着手/進行中のステータスが把握できるようにテーブル化した。
- pytest/CLIログを本ドキュメントへ集約し、設計書・プロンプトパッケージ双方から参照可能なアンカーを用意した。

## 2. Packetインベントリ要約
| Packet | Epic | ステータス | 進捗メモ | 必須テストの現状 |
| --- | --- | --- | --- | --- |
| EP00-P1 | EP-00 Readiness Scaffolding | 進行中 | Backlogテンプレート整備・証跡導線を構築 | `pytest`全体実行済み。ログは§4.1参照 |
| EP01-P1 | EP-01 DataLag Mitigation | 未着手 | RateLimit/CSVハンドリングの実装差分待ち | `pytest -k data_pipeline`は対象テスト未整備でdeselect。§4.2 |
| EP02-P1 | EP-02 Strategy Determinism | 未着手 | 特徴量/戦略決定論テストのドラフトが必要 | `pytest -k strategy_determinism`は対象テスト未整備でdeselect。§4.3 |
| EP03-P1 | EP-03 Guardrails | 未着手 | Health/KillSwitch配線待ち | `pytest -k health_state`は対象テスト未整備でdeselect。§4.4 |
| EP04-P1 | EP-04 Ticket Clarity | 未着手 | Board/チケットUX更新差分待ち | `pytest -k ticket_builder`は対象テスト未整備でdeselect。§4.5 |
| EP05-P1 | EP-05 Weekly Review | 未着手 | Reporterテンプレ整備待ち | `pytest -k reporter`は対象テスト未整備でdeselect。§4.6 |

## 3. 必須テスト指針（エピックマトリクス連携）
- エピック別成果物マトリクス（`basic_design_fx_signal_tool_v1.md` §3.21, §12.1）で定義された必須テストコマンドをPacketごとに再掲し、現状の充足状況を整理。
- テスト未整備のコマンドは**deselect**状態のログを残し、後続タスクが不足箇所を迅速に補填できるようにした。

## 4. テスト実行ログ

### 4.1 `pytest`
```
$ pytest
.......                                                                                                                  [100%]
7 passed in 0.02s
```

### 4.2 `pytest -k data_pipeline`
```
$ pytest -k data_pipeline

7 deselected in 0.02s
```

### 4.3 `pytest -k strategy_determinism`
```
$ pytest -k strategy_determinism

7 deselected in 0.02s
```

### 4.4 `pytest -k health_state`
```
$ pytest -k health_state

7 deselected in 0.01s
```

### 4.5 `pytest -k ticket_builder`
```
$ pytest -k ticket_builder

7 deselected in 0.01s
```

### 4.6 `pytest -k reporter`
```
$ pytest -k reporter

7 deselected in 0.02s
```

## 5. 今後のアクション
1. Packet所有者は本棚卸しテーブルを起点に、該当Packetの`docs/prompt_packages/20250318_packet_backlog.md`テンプレートへ追記を行う。
2. 未整備テストについては対象モジュールの実装計画に合わせてテストケースを補完し、ログがdeselect状態から脱却した時点で本ドキュメントのログを更新する。
3. CLIベースの手動テスト（例: `scripts/qa/manual_csv_smoke.sh`）が整備され次第、§4へコマンドログを追記し§2・§3のステータスを更新する。
4. 詳細設計書の§9および§22〜§26の重複ブロックは`CR-20250320-SECTION-COMMON-SPEC`で共通仕様へ統合予定。差分吸収後は本バックログから該当セクション差分メモを削除する。【F:docs/change_requests/CR-20250320-section_common_spec.md†L1-L108】
