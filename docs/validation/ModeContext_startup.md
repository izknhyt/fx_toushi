# ModeContext Startup Validation Template

Codex実装物の受入時に、`ModeContext`初期化手順（詳細設計 §0.6.9, §3.1）を証跡化するためのテンプレート。各検証項目はCodex着手前チェックリスト (§0.6.9) の番号を`CHK-0.6.9-<n>`として参照し、レビュー記録やCodex Issue/PRコメントから相互リンクできるようにする。

- **データ取得API参照**: DataIngestionServiceのスキャフォールドは`src/data/service.py`、プロバイダスタブは`src/data/providers/`配下に配置し、Manual CSV検証ログは`src/data/quality.py::DataQualityGuard.record_manual_csv_hash_verification`を介して`metrics/`へ追記する。

## 1. 実行マトリクス（CHK-0.6.9-7）
`tradectl start` → `tradectl stop` のフローをモード別に記録し、`logs/ops/session_start.log` と Snapshot 永続化 (`SnapshotManager.persist()`) の証跡を残す。

| Mode | Command | 事前条件 (関連 Runbook) | 期待するログシグネチャ | 証跡リンク | 検証結果 |
| --- | --- | --- | --- | --- | --- |
| backtest | `tradectl start --profile backtest`<br>`tradectl stop` | `config/profiles/backtest.yaml` 更新済み<br>`RUN-TIME-01`/`STRAT-M1-VALIDATION` | `ctx.mode=backtest`<br>`ctx.profile.name=backtest`<br>`deterministic_seed=<int>` | `logs/ops/session_start.log#L<line>`<br>`reports/validation_log/` | [ ] Pass<br>[ ] Fail |
| paper | `tradectl start --profile paper`<br>`tradectl stop` | `config/profiles/paper.yaml` 更新済み<br>`RUN-PERF-01` | `ctx.mode=paper`<br>`ctx.profile.name=paper`<br>`deterministic_seed=<int>` |  | [ ] Pass<br>[ ] Fail |
| live | `tradectl start --profile live`<br>`tradectl stop` | `config/profiles/live.yaml` 更新済み<br>`RUN-RISK-01`/`RUN-BROKER-API-02` | `ctx.mode=live`<br>`ctx.profile.name=live`<br>`deterministic_seed=<int>` |  | [ ] Pass<br>[ ] Fail |

- **Snapshot確認**: 各モード終了後に `SnapshotManager.persist()` が呼び出され、`snapshots/latest/<mode>.json` が更新されたことを記録する（Evidence欄にファイルパスを追記）。
- **CI/自動化**: CI上での実行は`CHK-0.6.9-2`のpytestスモークテストと紐付け、成功ジョブIDを Evidence欄に追記する。

## 2. ModeContext フィールド初期化監査（CHK-0.6.9-6）
`ModeContextFactory`/`ModeController`の初期化項目と `config/profiles/<mode>.yaml` のフィールド対応を確認する。

| Mode | Field | 期待値・検証方法 | 証跡 (テスト or ドキュメント) | 備考 |
| --- | --- | --- | --- | --- |
| backtest | `clock` | `tests/unit/test_mode_context_factory.py::test_backtest_clock_initialization`で`MarketClock.name='ReplayClock'`を確認。 | テストログ、`docs/schemas/mode_context.schema.json#/definitions/MarketClock`検証結果 | `drift_tolerance_ms=0`かつ`supports_halt_windows=false`をassert |
|  | `data_feeds` | `pytest -k json_schema_validation::test_mode_context_contract_accepts_valid_payload` で`DataFeedBundle.primary.channel='file'`を確認。 | JSON Schema検証ログ (`mode_context.schema.json`) | `manual_sources`省略許容を確認 |
|  | `execution_profile` | `tests/unit/test_mode_context_factory.py::test_backtest_execution_profile_defaults`で`allowed_entry_modes`全列挙を確認。 | テストログ、`docs/schemas/mode_context.schema.json#/definitions/ExecutionProfile` | `kill_switch_policies.reduce_only_on_soft_stop`はFalse許容 |
|  | `account_gateway` | Runbook `RUN-ACCOUNT-02` Step 2 のメモ + `pytest -k json_schema_validation::test_mode_context_contract_accepts_valid_payload` | Runbookリンク、Schemaセクション`#/definitions/AccountGateway` | `type='backtest_memory'` |
| paper | `clock` | `tests/unit/test_mode_context_factory.py::test_paper_clock_initialization`で`UtcMarketClock`と`drift_tolerance_ms<=500`を検証。 | テストログ | `supports_halt_windows=true` |
|  | `data_feeds` | `pytest -k json_schema_validation::test_mode_context_contract_accepts_valid_payload` で`fallback`/`manual_sources`必須確認。 | Schemaログ | RateLimitステージ=`baseline` |
|  | `execution_profile` | `tests/unit/test_mode_context_factory.py::test_paper_execution_profile_latency_shape`で`latency_distribution_ms`を検証。 | テストログ | `kill_switch_policies.reduce_only_on_soft_stop`=True |
|  | `account_gateway` | `pytest -k json_schema_validation::test_mode_context_contract_accepts_valid_payload` で`type='paper_simulator'`と`statement_export.frequency='daily'`を検証。 | Schemaログ | |
| live | `clock` | `tests/unit/test_mode_context_factory.py::test_live_clock_initialization`（要作成）で`timezone='UTC'`と祝日配列を検証。 | テストログ | `drift_tolerance_ms<=500` |
|  | `data_feeds` | `pytest -k json_schema_validation::test_mode_context_contract_accepts_valid_payload` で`primary.credentials_ref`必須を検証。 | Schemaログ | `manual_sources`定義あり |
|  | `execution_profile` | `tests/unit/test_mode_context_factory.py::test_live_execution_profile_requires_reduce_only`（要作成）で`allowed_entry_modes`とKill Switch設定を確認。 | テストログ | `allowed_entry_modes`に`limit_requote`必須 |
|  | `account_gateway` | Runbook `RUN-ACCOUNT-02` + `pytest -k json_schema_validation::test_mode_context_contract_accepts_valid_payload` で`type='live_broker'`と`supports_swap=True`を確認。 | Runbookリンク、Schemaログ | |

