# Review Log

週次・月次・四半期レビューの記録と、コメント欄責務/締切の証跡を管理する。記載内容は週次レポート`reports/weekly/<YYYY-WW>.md`およびOpsアジェンダと双方向に同期する。

## 記録ルール
- **更新タイミング**:
  - 週次レビュー: 毎週月曜 09:00 JST 開催前までに最新週のエントリを作成する。
  - 月次レビュー: 第1営業日夜のレビュー完了後24時間以内。
  - 四半期レビュー: 最終営業週のセッション当日中。
- **記入権限**:
  - Quant Lead: A/Bテスト結果、研究関連のインサイト。
  - Ops Manager: Opsアジェンダ、次週ToDo、Runbookの実行状況。
  - Product Owner: 決裁コメントとKPI評価サイン。
- **差分管理**: 締切後の修正は`Update:`エントリとして追記し、誰がいつ修正したかを明記する。Gitログと併せて監査する。

## 週次レビューエントリ テンプレート
```
### <YYYY-WW> Weekly KPI Review
- Reporter: Ops Manager
- Report Source: reports/weekly/<YYYY-WW>.md (generated <YYYY-MM-DD HH:MM JST>)
- A/Bテスト結果 (Quant Lead, due Sun 18:00 JST)
  - Summary: <必須>
  - Evidence: <link to experiment artifacts>
  - Review Log ID: AB-<YYYY-WW>
- 次週ToDo (Ops Manager, due Mon 08:30 JST)
  - Priority Items: <必須>
  - Linked Runbooks: <RUN-PERF-01 / RUN-RISK-01 / others>
  - Ops Agenda Export: `docs/runbooks/daily_agenda/<YYYY-MM-DD>.md`（テンプレ: `docs/runbooks/daily_agenda/TEMPLATE.md`）
- KPI Sign-off (Product Owner, due Mon 12:00 JST)
  - Decision: <approve / hold / escalate>
  - Notes: <optional>
- Follow-up Tickets
  - [ ] <ticket placeholder>
  - [ ] <ticket placeholder>
```

## 月次・四半期エントリ
- 月次: `### <YYYY-MM> Monthly KPI Review`を見出しにして週次テンプレートの`A/Bテスト結果`欄を「主要改善テーマ」に置き換える。
- 四半期: `### <YYYY-Q> Quarterly KPI Review`としてBacktest/SLA結果、SLAプロファイル更新状況、Runbookサイン記録を追記する。

## Opsアジェンダ連携
1. Ops Managerは`tradectl ops agenda --date <YYYY-MM-DD>`を実行し、生成されたMarkdownを`docs/runbooks/daily_agenda/`へ保存する（テンプレ `TEMPLATE.md` を起点に`CHK-0.6.9-*`欄を更新）。
2. 保存したファイルを上記テンプレートの「Ops Agenda Export」にリンクし、ToDo欄と整合させる。
3. Agendaの「ModeContext Startup Walkthrough」セクションで更新した証跡は`docs/validation/ModeContext_startup.md`の該当行へリンクし、次週レビュー時に`CHK-0.6.9-6/7`の状態を確認する。
4. Agendaに未完了タスクがあれば次週ToDo欄へ転記し、完了済みタスクはOps Worklogへログする。
5. 未完了チェックボックスを`tradectl ops action-sync --review-log docs/review_log.md --agenda docs/runbooks/daily_agenda/<date>.md --out docs/change_requests/CR-<date>-ops-followups.md`で抽出し、Change RequestとAgenda埋め込みブロックを同時更新する。
6. フォローアップ完了時は本エントリへ`Closed #<n>`を追記し、`logs/ops/review.log`へ同じIDの行を追加する（RUN-POST-03参照）。

## 監査リンク
- 週次コメント締切超過時は`reports/validation_log/AC-45_sla_<date>.md`に遅延理由を記録する。
- 実験結果が承認されなかった場合は`reports/research/m1_baseline/validation_<date>.md`に原因を追記し、次週のレビューでフォローアップする。

## 特別レビュー記録

### 2025-03-10 Detail Design Review (Special)
- Reviewer: SE/Trader Lead（Codex Liaison同席）
- Scope: `detailed_design_fx_signal_tool_v1.md` v1.28（§0.6〜§1.3・§79）とリポジトリ初期状態の実査
- Findings Summary:
  - `pyproject.toml`欠落・ソーススキャフォールド未整備・テスト雛形未整備など、設計と実装準備のギャップを5項目抽出（§0.6.8参照）。
  - Broker Adapterメタデータは`EndpointSpec`のみ実装済みであり、`FieldMapping`/`RateLimitSla`定義が不足（§79.1注記）。
