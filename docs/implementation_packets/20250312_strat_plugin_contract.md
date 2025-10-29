# Implementation Packet: PKG-STRAT-IFACE-01

## メタデータ
- Epic: EP-02 Strategy Determinism
- Packet範囲: Strategy Plugin Protocol/ベースクラス整備
- 参照セクション: §0.6.11, §3.5.5, §15.2
- 依頼Issue/PR: <TBD>
- 作成日: 2025-03-12
- 作成者: Codex Liaison（SEレビュー指摘#7反映）
- エビデンス格納先: reports/implementation/20250312_pkg-strat-iface-01/

## 1. 目的と背景
- KPI/リスク影響: Backtest/Live決定論一致率>99.5%、StrategyRegistry起動時の契約逸脱Fail-Fast。署名揺らぎによる誤発注・テスト不一致を回避。
- ユーザストーリー/Runbook整合: Runbook `GOV-STRAT-01`と§3.5.5で定義したプラグインチェックリストを実装に落とし込み、Codex PRレビューの自動チェックを可能にする。

## 2. 変更サマリ
| コンポーネント | 変更内容 | テスト指示 | Feature Flag |
| --- | --- | --- | --- |
| src/strategies/base.py | `StrategyContext`（features/regime/gate/account/config/watchlist/clock/seed）と`StrategyMetadata`を`@dataclass(slots=True, frozen=True)`で定義し、`StrategyPluginProtocol`に`evaluate/required_warmup_bars/cooldown_bars`を明示。`Strategy`は後方互換エイリアスに変更。 | `pytest -k strategy_plugin_contract` | N/A |
| src/strategies/registry.py | Manifestロード時にProtocol準拠検査・`StrategyRegistrationError(code='contract_violation')`のFail-Fast実装。 | `pytest -k strategy_registry` | N/A |
| tests/unit/test_strategy_plugin_contract.py | Protocol準拠/seed決定論/ログ付与のスモークテストを追加。 | `pytest -k strategy_plugin_contract` | N/A |
| docs/trader_signoff/PKG-STRAT-IFACE-01.md | CLIスナップショット/Runbookリンク/承認サイン欄を作成。 | `tradectl board --view strategy --save-snapshot ...` | N/A |
| detailed_design_fx_signal_tool_v1.md | §3.3のFeatureContext仕様・§3.5の利用例を整備し、`available_keys`/`get_latest`の契約と必須Featureキー表を追加。 | N/A | N/A |

### 2.1 EntryMode / FillStyle リテラル更新（§3.6, §4.3）
- `EntryMode = Literal["market", "marketable_limit", "limit_requote"]`
  - Ticket Builder / CLIバッジ表示: `Market (IOC)`、`Marketable Limit`、`Limit (Requote)`。
  - 監査: Runbook `RUN-HITL-01` と Validation Log `AC-02_execution_pipeline.md` が同一文字列を要求。
- `FillStyle = Literal["ioc", "fok", "gtd"]`
  - `ExecutionAdjustments.fill_style` と `TradeTicket.entry.fill_style` で共有。CLI出力キーは`fill_policy`。
  - 監査: Validation Log `AC-02_execution_pipeline.md` の `fill_policy` 列で表記一致を検証。

### 2.2 FeatureContext契約更新（§3.3, §3.5）
- `FeatureContext.available_keys` は `<feature>_<tf>`（例: `ema_fast_5m`, `macd_signal_1h`, `donchian_upper_1d`）形式の `frozenset[str]` とし、`StrategyMetadata.required_features` は同一文字列を列挙する。
- `FeatureContext.get_latest(symbol, feature, timeframe)` / `lookup(symbol, feature, timeframe)` をStrategy Pluginが利用するコード例を §3.5 に追加し、`FeatureLookupError`・`FeatureStaleError` をFail-Fastさせる運用を明文化する。
- 指標キーとタイムフレームのマッピング表を §3.3.2 に追加し、Codex 実装者が `metadata.required_features` へ貼り付けるべき文字列を一覧化する。
- dataclass 例: `FeatureFrameView`（`last_updated`, `values`, `latest`, `window`）と `FeatureContext`（`symbols`, `timeframes`, `available_keys`, `frame`, `lookup`, `get_latest`）を提示し、Codex が型シグネチャを迷わないようにする。
- `StrategyContext.watchlist` を `frozenset[str]` で明文化し、Manifestの有効シンボル集合と `FeaturePipeline` からのフォールバック（`feature_frame.symbols`）を組み合わせて算出する手順、および `GateState.market.*` / `GateState.risk.reduce_only` / `GateState.human.double_entry_required` / `RegimeState` による除外ロジックを §3.5.2 に追記する。