- 監査観点: `session_state`/`session_handle`/`active_backfill_jobs`は`docs/schemas/mode_context.schema.json`の該当定義で検証し、`tests/schema/test_json_schema_validation.py::test_mode_context_contract_rejects_invalid_payload`で必須項目欠落時の挙動を確認する。証跡は`reports/validation_log/mode_context_<date>.md`に貼付し、Runbook `STRAT-M1-VALIDATION` の`CHK-0.6.9-6`チェックを更新する。

- フィールド検証は `ModeContext.profile` の値も含めて記録し、未検証の場合は備考欄に次アクションを記載する。
- Codex Issue/PRチェックリストに `CHK-0.6.9-6` の完了状態を記載できるよう、証跡ファイル名を統一する（例: `validation/mode_context/2025-03-15_backtest.md`）。
- `EventBus`/`SnapshotManager` 初期化の検証結果は以下のチェックリストで追跡する。

### 2.1 EventBus / SnapshotManager 初期化証跡（CHK-0.6.9-8）

| Component | 検証項目 | 期待する証跡 | 証跡リンク | 検証結果 |
| --- | --- | --- | --- | --- |
| EventBus | インターフェース初期化 (scaffold) | `tests/unit/core/test_event_bus_snapshot_scaffold.py::test_event_bus_publish_placeholder` 実行結果 |  | [ ] Pass<br>[ ] Fail |
| EventBus | `EventBusConfig` パラメータ適用 (`queue_maxsize`, `backpressure_policy`, `metrics_path`) | `config/event_bus.yaml` / `logs/events/YYYYMMDD.jsonl` 初期化ログ |  | [ ] Pass<br>[ ] Fail |
|  | バックプレッシャ設定の証跡 (`QueueDepthHigh`, `DroppedEventWarning`) | `metrics/event_bus_queue.jsonl` / `logs/events/*.jsonl` |  | [ ] Pass<br>[ ] Fail |
| SnapshotManager | インターフェース初期化 (scaffold) | `tests/unit/core/test_event_bus_snapshot_scaffold.py::test_snapshot_manager_persist_placeholder` 実行結果 |  | [ ] Pass<br>[ ] Fail |
| SnapshotManager | アトミック保存ハンドオフ (`SnapshotManager.persist`) | `snapshots/latest/<mode>.json` 更新ログ / `audit` 記録 |  | [ ] Pass<br>[ ] Fail |
|  | 復旧パス確認 (`SnapshotManager.restore`) | `snapshots/latest/event_bus_state.json` / `RUN-DR-04` 証跡 |  | [ ] Pass<br>[ ] Fail |
|  | ハッシュ比較 (`compare_hash`) 証跡 | `reports/validation_log/snapshot_hash_<date>.md` |  | [ ] Pass<br>[ ] Fail |

## 3. Codex着手前チェックリスト連携
| Check ID | 詳細設計 §0.6.9 要件 | 証跡テンプレ位置 | Codexテンプレ参照 |
| --- | --- | --- | --- |
| CHK-0.6.9-1 | `poetry install --no-root` 成功 & `python -m tradectl --help` 0終了 | `reports/validation_log/templates/env_setup.md` (必要に応じ作成) | Codex Issueチェックリスト「環境前提」項 |
| CHK-0.6.9-2 | `pytest -k smoke` スイートがCIテンプレに組み込み済み | `ci/templates/python_smoke.yml` 実行ログ | Codex PRチェックリスト「Tests」項 |
| CHK-0.6.9-3 | レビュー記録/Prompt Packet 格納 | `docs/review_log.md`, `docs/prompt_packages/` | Codex Issueチェックリスト「Review Hand-off」項 |
| CHK-0.6.9-4 | リスク閾値ファイル雛形とスキーマ整合 | `config/` サンプル & `docs/schemas/` | Codex Issueチェックリスト「Risk Controls」項 |
| CHK-0.6.9-5 | Issue/PR テンプレに §0.6.8 番号を引用 | Codex Issue/PR テンプレート | Codex Issueチェックリスト「Checklist」項 |
| CHK-0.6.9-6 | `ModeContext` フィールド初期化証跡 | 本テンプレ §2 | Codex PRチェックリスト「Mode Context」項 |
| CHK-0.6.9-7 | `tradectl start --profile ...` ログ証跡 | 本テンプレ §1 | Codex PRチェックリスト「CLI Evidence」項 |

- 新たに作成したエビデンスファイルは `docs/validation/` 以下に配置し、レビュー記録 (`docs/review_log.md`) から `CHK-0.6.9-<n>` へのリンクを張る。
- Codex側テンプレート（Issue/PRチェックリスト）にチェックを付ける際は、Evidence欄のパス/コミットIDを記入してクロスリファレンスを維持する。

## 4. 更新履歴
- 2025-03-15: 初版作成（Codexハンドオフ監査用テンプレート）