- Follow-up Packets: `PKG-BOOT-01`, `SRC-SCAFF-01`, `TEST-SMOKE-01`, `BROKER-META-01`（起票担当: Codex Liaison, 締切: 2025-03-12 JST EOD）
- Ops Agenda Sync: Ops Managerが`OpsAgendaService`へTODO登録済み（Ref: agenda entry OPS-2025-03-11-01）
- Next Review Gate: 2025-03-14 スプリント計画レビューで是正状況を確認し、未完了項目は`docs/change_requests/`で正式化する。

### 2025-03-11 Detail Design Review (Follow-up)
- Reviewer: SE/Trader Lead
- Scope: `detailed_design_fx_signal_tool_v1.md` v1.28（§0.6.8, §4.2, §4.4）
- Findings Summary:
  - `config/`ディレクトリと設定YAML雛形が欠落しており、設計記載のスキーマ検証が実行できないギャップを確認。`CONFIG-SCAFF-01` Packetを新規追加し、`docs/schemas/`へのリンクとスモークテスト（`pytest -k config_schema_smoke`）を要求。
  - `SpreadCooldownState`の値域が記述上のみで型定義されておらず、Codex実装時の齟齬リスクがあるため、`Literal`による型エイリアスを詳細設計へ追記。
  - 設定ファイルセクションで`cfg.schema.json`の参照先が曖昧だったため、`docs/schemas/`配下の実体とRunbook/テスト導線を明示。
- Follow-up Packets: `CONFIG-SCAFF-01`（新規, 起票担当: Codex Liaison, 締切: 2025-03-13 JST EOD）
- Status Update (2025-03-13): `config/risk_policy.yaml` の雛形を作成し、Spread/Kill Switch主要閾値をコメント付きで整備済み。
- Update (2025-03-14): `ci/templates/python_smoke.yml` を追加し、README/詳細設計§0.6.9の前提どおり `poetry install --no-root` → `pytest -k smoke` を実行するCIテンプレートをパイプライン対象に登録。失敗時の検証ログは`python-smoke-logs`アーティファクトで保存するよう構成。
- Ops Agenda Sync: Ops ManagerがOPS-2025-03-12-02へTODO追記済み
- Next Review Gate: 2025-03-15 Codexスプリントキックオフで前提条件チェック（§0.6.9）を再実施

### 2025-03-12 Detail Design Review (Strategy/Risk Alignment)
- Reviewer: SE/Trader Lead（Codex Liaison立会い）
- Scope: `detailed_design_fx_signal_tool_v1.md` v1.29草案（§0.6.8〜0.6.11, §3.5, §3.6, §7.x）、`docs/implementation_packets/`
- Findings Summary:
  - Strategy Plugin契約（Protocol/決定論シード）が暗黙的で、Codex実装時に署名不一致・乱数非決定論のリスクがある。§3.5.5を新設して`StrategyContext`/`StrategyMetadata`/ログ要件を明文化し、Implementation Packet `PKG-STRAT-IFACE-01`を起票。
  - シグナル疑似コード（§3.5.2）が`ExecutionModel.apply`の入出力と乖離し、Spread/Market Snapshotを未取得のまま呼び出していた。API整合のため疑似コードを更新し、`ModeContext`/Spread状態の明示的受け渡しを追加。
  - 週次レポート受入条件の証跡がRunbook/ログ/テンプレートに分散していた。§0.6.11/§7.6でCLIスナップショット・`signal_cycle_snapshot`ログ・`metrics/strategy_execution.jsonl`抽出を必須化。
- Follow-up Packets: `PKG-STRAT-IFACE-01`（新規）, `DOC-RUNBOOK-ALIGN-02`（テンプレ更新）, Issue `OPS-58`（Codex Issueテンプレ追補）
- Ops Agenda Sync: OPS-2025-03-13-01 に #7〜#9 の追跡項目を登録済み（Ops Manager）
- Next Review Gate: 2025-03-19 週次Opsレビューでフォローアップ完了確認。未完の場合は`docs/change_requests/`へ正式エントリ化。

### 2025-03-15 M1 Test Coverage Kick-off
- Reviewer: Ops Manager / Codex Liaison
- Scope: `tests/README.md` M1 必須 `pytest -k` 行、詳細設計 §3.0〜§3.5・§4.4・§6.7・§15.2・§16.5
- Actions:
  - `PKG-CONFIG-SCHEMA-01`, `PKG-DATA-STATUS-01`, `PKG-STRAT-DETERMINISM-01`, `PKG-FEATURE-CONTEXT-01`, `PKG-STRAT-MANIFEST-01`, `PKG-STRAT-REGISTRY-01`, `PKG-TICKET-BUILDER-01`, `PKG-JSON-SCHEMA-01` を起票。各Packetは `docs/implementation_packets/` 配下に格納し、対応する `pytest -k` プレースホルダーを `xfail(strict=True)` で追加。
  - 既存Packet `PKG-STRAT-IFACE-01` の進捗表を更新し、`tests/README.md` と実装状況を同期。
  - Ops Agenda `docs/runbooks/daily_agenda/2025-03-15.md` を作成し、上記Packetリンクと `tests/README.md` 行番号を紐付け。
