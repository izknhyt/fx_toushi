---
id: CR-20250320-SECTION-COMMON-SPEC
status: draft
created: 2025-03-20
owner: Ops PMO
reviewers:
  - Documentation WG
  - Quant Lead
summary: >-
  Plan to deduplicate repeated operational design sections (§9, §22–§26) into a
  single shared source with a "共通仕様" hub and epic-specific deltas.
---

# 詳細設計セクション統合計画（§9, §22〜§26）

## 1. 背景と目的
- `detailed_design_fx_signal_tool_v1.md`のテスト計画（§9）が文書内に二重で掲載されており、表やKPI基準が完全に重複している。【F:detailed_design_fx_signal_tool_v1.md†L1556-L1895】【F:detailed_design_fx_signal_tool_v1.md†L2759-L3093】
- 同文書のOps強化エピック群（§22〜§26）も同一内容が二度繰り返されており、将来の差分編集時に同期漏れのリスクが高い。【F:detailed_design_fx_signal_tool_v1.md†L1771-L2315】【F:detailed_design_fx_signal_tool_v1.md†L2974-L3518】
- 重複のままではChange Request/Runbookからの参照先が複数存在し、更新時にリンクずれや改訂漏れが発生するため、原本を1箇所に集約する。

## 2. 対象範囲
1. `detailed_design_fx_signal_tool_v1.md`
   - §9 テスト計画とカバレッジ
   - §22 Opsシミュレーションゲーム設計
   - §23 リサーチ/運用エビデンスグラフ統合
   - §24 Acceptable Degradation Analytics & Recovery Toolkit
   - §25 Codexデリバリーコントロールタワー
   - §26 トレーダーフィードバック循環エンジン
2. 参照側ドキュメント
   - `docs/change_requests/CR-20250313-test_cli_gap.md`（§9, §22〜§26参照あり）【F:docs/change_requests/CR-20250313-test_cli_gap.md†L3-L206】
   - `docs/change_requests/20250318_packet_backlog.md`（各エピックの参照行を持つ）【F:docs/change_requests/20250318_packet_backlog.md†L24-L33】
   - `docs/prompt_packages/20250318_packet_backlog.md`（エピック別リンク）【F:docs/prompt_packages/20250318_packet_backlog.md†L26-L87】
   - `docs/knowledge_packs/README.md`（§22, §23参照）【F:docs/knowledge_packs/README.md†L5-L90】
   - `docs/runbooks/*`で該当セクション番号を引用している箇所（例: `RUN-OPS-05`, `RUN-RISK-01`等）。

## 3. 統合方針
### 3.1 共通仕様ハブの新設
- §9と§22〜§26について、重複部分をそれぞれ1箇所に集約し、節冒頭に`### 共通仕様`サブセクションを新設する。
- 共通仕様には、テストテーブル、モジュール構成、テレメトリ要件など、全エピックに共通する記述を集約する。
- 共通仕様直下に`#### Epic別差分`配下のサブセクション（例:`#### EP-03 Guardrails向け差分`）を設け、差分が必要な場合のみ記載する。現時点で差分が無い節はプレースホルダを置かず、将来追加時にのみ増設する。

### 3.2 アンカーと参照の維持
- 既存の節番号（§9, §22〜§26）は維持し、内部アンカーを`#共通仕様`などに変更して外部リンク互換性を確保する。
- 各節末尾にあった「実装状況メモ」テーブルは共通仕様内に一本化し、Epicごとの差分がある場合のみ`Epic別差分`側で更新する。
- 章内で互いに参照している箇所（例: §24→GameEngine (§22)）は共通仕様のサブセクション名を参照するように更新する。

### 3.3 差分抽出と再配置手順
1. 既存節を`Common`ブロックと`Epic-specific`ブロックに仮分解するため、`python`スクリプトか`awk`でサブヘッダを解析し、重複範囲を確認する。
2. 初回出現ブロックを「原本」とみなし、そこへ`### 共通仕様`サブヘッダを挿入し、内容を保持する。
3. 2度目に出現するブロックを削除し、必要に応じて`#### <Epic>`サブセクションを追加して差分のみを記述する。
4. 将来差分が期待される節には、コメントではなく文章で「現時点で差分なし」と記載しておく。

## 4. クロスリファレンス更新計画
1. `docs/change_requests/CR-20250313-test_cli_gap.md`
   - テーブル見出しを新しい共通仕様アンカーに更新し、節番号は維持。
2. `docs/change_requests/20250318_packet_backlog.md`
   - Epic表内の`§9`や`§22`参照を共通仕様または該当差分サブセクションに更新。
3. `docs/prompt_packages/20250318_packet_backlog.md`
   - 各Promptセクションで参照するリンクを新しいアンカー（例:`#共通仕様`や`#ep-03-guardrails`)に置換。
4. Runbook群 (`RUN-OPS-05`, `RUN-RISK-01`, `RUN-HITL-01`, `RUN-SPREAD-03`, `RUN-DATA-06`, `RUN-OPS-02`, `RUN-OPS-04`, `RUN-PERF-01`, `RUN-REL-01`, `RUN-DATA-05`) に存在する該当節番号参照を`共通仕様`導入後のアンカーへ更新。
5. `docs/knowledge_packs/README.md`と関連テンプレートからの節参照を点検し、共通仕様に一本化する。
6. その他`rg "§2[2-6]"`でヒットしたファイルを棚卸しし、リンクの重複/破断がないか確認する。

## 5. 実施ステップ
1. `detailed_design_fx_signal_tool_v1.md`の該当節から重複ブロックを削除し、共通仕様構造へ再編。
2. 参照先ドキュメントを網羅的に更新し、PRでリンクチェッカまたはローカルスクリプトを用いて壊れたアンカーがないか確認。
3. `docs/change_requests/20250318_packet_backlog.md`へ「§9/§22〜§26重複ブロックの共通仕様化により差分が1箇所に集約された」旨のメモを追記。
4. Change Request `CR-20250320-SECTION-COMMON-SPEC`をレビューに回し、承認後に実装へ着手。

## 6. リスクとフォローアップ
- **リンク断**: 節見出しを変更する際、既存の`#`アンカーが変化しないよう、必要であればHTMLアンカー（`<a id="...">`）を併設する。
- **将来差分の混在**: Epic別差分サブセクションの導入基準をドキュメント化し、共通仕様に含めるべき内容と個別差分を明確化する。
- **レビュー負荷**: 影響ファイルが多いため、PRでは`docs/`配下のリンクテスト手順を明示し、レビューアが差分確認しやすいように段階コミットを検討する。

## 7. 完了判定
- `rg "## 9. テスト計画とカバレッジ" detailed_design_fx_signal_tool_v1.md`が単一ヒットとなり、§22〜§26もそれぞれ1回のみの出現に減少していること。
- `docs/change_requests/20250318_packet_backlog.md`に共通仕様化のメモが追加されていること。
- 主要Runbook/Change Request/Prompt Packageで更新後のアンカーへ正常にジャンプできることを手動確認またはリンクチェッカで証明する。

## 8. タイムライン（目安）
| フェーズ | 目安 | 内容 |
| --- | --- | --- |
| 調査完了 | 2025-03-20 | 重複箇所の棚卸しと計画策定（本ドキュメント）。 |
| 実装ドラフト | 2025-03-22 | 共通仕様再編＋主要参照更新。 |
| レビュー | 2025-03-23 | 文書レビュー/リンクチェック。 |
| クローズ | 2025-03-24 | Change Request承認・マージ。 |