### 2.3 Codex Prompt用 StrategyContext 属性一覧（§3.5.5）
- `StrategyContext` が公開するフィールド: `features`, `regime`, `gate`, `account`, `config`, `watchlist`, `clock`, `seed`。Codex プロンプトでは順序と名称を固定化し、`watchlist` を監視対象シンボル集合として参照すること。

### 2.4 GateState伝播（§3.5.2, §3.16）
- `run_signal_cycle` 疑似コードでは`gate_state = GateAggregator.snapshot()`で取得したオブジェクトを保持し、`TicketBuilder.build(sized_signal, execution_adjustments, gate_state_or_slice)`へ第三引数として渡す。`gate_state.market.per_symbol.get(sized_sig.symbol)`が存在する場合はそのスライスを優先し、なければグローバル`gate_state`を渡して`reduce_only`や`double_entry_required`などのフラグが失われないようにする。Workflow/Backtestの双方が同一スナップショットを共有することで、シーケンス図 (§3.5.1) と疑似コード (§3.5.2) のGateState伝播が一致することを保証する。
- `TicketBuilder` 実装では受け取った`GateState`のミュータブル更新を禁止し、シンボルスライスとグローバル制約を統合してChecklist生成・WARNバッジ付与・`TicketBlockedError`判定を行う。Codex実装ではユニットテスト`pytest -k "ticket_builder"`でGateStateの反映を検証すること。

### 2.5 StrategyManifestResolverテスト要件（§3.5.7）
- `tests/unit/test_strategy_manifest_resolver.py::test_effective_symbols_respects_max_watchlist`で`config/profiles/<mode>.yaml::strategy.watchlist_max`を超えるManifestが`ManifestValidationError(code="watchlist_overflow")`をraiseすることを確認する。
- `tests/unit/test_strategy_manifest_resolver.py::test_effective_symbols_prefers_per_symbol_gate`で`gate_state.market.per_symbol['GBPJPY'].halted=True`のとき該当シンボルが除外され、同時に`strategy_manifest.symbol_filtered`ログが出力されることをassertする。
- `tests/unit/test_strategy_manifest_resolver.py::test_effective_symbols_guarded_board_mode`でBoardMode=`guarded`かつManifest `watchlist.allow_guarded=False`の戦略が空集合を返すこと、`allow_guarded=True`の戦略のみ`config/board_modes.yaml::modes.guarded.allowed_symbols`交差後に残ることを検証する。
- `tests/unit/test_strategy_manifest_resolver.py::test_validate_watchlist_feature_gap`でFeaturePipelineに存在しないシンボル/Feature組み合わせが指定された場合に`ManifestValidationError(code="watchlist_missing_feature")`と`strategy_manifest.watchlist_feature_missing`ログが生成されることを確認する。
- `tests/unit/test_strategy_manifest_resolver.py::test_resolve_context_watchlist_returns_frozenset`で`resolve_context_watchlist`が常に`frozenset[str]`を返却し、再評価でも同一インスタンスIDを返さない（コピー生成）ことを`id()`比較でチェックする。