- Ops Agenda Sync: `docs/runbooks/daily_agenda/2025-03-15.md`
- Next Review Gate: 2025-03-18 週次Opsレビューで各Packetのテスト実装着手状況を確認。

### 2025-03-17 ModeContext & Risk Validation Sync
- Reviewer: Ops Manager / Codex Liaison
- Scope: CHK-0.6.9-3/4/5 前提条件（ModeContext起動証跡、リスク設定スキーマ、Issueテンプレ参照）
- Findings Summary:
  - ModeContext起動ログとスナップショットをBacktest/Paper/Liveで取得し、`docs/validation/ModeContext_startup.md`および`reports/validation_log/CHK-0.6.9_mode_context_20250317.md`へリンクした。
  - `config/risk_policy.yaml`と`config/risk_live_guard.yaml`をJSON Schemaで検証し、GateStateの`market.news.blocked`/`risk.reduce_only`/`human.double_entry_required`フィールドと整合することを確認（Evidence: `reports/validation_log/CHK-0.6.9_risk_schema_20250317.md`）。
  - Codex IssueテンプレートのCHK一覧に§0.6.8参照記載欄を追加し、前提条件ごとの証跡パスを必須化。
- Ops Agenda Sync: `docs/runbooks/daily_agenda/2025-03-17.md`
- Next Review Gate: 2025-03-20 Weekly Ops Review（CHK-0.6.9完了確認とFR-28 Validation Data Playbookの追跡）

### 2025-03-18 ModeContext / Ops Readiness Refresh
- Reviewer: Ops Manager / Risk Officer
- Scope: CHK-0.6.9-1/2/6/7再実行、Spread/Funding・Snapshot復旧タスクの前提整理、リスクログ更新
- Evidence:
  - `reports/validation_log/CHK-0.6.9_env_setup_20250318.md`
  - `reports/validation_log/CHK-0.6.9_mode_context_20250318.md`
  - `docs/runbooks/daily_agenda/2025-03-18.md`
  - `docs/risk_review/20250318_prelaunch.md`
- Decisions:
  - Spread/Funding CSV自動化（RUN-FUND-01改訂）、Snapshot復旧演習（RUN-TIME-01改訂）、オンコールEvidence（R-02）をOps Agendaへ登録。
  - `detailed_design_fx_signal_tool_v1.md` §11にリスクOwnerと期限を明記し、Ops/Quant/POへの責務割当を完了。
- Next Review Gate: 2025-03-25 Ops Weekly（R-02/R-05 Evidence確認）

### 2025-03-23 Detailed Design §11 Follow-ups (Pre-Sign-off)
- Reviewer: Codex Liaison / Ops Manager
- Scope: `detailed_design_fx_signal_tool_v1.md` §11 リスクログおよびRunbook追記タスク
- Follow-up Items:
  - [ ] Runbook `docs/runbooks/RUN-EXEC-02.md` に「Paper/LIVE 実績に基づく半月ごとの `execution_model.yaml` 更新」手順を追記（Owner: Quant Lead, Due: 2025-03-28 JST, Ref: §11.1 技術的リスク 1行目）
  - [ ] リスクログ `R-02`（運用者不在時のアラート未対応）: オンコール表整備と `RUN-EMER-UNWIND-01` 訓練ログ Evidence 登録をチケット化（Owner: Ops Manager, Due: 2025-03-25 JST, Evidence: §11.3 R-02）
  - [ ] リスクログ `R-05`（監査ログ肥大化）: ログ圧縮ジョブ自動化と `RUN-AUD-02` 反映をチケット化（Owner: Lead Engineer, Due: 2025-03-29 JST, Evidence: §11.3 R-05）
  - [ ] リリース計画ドキュメント（`docs/release_checklist.md` 相当）不在：詳細設計 §13/§31 のゲート手順を参照する正式なチェックリストファイルを作成し、節番号整合を確認（Owner: Product Owner, Due: 2025-03-27 JST, Notes: Release plan cross-checkで欠損を確認）
- Notes:
  - Codex実装パケット各資料のセクション参照は`detailed_design_fx_signal_tool_v1.md`の実際の節番号と整合していることを確認済み（§0.6.11, §3.5.5, §16.5 等）。