## 3. チェックリスト
- [ ] 設計整合: §3.5.5・§0.6.11と照合し、Protocol/ログ要件を満たす
- [ ] テスト実行: `poetry run pytest -k "strategy_plugin_contract or strategy_registry"`
- [ ] 監査ログ検証: `logs/signals/raw/<date>.jsonl`に`seed`/`feature_sample`が記録されていることを確認
- [ ] Rollback手順記載: docs/governance/feature_flag_register.mdへ「Strategy Plugin Contract」項目を追記
- [ ] Trader Sign-offテンプレ発行: docs/trader_signoff/PKG-STRAT-IFACE-01.md にスクリーンショット・承認サイン
- [ ] FeatureContext契約: `poetry run pytest -k "feature_context_contract"` を将来のCIテンプレに追加し、`available_keys` 表と一致することを確認

## 4. エビデンス
- CLI/スクリーンショット: docs/trader_signoff/PKG-STRAT-IFACE-01.md を参照
- メトリクス: reports/implementation/20250312_pkg-strat-iface-01/metrics/
- ログ: reports/implementation/20250312_pkg-strat-iface-01/logs/

## 5. リスクと依存関係
- 依存Packet: `PKG-BOOT-01`（poetry環境整備）, `SRC-SCAFF-01`（srcディレクトリ雛形）
- 懸念事項/Acceptable Degradationへの影響: Protocol導入により未対応プラグインは起動時に停止するため、Manifestの`enabled`初期値確認が必須。Runbook `RUN-RISK-02`でGuarded移行手順を確認してから有効化する。

## 6. アクションアイテム
- Runbook更新ID: GOV-STRAT-01, RUN-SIGNAL-02
- Follow-upチケット: `DOC-RUNBOOK-ALIGN-02`（テンプレ更新）, `OPS-58`（Issueテンプレ整備）

## 7. 更新履歴
| 日付 | 更新者 | 内容 |
| --- | --- | --- |
| 2025-03-12 | Codex Liaison | 初版作成（SEレビュー#7是正） |

## 8. 進捗管理

M1 スコープで要求されている `pytest -k` コマンドの進捗は次表で管理する。Apple Silicon (M1) 環境での必須テストとして、Codex／Ops が同じ一覧を参照できるよう `tests/README.md` と同期する。

| テスト名 | 目的 | pytest コマンド | 実装状況 |
| --- | --- | --- | --- |
| config_schema_smoke | `config/` 雛形を JSON Schema と突き合わせるスモーク検証。 | `pytest -k "config_schema_smoke"` | 未実装（テスト雛形と config スキーマの整備が未着手）。 |
| data_status_cli | レート制限ステージ評価ログを自動点検し、Ops 手順と同期する。 | `pytest -k "data_status_cli"` | 未実装（CLI／メトリクス連携のコードが未着手）。 |
| strategy_determinism | Backtest / Paper / Live でシグナル決定論を担保する。 | `pytest -k "strategy_determinism"` | 未実装（StrategyEngine 実装とテストが未着手）。 |
| strategy_plugin_contract | Strategy Plugin Protocol への準拠を静的に検証する。 | `pytest -k "strategy_plugin_contract"` | 未実装（Protocol テスト未整備）。 |
| feature_context_contract | FeatureContext/FeatureFrameView の契約と必須Featureキーのセットを検証する。 | `pytest -k "feature_context_contract"` | 未実装（FeatureContextダミー実装とテストが未整備）。 |
| strategy_manifest | `strategy_manifest.yaml` のバリデーションとガバナンス手順の検証。 | `pytest -k "strategy_manifest"` | 未実装（Manifest テスト未整備）。 |
| strategy_registry | Strategy Registry のロードと Fail-Fast 振る舞いを検証する。 | `pytest -k "strategy_registry"` | 未実装（Registry テスト未整備）。 |
| ticket_builder | チケット JSON 整形と HITL UX の要件を検証する。 | `pytest -k "ticket_builder"` | 未実装（Ticket Builder 実装／テストが未整備）。 |
| json_schema_validation | 取引状態およびアカウント関連 JSON Schema の整合性を検証する。 | `pytest -k "json_schema_validation"` | 実装済（`tests/schema/test_json_schema_validation.py`）。 |

> **補足**: 指定された共有スプレッドシートは現時点で提供されていないため、進捗トラッキングは本表および `tests/README.md` を共通の参照点とする。
