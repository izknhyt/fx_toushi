# FXヒューマン・インザループ投資ツール 基本設計書 v1.4

## 0. 文書情報
- 作成日: 2025-02-20
- 作成者: Codex AI 支援
- 参照文書: `要件定義（テンプレ形式）v_1.md`
- 想定リリース: マイルストーンM1 Core（M1.0）

### 0.1 改訂履歴
| 版 | 日付 | 改訂概要 |
| --- | --- | --- |
| v1.4 | 2025-02-25 | 要件v1.4対応。M1を「M1 Core/M1.1 Hardening」に再分解し、Signal BoardのUXフロー・データスキーマ・SQLite/Parquetインデックス設計・Validation Data Playbook連携を追記。戦略ロードマップの検証窓・担当責務と整合させ、Paper運用90日→Live移行のゲートを再定義。 |
| v1.3 | 2025-02-24 | 要件v1.3対応。戦略スコアボード/アルファ評価、オポチュニティ・パイプライン、オペレーションレディネス/モデルリスク管理を追加し、研究レビュー/昇格ガバナンスの役割分担とデータストア構造を明文化。 |
| v1.2 | 2025-02-23 | 要件v1.2対応。ストレステスト/ベンチマーク/ジャーナル/緊急プロトコル/可観測性強化の設計を追加し、M1〜M3の役割整理とRunbook連携を追記。 |
| v1.1 | 2025-02-20 | 要件差分レビュー結果を反映。コスト/執行モデル、ヒューマンエラー抑止、スプレッドクールダウン、Reduce-Onlyセーフティ等の設計を具体化し、トレーサビリティを拡充。 |
| v1.0 | 2025-02-15 | 初版作成 |

## 1. システム概要
- 目的: 主要FXペアに対する裁量支援（HITL）トレードを自動化された分析と提案で補助し、Sharpe/Sortino/最大DDなどのKPIを達成する。
- 競争優位: 市販FXシグナルツールをベンチマークとし、Sharpe/最大DD/提案レイテンシで常時上回ること、ストレスシナリオでも崩れにくい運用体制を実現する。
- ユーザー: 個人トレーダー（プロダクトオーナー）
- 運用形態: macOS上でPython 3.11アプリケーションとして稼働。PC稼働時のみオンライン。
- 稼働モード: Backtest / PaperTrade / LiveTrade の3モードを共通コードベースで提供。
- 投資対象: USDJPY, EURUSD, GBPUSD, EURJPY (MVP)。
- 配布/復旧: `poetry install --sync`によるオンライン展開と、依存Wheel・SBOM・ハッシュリストを束ねた`dist/offline_bundle/<version>.tar.gz`を毎リリース生成し、DR手順`DR-LOCAL-01`で4時間以内に代替マシンへ復旧できるよう設計する。

### 1.1 マイルストーン適用範囲
- **M1 Core (M1.0)**: FR-01〜FR-08, FR-10, FR-18にフォーカスし、データ取得/品質監視、MA+RSIベースのシグナル生成、Kill Switch・リスク制御、HITLチケット（承認/却下/編集）、Resync & Snapshot、週次レポート（**M1 Coreテンプレート: Sharpe/最大DD/WinRate/累積Rのみ**）を実装。監査/署名/高度ガバナンスは敢えて外し、Paper 90営業日運用とオペレーションスループット測定に集中する。Data Ingestionは**常時4ペア並列取得と30分以内のCatch-up完了**をKPI化し、SLAターゲット自体は**計測・逸脱検知・手動フェイルオーバードリルの確立**を完了条件とする（Runbook `RUN-DATA-05/06`）。`HealthMonitor`はp95/p99遅延に加えて429/403レート制限イベントを検知し、`reason=rate_limited`を付与して自動的にポーリング間隔を倍化する。実測が閾値未達の場合は`HealthState=degraded(reason=data_latency_fetch|processing)`でAcceptable Degradation運用（代替ソース＋手動CSVで主要4ペア継続）へ移行し、Signal Boardは`BoardMode=guarded`へ遷移して**主要4ペアの新規提案を「要ダブルチェック」バナー付きで提示し続ける**。自動承認や一括承認はロックするが、監査付きの単票承認は継続可能とし、承認時に`manual_review.required=true`のチェックリストを強制する。復旧計画は7日以内に提示し、`board_guarded`解除条件（後述）を満たすまでバナーを維持する。`degraded`が**連続3営業日またはローリング30日で2回**発生した場合はOps Manager主導でエスカレーションレビューを開き、`reports/ops/incidents`へ暫定策とETAを記録する。**5営業日超継続または週次レビュー2回未解消**でKill Switchを`hard_stop`へ昇格し、手動CSV運用とRunbook `RUN-DATA-06`に限定する。復旧は`catch_up_lag_minutes<30`とSLAターゲット復帰、手動CSV二重入力ハッシュ一致とPO/Opsサインを条件とする。週次レポートとKPI出力では`metric_state ∈ {confirmed, provisional, pending}`を明示し、Paper初期90営業日は暫定値＋手動レビューコメントのみを必須とする。Alpha Scoreboard/Idea Pipeline等のM2ガバナンス機構はスタブ化してFeature Flagを既定OFFで維持し初期リリースの複雑化を避ける。
- **M1.1 Hardening**: FR-09, FR-11〜FR-18, FR-23, FR-27, FR-30, FR-38, FR-44を追加し、監査ログ冗長化、設定ガバナンス、回帰テスト、Paper-Liveパリティ、ニュースガード/Spread Cooldown、Validation Data Playbookによるデータ整備、スナップショット/バックアップ強化を完了する。AC-08およびAC-12〜AC-45をカバーし、Live少額トライアルのゲートを準備する。
- **M2 (強化フェーズ)**: ハイブリッド最適化、レジーム検出、SPRT自動制御、リアルタイムスプレッド/API連携、Reduce-Onlyアドバイザ本運用、ストレステスト/ジャーナル自動化、戦略スコアボード算出・可視化、オペレーションレディネス指標集計、緊急プロトコル、ブローカーステートメント突合、オポチュニティ・パイプライン、モデルリスクレジスター連携、ベンチマーク差分の可視化。
- **M3 (拡張フェーズ)**: マージン/レバレッジ自動制御の高度化、相関合算Rによるポートフォリオ制御、GUI/Tauri化、ブローカーAPIによる自動発注拡張、ベンチマークリプレイ強化、運用健全性ダッシュボード高度化、戦略スコアボードによる昇格ゲート制御、オポチュニティ・パイプラインのフルワークフロー化。

#### 1.1.1 前提ファイルと準備タイミング
| マイルストーン | ファイル/ディレクトリ | 主な用途 | 推奨準備時期 |
| --- | --- | --- | --- |
| M1 Core | `config/broker_rules.yaml` | Broker Rules Loader/Spread Monitor/Execution Modelが参照するブローカー仕様の正本。 | M1 Coreローンチ前1週間までに整備とレビューを完了し、AC-11サインオフを支援する。 |
| M1.1 Hardening | `reports/validation_log/AC-*.md` | Validation Data Playbookの証跡として受け入れテストとサインオフを保管。 | M1.1回帰テスト開始の1週間前までにテンプレート整備と初期サインを完了。 |
| M2 | `data/liquidity_monitor.parquet` | Liquidity Intelligence Serviceの閾値計測・乖離監視データ。 | M2流動性演習（FR-49）に着手する3週間前からデータ取得ジョブを常時稼働させる。 |
| M2 | `config/emergency.yaml` | Emergency Orchestrator/Reduce-Only Advisorのシナリオとアクション定義。 | M2緊急対応ドリルの初回実施（月次レビュー前）までにドラフトを確定し、Runbook承認を得る。 |
| M2 | `reports/governance/ops_readiness_<YYYYWW>.md` | Ops Readiness Evaluator用の週次スコアシートと証跡リンク。 | M2リリースゲート適用の4週間前から毎週金曜に更新し、不足項目を翌週の準備タスクへ反映する。 |

#### 1.1.2 M1 Coreスコープガードレール

- **目的**: M1 Coreでは「稼働に不可欠な10要件」に集中し、ガバナンス/分析拡張の作り込みによる初期負荷を排除する。詳細設計・実装で迷わないよう、以下の原則を適用する。

| 分類 | 具体例 | M1 Coreでの扱い | 根拠 |
| --- | --- | --- | --- |
| ドメイン中核 | Data Ingestion / Feature Pipeline / Signal Engine / Risk Manager / Ticket Builder（承認UI必須部のみ） | 実装対象。将来拡張ポイントは`TODO(m2)`コメントで封じ、IFは変更しない。 | FR-01〜FR-08, FR-10, FR-18 |
| ガバナンス | Strategy Scoreboard / Idea Pipeline / Model Risk Register / Ops Readiness Evaluator | **最小スタブのみ配置**。必要なインターフェースは`src/domain/governance/contracts.py`に小さく定義し、DI登録はスタブの空クラスのみ。 | スコープ圧縮、レビュー指摘#2 |
| レポーティング拡張 | Enhanced weekly report, Benchmark差分, Bootstrap CI | Feature Flagを既定`false`とし、テンプレート/処理を削除。`tradectl report`はM1テンプレのみをバンドル。 | FR-18最小要件のみに集中 |
| オペレーション演習 | Emergency Orchestrator / Reduce-Only自動化 / Ops drill | Runbookとチェックリストのみ整備。コード実装はM1.1以降のFollow-up Issueとして分離。 | M1.1 Hardening以降のFR |
| 可観測性拡張 | Prometheus Exporter / GUI WebSocket / SLAダッシュボード | `ObservabilityExporter`に`GuardedMetricsSink`を実装し、JSONL出力のみ提供。HTTPサーバや外部連携は`NotImplementedError`で明示。 | NFR-06, NFR-15最小限 |
- **変更管理**: 上記例外以外の追加コンポーネントは`docs/change_requests/`でPO承認を得た後に`m1-core-scope`ラベル付きIssueとして管理し、M1ブランチではマージしない。

## 2. 全体構成
```
┌────────────────────────────────────────┐
│ CLI / Signal Board (将来: GUI via React/Tauri) │
└───────────────┬────────────────────────┘
                │WebSocket/CLI出力
┌───────────────┴────────────────────────┐
│         Application Service Layer         │
│  - Session Manager & Mode Controller      │
│  - Workflow Orchestrator (Signal->Ticket) │
└───────────────┬────────────────────────┘
                │Domain Events (JSON)
┌───────────────┴────────────────────────┐
│              Domain Core Layer          │
│  Data Ingestion -> Feature Pipeline     │
│  Regime Detector -> Signal Engine       │
│  FX Rate Updater -> Spread Monitor -> Execution Model -> Calendar Gate -> Scoring -> Risk Manager -> Correlation Guard -> Position Sizer -> Reduce-Only Advisor -> Emergency Orchestrator │
│  Ticket Builder -> Trade Journal -> Benchmark Monitor -> Audit & Persistence -> Observability Exporter │
│  StressTest Engine -> Optimizer (Scenario) │
└───────────────┬────────────────────────┘
                │Time-series Cache / Stores
┌───────────────┴────────────────────────┐
│ Infrastructure Layer                   │
│  - Data Providers (yfinance/dukascopy) │
│  - Local Storage (Parquet/SQLite)      │
│  - Config/Profile (YAML/JSON)          │
│  - Notification (Email/Slack future)   │
└────────────────────────────────────────┘
```

### 2.1 コンポーネント一覧
| コンポーネント | 役割 | 技術/形式 | Milestone |
| --- | --- | --- | --- |
| CLI/Signal Board | 提案表示・操作入力 | Rich CLI（M1: `tradectl board`コマンド、JSON Lines入力）／将来React GUI | M1 Core |
| Session Manager | アプリ全体の起動・終了、Catch-up調整。スナップショットと最新イベントの差分から欠損ウィンドウを検出し、`resync_queue`へ`priority={critical,high,normal}`付き`BackfillJob`を投入する。起動時は`TimeSyncGuard`でNTPドリフトを測定し、`abs(clock_drift_ms)>500`の場合は`board_mode=guarded`で起動。長時間停止（24h超）では主要4ペアに`priority=critical`を付与し、復旧完了までは`HealthState=soft_stop(manual_review)`を維持する。 | Python service | M1 Core |
| Mode Controller | Backtest/Paper/Liveの振る舞い切替 | Stateパターン | M1 Core |
| Data Ingestion Service | データ取得・キャッシュ管理。ティッカー×プロバイダ単位で**`asyncio.Queue(maxsize>1)`を持つフェッチワーカー**と**内部バッファ**を用意し、取得（fetch）と整形/検証（processing）を分離する。主経路はDukascopy（中央値6秒/p95 12秒）、短期フォールバックはyfinance（中央値24秒/p95 58秒）。`ProviderFetchWorker`が常時4ジョブ並列、Catch-up時は6ジョブまで拡張し、`ProviderParseWorker`が`AsyncBuffer`内でUTC整列・Quality Guard検証を完了させてから`bar_ready_queue`へ整合済みバーのみ投入する。`FallbackRetryTask`が再試行間隔を管理し、手動CSV移行は`ManualCsvIngestionTask`へ委譲してパイプライン本流から切り離す。`ManualCsvIngestionTask`は`manual_csv/primary/<provider>/<YYYYMM>.csv`と`manual_csv/review/<provider>/<YYYYMM>.csv`の**二重入力ファイル**を取り込み、`ManualCsvReconciler`が差分チェック・SHA256ハッシュ生成・承認者イニシャルの検証を行った後でのみ`bar_ready_queue`へ反映する。`metrics/data_ingestion_sla.jsonl`へ`phase=fetch|processing`別の遅延と429/403イベント（`event=rate_limited`, `backoff_sec`）を記録し、30分内に4ペア全履歴を追いつけなければ`health.changed(reason=data_latency_fetch|process|rate_limited)`を発火する。`RateLimitGuard`がRolling 1h失敗率>3%または連続429>5回を検出すると**ポーリング間隔を倍化**し、回復後15分で段階的に戻す。プロバイダp99遅延や連続失敗はRunbook `docs/runbooks/RUN-DATA-05.md`（フォールバック調整）/`docs/runbooks/RUN-DATA-06.md`（手動補填）と連携し、Acceptable Degradation期間中は`HealthState=degraded(fetch)`でSignal Boardへ`BoardMode=guarded`を指示して主要4ペアのガード付き提案を継続する。承認画面では「代替ソース/手動CSVで補完中」バナーとダブルチェック必須チェックリストを強制し、承認操作ごとに`degraded_ack`監査イベントを追記する。**公式API移行計画**として、M1.2でRefinitiv Elektron Lite / dxFeed FX / OANDA premium APIを比較し（費用≦月額¥80,000・ライセンスで個人利用許諾・REST/WebSocketで再配信不可を遵守）、PoCでp95≤12秒を満たしたプロバイダを`Data Ingestion Adapter`へ追加する。導入条件はコンプライアンス承認とSLA 30日ローリング合格、フェイルオーバー統合テスト（AC-45拡張）を満たすこと。 | yfinance, Dukascopy, CSV（M1）、有償API（M1.2+オプション） | M1 Core |
| Data Quality Guard | 欠損/外れ値判定、再取得制御 | Pandas/Numpy | M1 Core |
| Feature Engine | インジケータ計算・マルチTF合成 | pandas-ta/custom | M1 Core |
| Regime Detector | レジーム分類（ADX等） | 独自ロジック | M2 |
| Account Service（単一口座集計） | Paper/Backtest/Live各モードの残高・証拠金・保有ポジションを単一口座単位で再構築し、R計算と証拠金余力をSignal/Risk/Reportへ提供する。入力は`reports/performance/paper/<run_id>.parquet`、`db/tradectl.db`（`tickets`）、`data/account/live_account.csv`等の単一口座ログに限定 | Paper実績Parquet, Backtest台帳, Live CSV/API | M1 Core |
| Account Aggregator（複数口座統合） | `accounts/<broker>/<account_id>.yaml`を基にブローカー横断の口座プロファイルとウェイトを読み込み、残高・証拠金・有効レバレッジを統合。口座別Rガードと相関用エクスポージャ（FR-58）を算出し、複数口座の引当/警告ワークフローを提供 | Live/Paper統合CSV, Broker API, `accounts/<broker>/<account_id>.yaml` | M2+ |
| Funding Service | スワップ/ファンディングレートの取得と適用 | broker_rules.yaml, swap_rates.csv (手入力/公開CSV, M1) | M1 Core |
| FX Rate Updater | 口座通貨換算レート取得/保存 | yfinance, 手入力CSV, (M2+: ブローカーフィード) | M1 Core (M2+ feed) |
| Calendar Service | 経済指標/休日スケジュール配信（出力: GateState） | ローカルCSV, 外部API同期 | M1 Core |
| Broker Rules Loader | ブローカー仕様読み込み（pip値/contract等） | YAML loader (`broker_rules.yaml`) | M1.1 |
| Spread Monitor | スプレッド/コスト観測・クールダウン制御 | `spread_metrics.parquet`(Dukascopy/公開CSV, M1) / Broker API(M2+) | M1.1 (M2+ broker feed) |
| Execution Model | スリッページ/ロールオーバー/Fill判定モデル | MarketData, SpreadMetrics, broker_rules.yaml | M1.1 |
| Liquidity Intelligence Service | 複数レートソースの乖離検知・板厚監視・HOLD判定 | yfinance, Dukascopy, broker API/CSV, `liquidity_monitor.parquet` | M2 |
| Correlation Guard | 通貨/シンボル相関制御 | Rule-based filter | M1.1 |
| Signal Engine | ルール/モデルプラグインIF | Strategyプラグイン | M1 Core |
| Risk Manager | リスク制約・Kill Switch・スプレッド制御。通貨バケットエクスポージャ算出と相関行列生成で`R_eff`を評価し、M1 Coreでも`RiskMetricsSnapshot`をSignal Boardへ送信。 | Policy engine | M1 Core |
| Position Sizer | Fixed Fractionalロジック | Python class | M1 Core |
| Compliance Validator | チケット承認前のレバレッジ/建玉/規制確認と代替案提示 | `broker_rules.yaml`, `risk_policy.yaml`, 監査ログ | M1.1 |
| Capital Allocation Guard | VaR/ESモニタリングと提案スロットリング | Portfolio PnL, `risk_policy.yaml`, Exposure metrics | M1.1 |
| Reduce-Only Advisor | 収縮提案生成（閾値到達時、M2+） | Python service | M2+ |
| Emergency Orchestrator | `emergency.yaml`に基づく緊急アクション実行（Kill Switch連携、Reduce-Only指示） | Policy/Playbook Runner | M2 |
| Ticket Builder | 注文チケット生成・ヒューマンエラーチェック | JSON Lines | M1 Core |
| Persistence & Audit | イベント/ログ/設定履歴 | SQLite/Parquet/JSON | M1.1 |
| Optimizer | グリッド/ランダム/WFA | SciPy/自作 | M2 |
| Reporter | 週次/エクイティ/メトリクス出力、アトリビューションメトリクス生成（PF/Sharpe/HitRate/R_eff寄与） | Markdown/HTML/Parquet | M1 Core |
| Strategy Manifest Manager | `strategy_manifest.yaml`のSchema検証、ハッシュ生成、再検証期限監視、`deprecated`タグ付与 | Pydantic/JSON Schema/SQLite | M1.1 |
| Strategy Scoreboard Service | `alpha_score`/`decay_score`算出、戦略メタ指標キャッシュ、Signal Boardへのランキング配信（FR-61）。M1では`StrategyScoreboardServiceStub`をDomain Event Busに登録し、Feature Flag `governance.alpha_scoreboard`で実装切替。 | Pandas/NumPy/SQLite | M2+ |
| Idea Pipeline Manager | `ideas/`配下の候補戦略を段階管理し、`screening_checklist`生成・必須エビデンス検証・昇格ゲート条件を統制（FR-62）。M1では`IdeaPipelineStub`を介して昇格ゲート通知を抑止し、Feature Flag `governance.idea_pipeline`でオンボード。 | Typer CLI/Pydantic/YAML | M2+ |
| Ops Readiness Evaluator | バックアップ整合度・Runbook更新率・演習ログを収集し、`ops_readiness_score`とHealthState連携を行う（FR-63, NFR-28） | Markdown parser/SQLite/CLI | M2+ |
| Model Risk Register Service | `model_risk_register.md`の差分監視・エビデンス突合・Explainability生成チェックを実施し、`model_risk_gap`ステータスを管理（NFR-26, AC-52） | Git metadata/Markdown AST/Python | M2 |
| Statement Reconciliation Service | ブローカー公式ステートメント（CSV/PDF→CSV）とLive/Paperログを突合し、残高差分/取引突合率を集計。差分閾値で`HealthState=degraded(reason=statement_gap)`を通知し、`reports/audit/reconciliation/`へMarkdownサマリを出力（FR-64, AC-53） | Pandas/Great Expectations/CLI | M2 |
| Research Workspace Bridge | `research/strategies/<id>/`のノートブック/成果物を解析し、`tradectl research promote`フローで検証メトリクスを取り込む | Papermill/nbconvert/CLI | M2 |
| Trade Journal Service | トレード/コメント管理、振り返りダッシュボード | SQLite/Markdown | M2 |
| Benchmark Analyzer | 外部ベンチマークデータとの比較、ギャップ算出 | Pandas/Plotly | M2 |
| Data Provenance Service | `data_manifest.json`生成・署名・検証、アーカイブ連携 | `manifest.sig`, ハッシュ計算, WORMストレージ | M1.1 |
| Audit Bundle Service | `audit_pack/<period>/`への証跡束ね（シグナル・承認・約定・設定・リスク承諾・ベンチマーク差分）と署名`audit_manifest.sig`生成 | JSON/Parquet/Markdown/署名モジュール | M1.1 |
| Release Governance Service | `tradectl release prepare/tag`のチェックリスト評価、Smokeテスト結果と承諾差分の検証、Kill Switchの`HOLD`制御 | CLI orchestrator, Markdown checklist | M1.1 |
| StressTest Engine | 指定シナリオの再生と感度分析、結果レポート生成 | Backtest Runner拡張 | M2 |
| Parameter Drift Monitor | 最適化パラメータと最新指標のドリフト監視 | Numpy/Scipy | M2+ |
| Observability Exporter | メトリクス収集とJSONL書き出し（M1）。Prometheus互換エンドポイントはM2+で有効化 | JSONL writer / future `prometheus_client` | M1 Core (M2+ HTTP) |
| Alert Dispatcher | メール通知 | SMTPライブラリ | M1.1 |

### 2.1.1 ガバナンス機構のスタブ/Feature Flag方針 (M1 Core)
- **目的**: Alpha Scoreboard/Idea Pipeline等のガバナンス機構がDomain層へ既に結合されているが、M1リリースでは実装を遅延させ、基盤を簡潔に保つ。
- **スタブ配置**: `domain/governance/alpha_scoreboard_stub.py`と`domain/governance/idea_pipeline_stub.py`を用意し、`DomainEventBus`へ既定登録。両スタブはイベントを受信しても副作用を発生させず、ログに`noop`を記録する。
- **Feature Flag**: `config/feature_flags.yaml`に`governance.alpha_scoreboard=false`, `governance.idea_pipeline=false`を既定値として追加。`ConfigRegistry.get_flag()`経由で参照し、アプリ起動時にスタブ/実装のDIを切り替える。CLI `tradectl config flags --set governance.alpha_scoreboard=true`などで将来切替可能。
- **テレメトリ**: スタブ状態でも`governance.flag_state`イベントを5分間隔で発火し、`health_snapshots`に`governance_disabled`理由を残す。これによりM2移行時に切替漏れを検出できる。
- **テスト方針**: M1ではスタブに対して`test_governance_stubs.py`を作成し、Feature Flag ON/OFFでのDI/イベント挙動を検証。将来実装時は同テストを拡張し、スタブと実装双方の契約を維持する。
- **リリースゲート**: Release Governance ServiceはM1で`governance.alpha_scoreboard`と`governance.idea_pipeline`が`false`であることを検証し、誤って有効化された場合は`release.blocked(reason=flag_mismatch)`を発火する。


#### Data Ingestion Service 詳細
- **実装判断指針**:
  - **主経路優先順位**: ライブ取得はDukascopy→yfinance→ローカルキャッシュ→手動CSVの順とし、yfinanceはYahoo利用規約が想定する個人利用・非再配信の範囲に限定する。Dukascopy取得はHTTPバースト＋`ProviderFetchWorker`で**常時4ペア並列（必須ティッカー4種）**、Catch-up時は`max_fetch_workers=6`まで拡張する。取得した生データはプロバイダごとの`asyncio.Queue(maxsize>1)`に格納され、`ProviderParseWorker`が`AsyncBuffer`でUTC整列とQuality Guard検証を実施してから`bar_ready_queue`へ流す。Buffer飽和時は`priority=critical`の欠損補完ジョブが最優先で割り込む。
  - **フェイルオーバー閾値**: `provider=yfinance`で`fetch_delay_p99>120`または連続3回の`fetch_timeout`を検出したら即座にDukascopyへ切替え、Dukascopyでも`fetch_delay_p99>25`または`processing_delay_p99>18`が継続する場合はローカルキャッシュ→手動CSV（Runbook `docs/runbooks/RUN-DATA-05.md` → `docs/runbooks/RUN-DATA-06.md`）へ移行する。切替履歴は`reports/performance/data_latency/<YYYYMMDD>.md`と`logs/events/data_latency.jsonl`へ同時記録し、Validation Data Playbook（AC-45）でレビューする。
  - **公式API移行計画**: M1.2でRefinitiv Elektron Lite / dxFeed FX / OANDA premium APIを比較し、費用（月額¥80,000以内目安）・API方式（REST/WebSocket）・商用/再配信制約・サポート体制を調査する。PoCで30日ローリングp95≤12秒を達成し、コンプライアンス/コスト承認が完了したプロバイダを`Data Ingestion Adapter`へ追加し、`feature_flags.data.paid_feed`で有効化する。切替前には`provider_switch_checklist.md`の承認とRunbook更新、`HealthMonitor`閾値の反転テストを必須とする。
- **ヘルスチェック/SLA監視**: ティッカー毎に`fetch_delay_sec = (enqueue_ts - request_ts)`、`processing_delay_sec = (bar_ready_ts - enqueue_ts)`を追跡し、直近30日ローリングで`fetch_delay_p95/p99`と`processing_delay_p95/p99`、`success_rate`を集計。ターゲットは**yfinance: fetch_p95≤60秒・fetch_p99≤120秒・processing_p95≤18秒・成功率≥97.5%／Dukascopy: fetch_p95≤15秒・fetch_p99≤25秒・processing_p95≤10秒・成功率≥99.0%**。閾値超過または`success_rate`低下時は`HealthMonitor.raise(level='warning', reason='data_latency_fetch|process', provider=...)`を送出し、`fetch_timeout>config.ingestion.fetch_timeout_sec`または`processing_timeout>config.ingestion.processing_timeout_sec`が連続3回で`level='critical'`を発火する。`SlaMinuteRollup`は`phase`別に`status ∈ {up, degraded, down, excluded}`を判定し、`metrics/data_ingestion_sla.jsonl`へ`{window_start, window_end, provider, phase, uptime_ratio}`を記録。`tradectl data health`はfetch/processingのどちらがボトルネックかをハイライトする。
- **プロバイダ別更新頻度/再接続ポリシー**: yfinanceはHTTPポーリングを**5秒間隔+ランダムジッタ1秒**で実施し、`RetryPolicy(max_attempts=3, backoff=1.5)`を適用。連続失敗時は60秒クールダウン後に再接続、`tradectl data switch --to dukascopy`で手動切替を指示できる。DukascopyはWeb APIを**2秒間隔**でチェックし、失敗時は`retry<=5`の指数バックオフ（最大間隔20秒）を実施。WebSocketモード（M2+）は`ping_interval=15s`、`pong_timeout=5s`で監視し、`tradectl data reconnect --provider dukascopy`で強制リセット可能。手動CSVモードは`manual_source=true`で健康監視を除外するが、`tradectl data resume --provider <name>`で既定経路に戻す。
- **遅延伝播シーケンス**: `warning(fetch)`はEvent Bus経由で`Spread Monitor`へ配信し、対象シンボルの`SpreadCooldownState`を`halt`へ強制遷移した上で`BoardGuardPolicy.activate(symbols=core_pairs)`を発火する。`warning(processing)`は`FeaturePipeline`の`bar_ready_queue`深さを監視し、処理遅延のみでKill SwitchがSTOPに遷移しないよう`BoardMode=guarded`での運用継続に切り替える。`critical(fetch)`（`fetch_timeout`連続3回）は手動CSVフェイルオーバーとRunbook `docs/runbooks/RUN-DATA-05.md`の実施を要求し、Kill Switchは維持したまま`BoardMode=guarded(core_pairs_only=true)`で提案継続とする。`critical(processing)`は`ManualCsvIngestionTask`完了まで`Workflow`をディレイキューに切替えるが、主要4ペアの既存チケットはガード付きで承認可能とする。M2+では`Emergency Orchestrator`が`data_latency`プレイブックを評価し、CLI/メール通知と自動シナリオ実行を追加する。復旧後は`HealthMonitor.ack`で解除し、Spread Monitor・`bar_ready_queue`・`BoardMode`を通常状態へロールバックする。
- **フェイルオーバー手順/ログ**: 1) `fetch_delay_p99>閾値`または`critical(fetch)`シグナルでDukascopy高速フェッチへ自動切替（`failover_stage=primary->secondary`）。2) Dukascopyも不可の場合は`FallbackRetryTask`がローカルキャッシュ`data/raw/<provider>/<symbol>/<tf>.parquet`を読み出すジョブをスケジュールし、完了時に`cache_source=fallback`をマーキングして`tradectl data jobs --pending`で確認する。3) それでも欠損が残る場合はRunbook `docs/runbooks/RUN-DATA-06.md`に従い`ManualCsvIngestionTask`を起動し、`tradectl data jobs enqueue --task manual_csv --symbol <symbol>`で取り込みを指示する。4) 各ステージで`failover_trigger_ts`/`failover_reason`/`stabilization_elapsed`/`sla_status_before`/`phase`をJSONLへ記録し、復旧後5分間安定性を監視してから`tradectl data resume --provider <name>`で主経路へ復帰する。手動モード中は`manual_source=true`フラグをイベントに添付し、ライセンス制約チェックリストの実施結果を`reports/audit/license/`へ保存する。

#### Reporter/Benchmark MonitorのKPI評価ガイド
- **キャッシュ保持期間**: Sharpe/Sortino/最大DD/年率は要件定義の評価期間に合わせ、最低でも**直近252営業日＋安全マージン10営業日**の取引履歴・エクイティカーブ・リスクメトリクスをキャッシュする。四半期レビュー用に**直近90営業日ローリング**のサマリも常備し、`metrics/kpi_cache.parquet`に`window={252d,90d}`単位で保管する。ブートストラップ再標本化での再利用に備えて、各ウィンドウのリターン系列を`returns_{window}.parquet`として別途保持する。
- **前処理ルール**: ReporterとBenchmark Monitorは共通のData Qualityフィルタを適用し、**欠損バー率≤0.5%/日・連続欠損≤3バー・異常イベント（`flash_crash`, `manual_exclusion`タグ）除外**後のデータセットのみをメトリクス計算に渡す。閾値を超えた場合は当該期間をドロップし、`data_quality_report.md`を添付した上で`HealthState`へ`data_gapped`理由を通知する。ドロップ後にサンプル不足となった場合は`KpiEvaluationStatus=pending`としてRunbookへ記録する。
- **データバージョン固定**: AC-07向け検証は`data_manifest.json::m1_baseline_ma_rsi::2024-12-31`の`sha256`を基準とする。Reporterは週次実行時に`metrics.json::dataset_hash`を突合し、差分が検知された場合は`metric_state=pending(reason='dataset_hash_drift')`を付与して`reports/research/m1_baseline/validation_<date>.md`への差分記録とRunbook `STRAT-M1-VALIDATION`の再承認フローを自動TODO化する。承認完了まではBenchmark Monitorも同じデータスナップショットを参照し、未承認データでは比較レポートを`status=draft`に留める。
- **KPI計算ロジック**: キャッシュ済みの取引リターンからSharpe/Sortino/最大DD/年率/Profit Factorを算出し、252営業日ウィンドウを週次モニタリング、90営業日ウィンドウを四半期レビューにマッピングする。計算は`metrics.compute_kpi(window, returns_df, equity_curve)`ヘルパーに集約し、Data Qualityフィルタ後のデータのみを許可する。ベンチマーク比較時は同一フィルタ・同一ウィンドウで差分を計算する。
  - **CLIロールアップ**: `tradectl kpi rollup`は週次テンプレート生成とは独立して上記パイプラインをワンショット実行し、`reports/performance/<mode>/<YYYYMMDD>.md`と`reports/kpi_snapshots/<YYYYMMDD>.json`を再生成する。UIは単点値のままでも、ローリング90/252営業日メトリクスは常にバックエンドで更新され、`reports/governance/kpi_alerts/`の逸脱検知と四半期レビューで活用される。
- **ベンチマークデータ取得**: M1ではTradingView公開シグナル（FX Majorsカテゴリ、ICS/CSVエクスポート）とMyfxbook公開システム（Sharpe>0.6, 稼働>12か月, CSVダウンロード可）をサポートする`BenchmarkFeedLoader`を用意。CLI `tradectl benchmark ingest --provider tradingview --file <path>`でICS/CSVを読み込み、`benchmark_runs/raw/<provider>/<YYYYMMDD>.parquet`へ正規化保存する。エクスポート不可区間は`benchmark_manual_log/<provider>/<YYYYMM>.csv`へ追記し、週次で`BenchmarkFeedLoader`がマージする。M2以降はAPI/Webhook拡張を想定し、インターフェース`BenchmarkFeedAdapter`を差し替え可能にする。
  - **再計算トリガー**: 週次レポート生成（`Reporter.run(schedule=weekly)`）と四半期レビュー（`calendar.quarter_review`イベントまたは`tradectl benchmark compare --quarterly`）の2系統で再計算を走らせる。どちらも**最新バー更新時（5分足確定）→キャッシュ更新→メトリクス再集計→信頼区間計算**の順に非同期ジョブを投入し、完了後に`kpi_snapshot.json`を上書きする。Data Qualityインシデント発生時（`data_gapped`, `anomaly_excluded`）も同じパイプラインを即時再実行する。
- **テンプレート/スコープ**: 週次レポートはM1 Coreで`reports/weekly/templates/m1_core.md`（Sharpe/最大DD/WinRate/累積R＋コメント2項目）のみをレンダリングし、`reporter.config`の既定値として`bootstrap_enabled=false`・`attribution_enabled=false`・`benchmark_gap_enabled=false`を設定する。Feature Flag `report.weekly.enhanced=true`に切り替えるとM1.1テンプレートへ移行し、ブートストラップ信頼区間やベンチマーク差分グラフ、カテゴリー別アトリビューションを追加出力する。
  - **metric_state出力**: `Reporter`は各メトリクスに`metric_state ∈ {confirmed, provisional, pending}`を付与し、`reports/performance/<mode>/<YYYYMMDD>.md`および週次テンプレートへ埋め込む。`metric_state=provisional`では自動生成コメント（例: 「90営業日未満の速報値」）とJeffreys事後勝率・移動平均Sharpeの暫定値を記載し、`metric_state=pending`ではKill Switchやキャピタル配分ゲートを発火させずRunbookチェックリストへ手動レビューTODOを追記する。
  - **AC-07閾値適用**: Reporterは`PF_all≥1.18`、`Sharpe_oos≥0.85`、`MaxDD_oos≤13%`を一方向閾値として評価し、逸脱した場合は`reports/research/m1_baseline/validation_<date>.md`に自動注記を追加する。Benchmark Monitorの比較チャートでも同閾値を注釈化し、下限/上限を混同しないよう`threshold_type ∈ {lower_bound, upper_bound}`をメタデータに明記する。
  - **統計検証**: Reporterの**BCaブートストラップ（1,000回）**はFeature Flag `report.weekly.enhanced=true`時のみ実行し、M1 Coreでは単点値のみを出力する。Benchmark Monitorの差分年率/Sharpeギャップ95%信頼区間も同Flag有効時に限り算出し、無効時は`confidence_interval_status=skipped(reason='m1_core')`をMarkdownへ記録する。信頼区間機能が有効化された場合、下限が要件を割り込むと`benchmark_gap`イベントに`confidence_breach=true`を付加し、受け入れ基準AC-07〜AC-09の検証ログに残す。ブートストラップ実行時の失敗はリトライ戦略に従って再実行する。
- **リトライ戦略**: KPI再計算ジョブが失敗した場合は`RetryPolicy`を継承した`KpiRecalcRetry`を使用し、**max_attempts=3, initial_delay=30s, backoff=2.0**で再実行。3回失敗時は`Reporter`が`Critical`ログを出力し、`HealthState`を`soft_stop`へ遷移させる。Benchmark Monitor側では最新成功スナップショットを保持し、復旧後に差分を自動再算出する。
- **サンプルサイズ監視**: Paperローンチから90営業日までは90営業日ウィンドウで**取引数<30（45営業日時点は<15）**の場合に`metric_state=provisional`とし、252営業日ウィンドウは一律で`metric_state=pending`とする。90営業日を経過した後は従来閾値（90営業日ウィンドウで取引数<60、252営業日ウィンドウで<180）を適用し、未達時は`metric_state=pending`を付与する。Reporterは`metric_state`を`reports/weekly/<YYYY-WW>.md`へ埋め込み、Runbookチェックリストに自動コメントを追加して人間レビューを促す。

### 2.3 データストア/フォルダ構成（v1.3追加）
※ M1 Coreでは以下ディレクトリは作成せず、必要に応じてM2以降で**最小スタブのみ配置**していく。存在しない段階では`docs/`およびRunbookで証跡管理する。
- `scoreboard/alpha/<YYYYWW>.json`（M2+）: 戦略ごとの`alpha_score`/`decay_score`と構成比、算出根拠（PF/Sharpe/Stability/Regime適合度）を保持。`scores/meta.json`で最新ウィンドウと前回比較を管理する。
- `ideas/<idea_id>/manifest.yaml`（M2+）: アイデアのデータソース、検証期間、想定リスク、現ステージ（`draft|screening|paper|ready`）を記述。`ideas/<idea_id>/checklists/<stage>.md`に必須エビデンスの進捗をMarkdownタスクで保持。
- `reports/model_risk/<strategy>.md`（M2+）: 各戦略のモデルリスク評価、Explainability添付リンク、緩和策のトラッキング。`model_risk_register.md`のインデックスと突合する。
- `reports/governance/ops_readiness_<YYYYWW>.md`（M2+）: オペレーションレディネス評価の詳細。Ops Readiness Evaluatorがスコア算出に参照し、Runbook `OPS-READINESS-01`（docs/runbooks/OPS-READINESS-01.md）のチェックリストIDを埋め込む。
- `reports/research/alpha_score/<YYYYWW>.md`（M2+）: Alpha Scoreboardの算出根拠をMarkdownで保存し、トレンド/レンジ/高ボラ別のサブスコアとリスクイベントを記録（FR-61）。
- `tickets/model_revalidate/<strategy>_<date>.md`（M2+）: Alpha ScoreboardまたはModel Risk Guardが起票する再評価タスク。完了時は`status=done`に更新し、Model Risk Register Serviceが参照する。

### 2.4 SQLite / Parquet スキーマ設計（M1 Core〜M1.1）

| ストア | テーブル/ファイル | 主キー / インデックス | 主要カラム | 説明 | パフォーマンス要件 |
| --- | --- | --- | --- | --- | --- |
| SQLite `db/tradectl.db` | `signals` | `PRIMARY KEY(id)`, `CREATE INDEX idx_signals_symbol_ts ON signals(symbol, generated_ts DESC)` | `id TEXT`, `symbol TEXT`, `side TEXT`, `score REAL`, `ttl_sec INTEGER`, `badges TEXT`, `state TEXT`, `generated_ts INTEGER`, `expiry_ts INTEGER`, `cfg_hash TEXT`, `data_hash TEXT` | 最新シグナル/TTL管理。`DomainEventBus`書き込みとSignal Board読み込みを統一。 | 最新10件取得クエリ`SELECT ... ORDER BY generated_ts DESC LIMIT 10`がp95<25ms。 |
| SQLite | `tickets` | `PRIMARY KEY(id)`, `CREATE INDEX idx_tickets_status_ts ON tickets(status, approved_ts DESC)` | `signal_id TEXT`, `entry REAL`, `size REAL`, `sl REAL`, `tp REAL`, `r_target REAL`, `status TEXT`, `approved_by TEXT`, `approved_ts INTEGER`, `latency_ms INTEGER` | HITL承認ワークフロー。Paper/Lliveレイテンシ記録。 | `WHERE status='approved' AND approved_ts BETWEEN ...`クエリp95<40ms。 |
| SQLite | `audit_events` | `PRIMARY KEY(id)`, `CREATE INDEX idx_audit_type_ts ON audit_events(event_type, ts DESC)` | `event_type TEXT`, `ts INTEGER`, `payload JSON`, `consent_reference_id TEXT`, `sha256 TEXT` | リスク開示/承認/緊急操作ログ。`Validation Data Playbook`でAC-40/AC-43の証跡に利用。 | `tradectl audit export --type approve --from`がp95<60ms。 |
| SQLite | `health_snapshots` | `PRIMARY KEY(ts)` | `status TEXT`, `reasons JSON`, `metrics JSON` | `tradectl status`やSLA集計の最新状態。 | `ORDER BY ts DESC LIMIT 1`がp95<5ms。 |
| Parquet `data/research/curated/<symbol>_m5_YYYY.parquet` | n/a（列指向） | `ts`ソート、`dictionary`エンコーディング（symbol） | `ts`, `open`, `high`, `low`, `close`, `volume`, `ema21`, `ema55`, `ema55_slope`, `rsi14`, `atr14`, `spread`, `session_tag` | バックテスト・特徴量抽出用の正本データ。`Validation Data Playbook`でAC-01/AC-07の入力を保証。 | `pyarrow.dataset.Scanner`で1年分読み込み<5.5s、IS+OOS全区間でも<35s。 |
| Parquet `reports/performance/paper/<run_id>.parquet` | `ticket_id`辞書化、`approved_ts`ソート | `ticket_id`, `signal_id`, `approved_ts`, `fill_ts`, `fill_price`, `sl_price`, `tp_price`, `r_realized`, `latency_ms`, `notes` | Paper実績ログ。AC-02/AC-10/AC-09の検証に使用。 | `approved_ts`範囲フィルタ付集計がp95<120ms。 |
| JSONL `metrics/pipeline_latency.jsonl` | n/a | `ts`, `component`, `latency_ms`, `p95`, `p99`, `provider` | データSLAとパイプライン遅延。`make sla-report`でAC-05/AC-45を検証。 | 24h分JSONL（約17k行）読み込みで集計<4s。 |

- **スナップショット/DR**: `snapshots/session_<ts>.json`（Open Tickets/HealthState/CfgHash）を1時間ごとに作成し、M1.1からは`sqlite3 .backup`でホットバックアップ。Runbook `DR-LOCAL-01`にリストア手順（4時間以内）を明記。
- **データ整合性チェック**: `make data-verify`がParquet/SQLiteのスキーマ版数を確認し、齟齬は`HealthState=data_gapped`に遷移。`Validation Data Playbook`のサインオフログと突合し、欠損時はCIを失敗させる。`strategy_manifest.yaml::dataset.hash`と`reports/data_manifest.json`の一致を`poetry run pytest tests/integration/test_data_manifest.py`で検証し、Paper昇格ワークフロー（`tradectl research promote`）はこのCIパス＋`reports/audit/data_integrity/<date>.md`のサインが無いと失敗する。Paper/Live切替時は`data/runtime/`のハッシュを記録して差分検知を強制する。
- **OOSデータ暫定補完**: Dukascopy/OOS更新が途絶した場合、Quant Leadが48時間以内にPaperログから`reports/research/paper_fill/<YYYYMM>.parquet`を生成し、Ops Managerが`reports/validation_log/AC-fallback_<date>.md`へ欠損理由・暫定期間・次回更新予定を登録する。暫定セットは最大30日までとし、延長時は研究レビューボードで承認した再取得計画（再ETL/代替フィード契約）を添付する。欠損がACへ影響する際は該当チェックを`status=pending`に切り替え、補完完了後に再サインオフする。

### 2.2 クロスカッティング・コンポーネント
- **Configuration Governance**: `ConfigRegistry`（シングルトン）でYAMLプロファイルを管理し、JSON Schema検証（FR-23）とバージョンハッシュを計算。安全項目はPub/Subでホットリロードし、危険項目は`NextBarChangeQueue`で遅延適用する。
- **Event Bus**: Domain層間の疎結合を保つために`DomainEventBus`を採用。同期処理はコアフロー、非同期処理（レポート生成、Slack通知など）はワーカーキューに委譲する。`MarketableLimitApplied`や`ReduceOnlyIssued`など執行関連イベントも同バスで配信する。イベントはJSON (`event_type`, `ts`, `payload`) 形式で`logs/events/DATE.jsonl`へ記録し、CLIの`tradectl events tail --type=signal`等で監視。主なイベントpayloadは以下の通り:
- **Strategy Lifecycle Governance**: Strategy Manifest ManagerとResearch Workspace Bridgeが連携し、`research.draft_created`→`research.metrics_published`→`strategy.promote_requested`→`strategy.promoted`のイベントシーケンスを管理する。Manifestに定義されたKPI・検証ウィンドウ・データセットハッシュを検証し、`last_validated_at`から90日超過で`strategy.expired`イベントを発火。`strategy.deprecated`状態ではSignal Engineがシグナル生成を抑止し、Paper整合率が復帰した場合にのみ`strategy.revalidated`で解除する。イベントは監査ログとRunbookの`GOV-STRAT-01`タスクにリンクし、Pull Requestのレビュー結果と自動突合する（NFR-20, NFR-21）。
- **Alpha Scoreboard Loop**: Strategy Scoreboard Serviceが週次ジョブで`returns_24w.parquet`/`metrics/kpi_cache.parquet`を読み込み、PF/Sharpe/Stability/Regime適合度を標準化して`alpha_score`を算出。リニア回帰から直近24週のドリフト勾配を算出し`decay_score`を導出する。結果は`scoreboard/alpha/<YYYYWW>.json`として保存し、Signal BoardへWebSocket/CLI経由で送信する。`alpha_score<75`または`decay_score>35`の場合は`strategy.watchlist`イベントを発火し、承認UIで昇格ブロックとウォーニングバナーを表示する（FR-61, AC-49）。データが24週に満たない場合は`status=pending`とし、直近で利用可能なウィンドウから算出した暫定メトリクスを`provisional=true`フラグ付きで返却、Signal Boardは「サンプル不足のため参考値」のフォールバックメッセージを表示する。暫定期間中は昇格ゲートを自動ブロックせず、前回確定スコアを参照する。M1 CoreではFeature Flag `governance.alpha_scoreboard=false`が既定となり、`StrategyScoreboardServiceStub`が同イベントを`noop`で受け止め、`strategy.watchlist`イベントを一切発火させない。
- **Opportunity Pipeline Workflow**: Idea Pipeline Managerが`tradectl research stage`操作ごとに`ideas/<id>/manifest.yaml`をSchema検証し、`stage`遷移に応じて`checklists/<stage>.md`を生成。未完了項目がある場合は`stage.blocked`イベントを返してPaper移行を阻止する。PaperステージではResearch Workspace Bridgeが整合率ログを監視し、4週連続未達で`strategy.promote`を拒否して`ideas/<id>/actions.md`へTODOを追記する（FR-62, AC-50）。M1 CoreではFeature Flag `governance.idea_pipeline=false`により`IdeaPipelineStub`が`stage.blocked`等のイベントを発火せず、研究作業ログのみ記録し、昇格ゲート制御を行わない。
- **Operations Readiness Loop**: Ops Readiness Evaluatorが`reports/governance/`, `reports/drill/`, `dist/offline_bundle/`のメタデータを収集し、バックアップ整合度・Runbook更新率・演習完遂率・緊急プロトコル検証の達成度を加重平均して`ops_readiness_score`を算出。スコア<75で`health.changed`（reason=`ops_readiness_low`）を発火し、新規リリース/戦略昇格コマンドをロックする。CLI `tradectl ops readiness --explain`でスコア構成と証跡ファイルを提示し、証跡欠損はスコア0扱いとする（FR-63, NFR-28, AC-51）。
- **Model Risk Register Guard**: Model Risk Register Serviceが`model_risk_register.md`および`reports/model_risk/<strategy>.md`をウォッチし、未更新>90日またはExplainability添付不足で`model_risk_gap`をRaiseする。解消は`tradectl model risk resolve <id>`で再評価メモとSHAP/Feature Importanceレポートのハッシュを登録することで実施し、Alpha Scoreboard側も`watchlist`解除には`model_risk_gap=false`を要求する（NFR-26, AC-52）。
- **Event Bus**: Domain層間の疎結合を保つために`DomainEventBus`を採用。同期処理はコアフロー、非同期処理（レポート生成、Slack通知など）はワーカーキューに委譲する。`MarketableLimitApplied`や`ReduceOnlyIssued`など執行関連イベントも同バスで配信する。イベントはJSON (`event_type`, `ts`, `payload`) 形式で`logs/events/DATE.jsonl`へ記録し、CLIの`tradectl events tail --type=signal`等で監視。主なイベントpayload仕様は以下の通り:
- **Liquidity Guard Pipeline**: Liquidity Intelligence Serviceが`quote_snapshot`イベントを5分足ごとに発行。`spread`, `quote_age`, `book_depth`のZスコアを算出し、閾値超過時は`liquidity.alert`イベントを発火。Risk ManagerとCompliance Validatorが同イベントをサブスクライブし、`HOLD`/サイズ縮小を同期的に適用する。
- **Compliance & Capital Policy Layer**: Compliance ValidatorとCapital Allocation Guardは`ticket.intent`イベントをフックし、`broker_rules.yaml`と`risk_policy.yaml`を参照して承認前検証を行う。結果は`ticket.intent_validated`イベントとしてTicket Builderへ返却し、監査ログに残す。
- **Data Provenance Mesh**: Data Provenance ServiceはData Ingestion/Persistence/Auditから`data.asset_written`イベントを受け取り、`data_manifest.json`と`manifest.sig`を更新する。アーカイブ時は`archive.created`イベントを発火し、外部WORM媒体へのコピー状況を`ops archive status`で可視化する。
- **Statement Reconciliation Loop**: Statement Reconciliation Serviceが`reconciliation.requested`イベントを受け取ると、`statement_reconciliation.yaml`に基づいてブローカーステートメントを正規化し、`trade_log.parquet`/`account_balances.parquet`と突合。差分が閾値内であれば`reconciliation.completed`を発行し、超過時は`health.changed(status=degraded, reason=statement_gap)`および`reconciliation.discrepancy`イベントを発火する。イベントpayloadには`missing_ticket_ids`, `balance_delta`, `fees_unmatched`を含め、Runbookチケットと連動する。
  - `signal.generated`:
    - `id: str`（`session_id`と`seq`で生成）、`symbol: str`（ISO通貨ペア）、`side: enum{LONG,SHORT}`、`entry: float`（提示価格）、`score: float[0,100]`、`ttl_sec: int`、`badges: list[str]`（`ALIGN/VOL/STAB/NEWS`等）、`extracts: dict`（根拠テキスト/指標値、任意）。
  - `risk.kill_switch`:
    - `reason: enum{daily_loss,weekly_loss,manual,spread_guard,data_quality}`、`trigger_metric: str`、`value: float`、`threshold: float`、`mode: enum{soft_stop,hard_stop}`。
  - `execution.ticket_approved`:
    - `ticket_id: str`、`user: str`、`note: str|null`、`sl: float`、`tp: float`、`latency_ms: int`（承認までの時間）、`oco_set: bool`。
  - `health.changed`:
    - `status: enum{ok,soft_stop,hard_stop}`、`previous: enum{ok,soft_stop,hard_stop}`、`reasons: list[{"code": str, "detail": str, "since": str}]`、`recommended_action: str`。
- イベント書き込み失敗時は最大3回リトライ（指数バックオフ1.5倍）。失敗後は`Critical`ログを出して`HealthState`を`hard_stop`へ遷移させ、Runbookに従って復旧。
- **Snapshot Manager**: `./snapshots/latest/*.json`にセッション状態（Open Tickets、AccountState、GateState、CfgHash）を周期保存し、再起動時にSession Managerがリプレイ（FR-18）。
- **Health Monitor**: SPRT評価（FR-22）、Kill Switch（FR-05）、連続エラー検出（FR-12）、SLAロールアップ（`SlaMinuteRollup`）を統合して`HealthState`を更新し、Signal Engine/Mode Controllerへブロードキャスト。`HealthState`は`{"status":"ok|soft_stop|hard_stop","reasons":[...]}`形式で保持し、SLA関連では`reasons[].code ∈ {data_latency_fetch, data_latency_processing, data_down, manual_stop, planned_maintenance, rate_limited}`を付与する。CLIの`tradectl health show`で確認し、`tradectl health manual-stop --reason <msg>`は`manual_stop=true`を、`tradectl health resume`は`manual_stop=false`と`manual_stop_released`イベントを残してSLA分母から除外・復帰を制御する。`HealthMonitor`は`degraded`状態が**連続3営業日**または**ローリング30日で2回**発生した時点で`health.escalate`イベントを生成し、Ops ManagerがRunbook `RUN-DATA-05`でエスカレーションレビューを開始する。`degraded`が**5営業日超継続**または週次レビュー2回連続で解消しない場合は自動で`risk.kill_switch`（mode=`hard_stop`, reason=`data_latency`)`を発火し、手動CSVモードのみに切り替える。復帰時は`catch_up_lag_minutes<30`、SLAメトリクス回復、手動CSV二重入力ハッシュ一致の3条件を検証し、承認サインを`reports/validation_log/AC-45_sla_<date>.md`へ記録する。

- **Board Guard Policy**: `HealthState.status`とは別に`board_mode ∈ {normal, guarded, halted}`を追跡する。`guarded`はAcceptable Degradation運用時に自動設定され、主要4ペアの提案のみを許可しつつ「要ダブルチェック」バナー・承認時ハッシュ記録・`degraded_ack`監査イベントを強制する。`board_mode=guarded`は`ResyncCompleted`または`health.resume(reason=data_latency_recovered)`で自動解除し、Kill Switchによる`soft_stop/hard_stop`とは独立して管理する。`halted`はKill Switch `soft_stop`/`hard_stop`でのみ使用する。状態遷移と運用アクションは以下。

| 現状態 | トリガー | 次状態 | オペレータ対応 |
| --- | --- | --- | --- |
| ok | Kill Switch閾値到達（daily_loss/weekly_loss） | soft_stop | 新規提案停止。`tradectl status`で原因確認、`tradectl health resume`で解除するまでReduce-Onlyのみ（M2+）。
| ok | Spread guard発火（連続閾値超） | soft_stop | `tradectl spread cooldown`で解除条件を監視。強制解除は不可。
| ok | DataDegraded（欠損>閾値） | soft_stop | `tradectl resync`で復旧し、正常バー3本確認後に自動復帰。
| ok | fetch遅延SLA未達（fetch_delay_p95/p99超過が連続3回、フェイルオーバー発火） | board_guarded | `HealthState=degraded(reason=data_latency_fetch)`へ遷移し、Dukascopy→キャッシュ→手動CSVの順で取得を継続。Signal Boardは`BoardMode=guarded`で主要4ペアのみ提案継続とし、`reports/governance/provider_switch_checklist.md`に代替計画（再ETL/プロバイダ切替）と7日以内の実施期限を記録する。解除はSLA回復＋PO/Opsダブルサインで実施。
| ok | processing遅延SLA未達（processing_delay_p95/p99超過が連続3回） | board_guarded | `HealthState=degraded(reason=data_latency_processing)`へ遷移し、`ManualCsvIngestionTask`完了と`processing_delay`改善を待つ。Signal Boardは`BoardMode=guarded`で承認可とし、`reports/validation_log/AC-45_sla_<date>.md`に対応メモと手動レビュー結果を残す。`bar_ready_queue`が安定するまでダブルチェック必須。
| soft_stop | オペレータ確認後、復帰コマンド | ok | `tradectl health resume`で復帰。Kill Switch解除時はRunbook `docs/runbooks/RUN-RISK-01.md`のチェックリストに従い、① `tradectl diagnostics risk --from -30d`でR分布/同時保有/`R_eff≤2.5`を確認、② `metrics/data_ingestion_sla.jsonl`で直近60分の成功率100%・遅延p95内を確認、③ `reports/audit/drawdown_guard/<date>.md`へ原因分析と是正タスク（Git/Ticketリンク）を記録しPO/Ops Managerのサインを取得——を満たした場合のみ`tradectl kill-switch release --ticket <id>`→`tradectl health resume`の順で復帰する。満たせない場合は`soft_stop`を維持し翌営業日に再審査する。
| 任意 | `tradectl stop`/manual emergency、クリティカル例外 | hard_stop | プロセス停止。再起動前に原因調査、`tradectl start`で立ち上げ直し。
| hard_stop | 再起動完了 | ok | スナップショットから復旧、`tradectl status`で整合性確認。
- **Audit Trail Service**: 監査イベント（FR-11）を受け取ってJSONL/SQLiteへ二重書き込みし、書き込み失敗時はWrite-Aheadログでロールフォワード可能にする（ERROR-C04対策）。`HumanCheckFailed`等のヒューマンエラー検知もここで証跡化する。CLIからは`tradectl audit export --date 2025-02-20`で抽出。
- **Logging Strategy**: `logging.config.dictConfig`を用い、モジュール別ロガーを定義（例: `core.signal`, `infrastructure.ingestion`, `interfaces.cli`）。デフォルトレベルINFO、`metrics`/`debug`チャンネルは`logs/app.log`へ、監査・イベントはJSONLへ出力。例外は`logger.exception`でトレースを記録し、再試行が必要なケースはRetryPolicyへ委譲。
- **RetryPolicy**: インフラ層でユニット化し、yfinance/Dukascopy取得は`max_attempts=3`, `backoff=1.5`倍増。取得失敗は`DataDegraded`イベントで通知し、閾値超えでKill Switchへ連携。CLIコマンドは即時エラーとし、非ゼロ終了コードでユーザーへ通知。
- **Emergency Orchestrator**: `emergency.yaml`を`pydantic`でロードし、シナリオ→アクション（Kill Switch遷移、Reduce-Only提案、通知、再接続リトライ）を状態マシンとして実行（FR-47, AC-38）。`tradectl emergency dry-run`で手順検証、`tradectl emergency trigger <scenario>`で手動発火（保護付き）。緊急時のオペレーション責務と承認テンプレートはRunbook `RUN-DATA-05`（docs/runbooks/RUN-DATA-05.md）を参照する。
- **Trade Journal Service**: チケット承認イベントと実績（Backtest/Paper/Live）を`journal_entries.db`へ保存し、週次レポート生成時にMarkdownテンプレートへレンダリング（FR-44）。CLIは`tradectl journal add-note --ticket <id>`でコメント追記、`tradectl journal review`で直近レビューを表示。
- **StressTest Orchestrator**: `scenarios/*.yaml`のイベントセットと感度パラメータ（spread_multiplier, slip_bias, decision_delay）をBacktest Runnerへ注入し、結果を`reports/stress/<scenario>/index.md`へまとめる（FR-43, AC-36）。
- **Benchmark Monitor**: `benchmark_feeds/*.csv`を取り込み、自戦略のエクイティ・KPIと差分チャートを生成。`tradectl benchmark compare --from 2023-01-01`で比較実行し、差分が閾値超過の場合はHealth Monitorへ`benchmark_gap`理由を追加（FR-46, FR-48）。
- **Benchmark Monitor**: `benchmark_feeds/*.csv`を取り込み、自戦略のエクイティ・KPIと差分チャートを生成。`tradectl benchmark compare --from 2023-01-01`で比較実行し、差分が閾値超過の場合はHealth Monitorへ`benchmark_gap`理由を追加（FR-46, FR-48）。Acceptable Degradation期間中に`benchmark_manual_log/<provider>/<YYYYMM>.csv`を利用する場合は、`benchmark validate-manual`サブコマンドで`manual_log/primary`と`manual_log/review`の二重入力一致を検証し、ハッシュと承認者イニシャルを`reports/benchmark/manual_log_signoff/<YYYYMM>.md`へ書き出すまでKPI集計をブロックする。
- **Observability Exporter**: M1は`metrics/pipeline.jsonl`/`metrics/cli_perf.jsonl`をストリーム書き出しし、`tradectl metrics report`でRunbook添付用スナップショット（Markdown/JSON）を生成する。Prometheus互換ExporterはM2+で`/metrics`（予定ポート`127.0.0.1:9108`）を公開する計画とし、M1ではExporterインターフェースとメトリクス登録コードをスタブ化しておく（NFR-06, NFR-15）。

## 3. ユースケースフロー（MVP）
※ 本節ではM2以降に有効となる機能を〈M2+〉と明記し、各ステップにマイルストーン注記（例: 〔M1〕）を付与しています。

1. アプリ起動 -> Session Managerが設定読み込み・Catch-upキュー投入->履歴データ同期。〔M1〕[^ms-core]
2. Data Ingestionが所定ティッカーの新規バーを取得し、キャッシュを更新。〔M1〕[^ms-core]
3. Broker Rules Loaderが`broker_rules.yaml`をロードし、pip値/contract size/最小ロット/tick制約を`BrokerSpecs`として共有キャッシュに展開。〔M1.1〕[^ms-hardening]
4. FX Rate Updaterが口座通貨換算レート（5m最新値＋日次終値）を取得し、差分があれば`fx_rates.parquet`を更新（排他ロック付与）。〔M1〕[^ms-core]
5. Spread Monitorが`spread_metrics.parquet`（M1: Dukascopyティック/公開CSV/手入力CSVから事前集計、M2+: ブローカーフィード連携）をロード・更新し、`SpreadMetrics`としてキャッシュ。CLIからは`tradectl spread ingest`でヒストリカル分位を生成し、`tradectl spread watch`でリアルタイムポーリングを開始する（M2+）。〔M1.1〕[^ms-hardening]
6. Funding Serviceが`broker_rules.yaml`で定義されたスワップ計算ルールを読み込み、`swap_rates.csv`（M1: 手入力/公開CSV、M2+: ブローカーフィード統合）から当日分のロング/ショートスワップ（Wednesday_NYの3倍など）を取得し、`FundingCurve`を生成。CLIは`tradectl funding sync`でCSV読み込み、`tradectl funding status`で最新値を照会。〔M1〕[^ms-core]
7. Account Serviceがモード別データソース（Backtest: シミュレーション台帳 / Paper: `reports/performance/paper/<run_id>.parquet` / Live: ユーザー入力CSV/API）と最新レートを用いて単一口座の残高・証拠金・含み損益を集計。口座単位のR計算と証拠金余力を`AccountState`へ反映し、欠損データや算出不能時はSignal Boardへ警告を送る。スワップは`FundingCurve`を日次で織り込んだキャッシュフローとして反映し、バックテストでも同一ロジックを適用する。〔M1〕[^ms-core]
8. Calendar Serviceが経済指標CSV/休日CSVをUTC基準でロードし、設定された`trading_timezone`（既定:JST）に変換した上で現在時刻に対するブロック/解除ウィンドウを判定して`GateState`を更新。イベント強度に応じた±15/30分の動的拡張ルールもここで適用する。〔M1〕[^ms-core]
9. Feature Engineが差分計算で新規バー分の指標を更新し、必要な区間のみ再計算。M1ベース戦略では5分足のインジケータ更新後に`multi_tf_joiner`が1時間足EMA(55)と日足Zスコアを参照し、`FeatureFrame`へ`ema55_slope`/`htf_bias_zscore`を追加する。〔M1〕[^ms-core]
10. Regime Detectorが最新特徴量からレジームスコアを更新し、ヒステリシスを適用。トレンド/レンジ/高ボラ分類は`ATR_Z`と`ema55_slope`を入力にしてSignal Engineのフィルタ条件へ渡す。〔M2+〕[^ms-m2]
11. Signal Engineが戦略プラグインを順に評価し、候補シグナルを生成。`m1_baseline_ma_rsi`プラグインは5分足EMA(21/55)クロス＋RSIゾーンの条件に加えて、1時間足EMA(55)の傾きがエントリー方向と一致した場合のみ`RawSignal`を返却し、日足Zスコアは`badges`に反映される。〔M1〕[^ms-core]
12. Execution Modelがヒューマン遅延Δt・Fillモデル（Marketable Limit/IOC）・滑り分布を適用し、想定約定価格・失効条件・コストを補正（FR-27, FR-29, FR-39）。ΔtはM1ベース戦略の検証値（Triangular(30,45,75)秒）をデフォルトとして`execution.adjustments.latency_ms`に埋め込み、Backtest/Paperは遅延後価格を用いたOCO距離を算出する。〔M1.1〕[^ms-hardening]
13. Calendar Serviceの`GateState`によりイベントや休日でブロック対象となるシグナルを除外。〔M1〕[^ms-core]
14. Scoring ServiceがM1では`expected_R`と`PF_all`ベースのシンプル重み付けで順位付けし、Spread Monitorがスプレッドクールダウン状態の場合はスコアを減衰（FR-41）。Funding Serviceが`swap_penalty`を供給し、保有期間が長期化するストラテジにはスワップコストをシミュレーション時のスコアに反映する。ハイブリッドスコアとStabilityペナルティは〈M2+〉で有効化し、Feature Flagで切り替える。〔M1〕[^ms-core]
15. Risk Managerが`AccountState`、`BrokerSpecs`、`SpreadMetrics`、`FundingCurve`を参照しつつリスク制約（ドローダウン/連敗/スプレッド上限/マージン/日次スワップ）をチェック。SPRTベースのライブ健全性ガードはM2以降で有効化し、適用時はHealth Monitorへステータスを送信（FR-05, FR-22〈M2+〉, FR-28, FR-36）。〔M1〕[^ms-core] Paper 90日評価では**1トレード0.75%リスク＋日次-3%/週次-6%停止**の組み合わせが提案頻度を阻害しないかを週次ダッシュボードで再計算し、連敗即日停止が発生した場合は`reports/diagnostics/risk/`にドリフト分析とReduce-Only暫定運用（§6.1）を添付する。
16. Correlation Guardが通貨バケット相関・シンボル相関行列を評価し、許容度を超えるシグナルを抑制。〔M1.1〕[^ms-hardening]
17. Position Sizerが`AccountState`・`BrokerSpecs`・最新レート・スプレッド・Execution Model補正を用いて推奨ロットサイズとOCO値を決定。M1ではATR(14)をpips換算した`atr_pips`から`sl_pips = max(atr_pips×1.2, broker.min_stop_distance)`、`tp_pips = sl_pips×2.0`を導出し、Marketable Limit採用時は`protect_pips`を加算した指値を提示する。結果は`Ticket Builder`へ`oco_recommendation`として渡され、Signal Boardのチケットに根拠（ATR係数/ブローカールール差分）が併記される。〔M1〕[^ms-core]
18. Ticket Builderが`BrokerSpecs`を用いた桁/最小距離検証、Marketable Limit提示、TTL/ドリフト監視設定、ヒューマンエラーチェックリスト（ダブルチェック/SLTP/OCO）を付与し、Signal Boardへ配信（FR-30, FR-38, FR-39）。〔M1.1〕[^ms-hardening]
19. ユーザーがチケットを承認/却下/編集->監査ログ記録。承認後のSL/TP未入力やTTL超過は自動アラート。〔M1〕[^ms-core]
20. Trade Journal Serviceが承認/却下イベントとユーザーコメントを`journal_entries.db`へ保存し、戦略/レジーム別メタデータを更新（FR-44, AC-37）。〔M1.1〕[^ms-hardening]
21. Statement Reconciliation Serviceが日次ジョブまたは`tradectl reconcile statements --from <date>`により呼び出され、ブローカーステートメントCSVを正規化してLive/Paperログと突合し、`reports/audit/reconciliation/<date>.md`へ差分を出力。残高差分>0.5Rまたは取引突合率<99%の場合は`Health Monitor`へ`statement_gap`理由を追加し、Kill Switch解除条件にRunbook調査メモを要求（FR-64, AC-53）。〔M2+〕[^ms-m2]
22. Parameter Drift Monitor（M2+）が最新最適化結果と現行パラメータを比較し、KLダイバージェンスしきい値を超えた場合は`benchmark_gap`同様にHealth Monitorへ理由を追加（FR-45）。〔M2+〕[^ms-m2]
23. Benchmark MonitorがベンチマークCSVとの差分を計算し、`benchmark_gap_pct`を更新。ギャップ>5%（設定値）でアラートを発火し、運用健全性ダッシュボードにハイライト（FR-46, FR-48）。〔M2+〕[^ms-m2]
24. Reporterが定期的にレポート/ログを出力し、Spread/Correlation/Resync/StressTest/Journal要約も含めてダッシュボードに反映（FR-10, FR-43, FR-44）。〔M1〕[^ms-core]
25. Observability Exporterが最新メトリクスをJSONLへ書き出し、必要に応じて`tradectl metrics report`でサマリースナップショットを生成してRunbookへ添付（NFR-06, NFR-15）。〔M1.1〕[^ms-hardening]
26. Audit Bundle Serviceが月次/四半期スケジュールまたは`tradectl audit bundle --period`コマンドに応じて、シグナル履歴・承認/約定ログ・設定差分・リスク承諾・ベンチマーク比較を`audit_pack/<period>/`へ束ね、`audit_manifest.json`と署名`audit_manifest.sig`を生成（FR-59）。〔M2+〕[^ms-m2]
27. Release Governance Serviceが`tradectl release prepare/tag`でSmokeテスト結果とリスク承諾差分を検証し、未完了チェック項目があればKill Switchを`HOLD`固定として新規配信を抑止。承認結果は`reports/audit/release/<version>.md`に記録（FR-60）。〔M2+〕[^ms-m2]
28. Kill Switchまたはアラート条件が発火した場合、Emergency Orchestratorが`emergency.yaml`に基づきアクション（Reduce-Only提案、通知、再接続リトライ）を実行し、Mode Controllerが新規提案を停止（FR-47）。〔M2+〕[^ms-m2]
29. Configuration Governanceが安全項目のホットリロードを配信し、Signal Engine/リスク管理へ反映。危険項目は`NextBarChangeQueue`に保留し、次バー確定時にSession Managerが適用て監査イベントを出力。〔M1.1〕[^ms-hardening]
30. Strategy Scoreboard Serviceが週次ジョブとして`returns_24w.parquet`を集計し、PF/Sharpe/Stability/Regime適合度を標準化して`alpha_score`を算出。`decay_score`は指数移動平均の傾きから求め、`scoreboard/alpha/<YYYYWW>.json`と`reports/research/alpha_score/<YYYYWW>.md`へ出力。24週未満やメトリクス欠損が検知された場合は`alpha_score_status=pending`で暫定スコアと注意文（`insufficient_sample_notice`）を同梱し、Signal Boardはフォールバック表示へ切り替える。このステータス中は自動昇格ブロックを抑制し、前回確定スコアを参照する。閾値割れ戦略には`strategy.watchlist`イベントを発火し、Signal Boardで昇格ゲートを閉じる（FR-61, AC-49）。〔M2+〕[^ms-m2]
31. Idea Pipeline Managerが`tradectl research stage`イベントを処理し、`ideas/<id>/checklists/`の必須タスク完了を検証。Paper移行には4週分の整合ログが必要で、未達成なら`stage.blocked`を返しRunbookへTODOを追記（FR-62, AC-50）。〔M2+〕[^ms-m2]
32. Model Risk Register Serviceが`model_risk_register.md`の更新を監視し、未更新>90日またはExplainability添付不足で`model_risk_gap`をRaise。`tradectl model risk resolve <id>`の完了時にタスクを`tickets/model_revalidate/`からクローズし、`HealthState`をクリアする（NFR-26, AC-52）。〔M2+〕[^ms-m2]

#### 〈M2+〉拡張フロー
1. Liquidity Intelligence Serviceが`quote_snapshot`を生成し、二重取得レートの乖離・板厚を集計。`liquidity_monitor.parquet`へ書き込み、閾値超過時は`liquidity.alert`をRisk Managerへ送出（FR-49, AC-38）。CLIの`tradectl liquidity inspect`で可視化し、解除条件メモをRunbookに追記。〔M2+〕[^ms-m2]
2. Account Aggregatorが`accounts/<broker>/<account_id>.yaml`と複数口座のログ（Paper: `reports/performance/paper/<run_id>.parquet`、Live: ブローカーCSV/API）を読み込み、残高・証拠金・R_effを統合。FR-58の受け入れ基準で定義するポートフォリオ整合率を`reports/performance/portfolio/<date>.parquet`で検証し、Risk/Correlation/Capital Guardへ統合`AccountState`を提供。〔M2+〕[^ms-m2]
3. Reduce-Only Advisorが`HealthState`とマージン閾値・イベント窓情報から新規提案可否を判断し、必要時は`ReduceOnlyTicket`を生成。M1は同条件での手動レビューのみ。〔M2+〕[^ms-m2]
4. Ops Readiness Evaluatorが`reports/governance/ops_readiness_<YYYYWW>.md`とRunbookチェックリストを読み込み、スコア<75の場合は`health.changed`（reason=`ops_readiness_low`）でKill Switchを`soft_stop`とし、新規リリース・戦略昇格を保留。復旧時は証跡リンクを検証しスコアを再計算（FR-63, NFR-28, AC-51）。〔M2+〕[^ms-m2]

[^ms-core]: `要件定義（テンプレ形式）v_1.md` §3.1「マイルストーン別優先度（Functional Requirements）」M1 Core (M1.0) 参照。
[^ms-hardening]: `要件定義（テンプレ形式）v_1.md` §3.1「マイルストーン別優先度（Functional Requirements）」M1.1 Hardening 参照。
[^ms-m2]: `要件定義（テンプレ形式）v_1.md` §3.1「マイルストーン別優先度（Functional Requirements）」M2 (強化フェーズ) 参照。
### 3.1 補足フロー: ストラテジーライフサイクル〈M2+〉
1. **研究公開**: 研究者が`notebooks/<strategy>.ipynb`を`papermill`で実行し、`research/strategies/<id>/results.json`（PF/Sharpe/Sortino/最大DD/評価ウィンドウ/データハッシュ）と`equity.csv`を生成。`tradectl research publish <id>`で`strategy_manifest.yaml`スケルトンとRunbookテンプレート（`README.md`）を作成し、初期`promotion_checks`と`validation_windows`を宣言する（FR-55）。
2. **メトリクス同期**: Research Workspace Bridgeが`results.json`を解析し、Manifestへ検証指標・サンプル数・`data_hash`・`code_version`を記録。`make research-sync`が共通のインジケータ/フィーチャ計算コードを同期し、研究環境と本番環境の差異が±0.5%以内かをCIで検証（FR-55, NFR-21）。
3. **Paper昇格審査**: `tradectl research promote <id>`実行時にPaperモードでサンドボックス検証を起動し、Manifestの`promotion_checks`（PF>1.05, Sharpe>0.8, 最大DD<15%, レジーム別PF≥1.0等）を評価。合格すれば`strategy.promote_requested`→`strategy.promoted`イベントを発火し、Manifestの`last_promoted_at`/`governance_ticket_id`/`paper_alignment`を更新。未達なら`strategy.promote_rejected`イベントと理由コード（`insufficient_pf`, `drawdown_excess`, `sample_shortage`など）を出力し、Runbook `GOV-STRAT-01`へフォローアップを記録（FR-55, FR-56, AC-46）。
4. **有効期限管理**: Strategy Manifest Managerが毎起動・日次ジョブで`last_validated_at`と`validation_ttl_days`をチェックし、90日超過（既定）またはPaper整合率<99%で`strategy.expired`イベントを発火。Signal Engineは該当戦略の提案を停止し、Signal Boardでは`deprecated`バッジを灰色表示する。`tradectl strategy renew <id>`により再検証が成功すると`strategy.revalidated`イベントと共に`deprecated=false`へ戻し、Paper整合率ログを再構築する（FR-56, AC-47）。
5. **アトリビューション/キャピタル配分**: Reporterが週次バッチで`reports/attribution/<YYYYWW>.parquet`と`weekly.md`を生成し、PF/Sharpe/HitRate/R_eff寄与を計算（FR-57, AC-48）。Manifestの`attribution_reference`に最新レポートパスを反映し、`Capital Allocation Guard`はこのデータを用いて戦略ごとのVaR/ES寄与とReduce-Only/サイズ上限を更新する。
6. **ガバナンス可観測性**: ManifestとRunbook議事録を`git`管理し、Pull Requestでは`strategy_manifest_check` CIが`promotion_checks`と`results.json`の整合性、`data_hash`の存在、`last_validated_at`更新を検証。`audit`イベント（`strategy_promotion`, `strategy_deprecation`, `strategy_revalidation`）は`reports/governance/`へ週次スナップショットとしてエクスポートされ、NFR-20/AC-46を満たすエビデンスとする。

### 3.2 CLIインターフェース仕様（M1）
- **`tradectl board`**: Signal Board表示コマンド。入力として`logs/events/<YYYYMMDD>.jsonl`を日付降順で探索し、最新の日次イベントファイルをストリームして最新バーごとに表形式レンダリング。出力列は`symbol, side, entry, size, sl, tp, score, ttl, badges`。`--filter symbol=USDJPY`や`--view open_tickets`などのフィルタ/ビュー切替を提供。起動時には`RiskDisclosureService`で承諾ステータスを確認し、**初回起動および四半期レビュー週の初回起動**ではリスク警告ダイアログ（投資助言禁止・主要リスク・損失可能性・想定利用範囲・ブローカー約款リンク・直近承諾ログサマリを含む）を表示する。承諾が取得できない場合はボード描画前に終了コード`103`でブロックし、承諾操作が完了すると`audit`イベント（type=`risk_consent`）へ承諾文言・表示バージョン・ユーザーID・端末識別子・コンセントハッシュを記録してからレンダリングへ遷移する。 Acceptable Degradation（`board_mode=guarded`）時はヘッダに橙色バナーを表示し、主要4ペア以外のティッカーを自動で折りたたむ。承認コマンド実行時にはダブルチェック済みトグルと補完ソース（Dukascopy/yfinance/manual_csv）を必須入力とし、`audit`へ`degraded_ack`イベントが追記される。`board_mode=guarded`解除後はバナーが自動で消え、履歴に解除ログを残す。
- **`tradectl ticket approve|reject|edit`**: チケット操作。引数は`--id <ticket_id>`とし、`edit`時は`--field sl=151.20`のように複数指定可。処理結果は`audit`イベントとして`logs/events/DATE.jsonl`に追記される。
- **高リスク操作の警告ガード**: `tradectl ticket approve`（ライブモード、R>既定閾値）、`tradectl emergency trigger`, `tradectl reduce-only push`等の高リスクコマンドは実行前に`RiskDisclosureService`へ承諾ステータスを照会し、未承諾・期限切れ・文言更新待ち・端末変更検知の場合はボードと同一の警告ダイアログを表示する。ユーザーが承諾を更新すると即座に`audit`イベント（`risk_consent`)を追記し、コマンド側では新規`audit`イベント（`ticket_action`, `emergency_action`など）に`consent_reference_id`と`consent_version_hash`フィールドを紐付けて監査可能性を担保する。
- **`tradectl events tail`**: Event Bus監視。`--type`で`signal|risk|execution|health|audit`を絞り込み、デフォルトは`signal`。出力フォーマットは`[ts][type] payload_json`。
- **`tradectl data health|switch|reconnect|failover|resume|ack`**: データプロバイダのメトリクスを一覧表示（SLA達成率、p95/p99、失敗回数）。`switch --to <provider>`で優先プロバイダを変更し、`reconnect`でセッション再確立、`failover --to cache|manual`で即時切替、`resume`で主経路に復帰。`ack`はRunbook承認後に遅延アラートを解除し、`reports/audit/license/`へ記録する。
- **`tradectl fx-rate status|switch|reconnect|ack|resume`**: `status`で為替レート取得状況（最新取得時刻、p99、成功率、使用中ソース）を表示。`switch`/`reconnect`/`resume`はData Ingestionと同じ操作フローを踏襲し、`ack`でアラート解除と監査ログ追記を行う。WebSocket（M2+）では`status --debug`でPing/Pong状況を確認。
- **`tradectl spread watch|switch|resume|ack|report`**: `watch`はリアルタイム観測、`switch`でソース切替、`resume`でフェイルオーバー解除、`ack`でアラート承認。`report`は直近24hのスプレッドSLA、フェイルオーバー履歴、ライセンスチェック状況をMarkdownで出力し、Runbookレビューに添付する。
- **`tradectl status`**: セッションのヘルスと統計を表示。`HealthState`（`status`, `reasons`）と`Snapshot`のハッシュ、現在のSpreadCooldownStateや未処理Reduce-Onlyチケット数、`benchmark_gap_pct`、直近ジャーナルハイライト（最新コメント/評価）を含む。
- **`tradectl export --what tickets|signals|account`**: 指定リソースをCSV/JSONにエクスポート。既定は`csv`で`--format json`指定可。出力パスは`reports/export/<date>/<what>.<ext>`。
- **`tradectl audit bundle --period <YYYYMM>`**: `audit_pack/<period>/`配下にシグナル履歴・承認/約定ログ・設定差分・リスク承諾ログ・ベンチマーク比較を集約し、`audit_manifest.json`と署名`audit_manifest.sig`を生成。`--verify`で署名検証を実施し、検証結果は`reports/audit/audit_pack/<period>.md`に記録。
- **`tradectl release prepare|tag`**: `prepare`が`release_checklist.md`を生成し、Smokeテスト（Backtest回帰、データソース切替、Kill Switch動作）とリスク承諾文言差分の承認状況を記録。`tag`はチェックリスト完了と署名済み承認が揃うまで拒否し、結果を`reports/audit/release/<version>.md`へ書き出す。
- **`tradectl readiness review`**（M1.1）: `ops_readiness_score`, `reports/validation_log/`のサインオフ状況、Paper-Liveパリティ（AC-26）の結果を集計し、Live昇格可否を判定。未完項目はExit code 121と未達リストを返す。`--export md`でRunbook添付用レポートを生成。
- **`tradectl validation log append --ac <id>`**（M1.1）: `reports/validation_log/AC-<id>_<date>.md`に検証データの取得手順・責任者サインを追記。`--check`で最新サインの有効期限（既定=14日）を検証し、期限切れは`HealthState=data_gapped`へ通知する。
- **`tradectl emergency trigger <scenario>` / `dry-run`**: `emergency.yaml`に定義されたシナリオを実行/検証。`--force`は確認プロンプトを無効化（Runbook承認が必要）。
- **`tradectl journal review`**: 直近の承認チケットとユーザーコメント、戦略別KPIを表形式で表示。`--weeks 4`等で期間指定。
- **`tradectl benchmark compare`**: ベンチマークCSVと最新エクイティを比較し、ギャップと指標差を出力。`--plot`で差分チャートを生成。
- **`tradectl stress run <scenario>`**: ストレステストシナリオを実行し、結果を`reports/stress/<scenario>/index.md`へ書き出す。`--sensitivity spread=1.5`等で感度上書き。
- **`tradectl metrics report`**: JSONLメトリクスから統計を集計し、Markdown/JSONサマリーを出力。`--window`（既定24h）、`--format {md,json}`、`--output`をサポート。Prometheus互換エンドポイントを起動する`serve`サブコマンドはM2でFeature Flag経由で追加予定。
- **JSON Linesインターフェース**: CLIコマンドは`stdout`にJSON Linesを返し、他ツール（例: `jq`）との連携を容易にする。例:`tradectl board --view json`で同一データをJSON Linesとして出力。
- **エラー挙動**: コマンド実行失敗時は非ゼロ終了コードを返却し、`stderr`に`[ERROR] <message>`形式で出力。必要に応じて`--no-prompt`（確認ダイアログ無効化）や`--yes`（承認操作の即時実行）を提供し、HITL確認はデフォルトでY/Nプロンプトを表示。
- **リスク開示と`audit`イベント連携**: `RiskDisclosureService`は承諾バージョンと期限を`consent_state.json`に保存し、承諾/拒否/期限切れイベントを`audit`イベントストアへ`risk_consent`タイプで記録する。このイベントには承諾文言・表示バージョン・ユーザーID・端末識別子・同意取得時刻・ダイアログ文面ハッシュを含め、WORMディレクトリへ書き出す。CLI各コマンドは実行前に`consent_state`と最新`risk_consent`イベントIDを参照し、承諾未取得時は`[WARN] Risk disclosure consent required`を出力して終了する。承諾ダイアログを通過した操作は`audit`イベントに`consent_reference_id`（最新`risk_consent`イベントID）と`consent_version_hash`を付与し、週次ガバナンスレポートと監査エクスポートでトレースできるようにする。
- **終了コードガイド**: `0=Success`, `10x=Validation/入力エラー`, `20x=I/O・データ欠損`, `30x=内部例外（トレース表示）` とし、Runbook・テストケースで参照する。

> **注記（イベントログ命名の共通方針）**: 本書ではイベントログ/監査ログを日次ローテーション（`logs/events/<YYYYMMDD>.jsonl`）で統一しています（参照: 「イベントログ/監査」「監査ログ」節）。CLI仕様も同一命名に従い、別名義のファイルは使用しません。

### 3.2 処理シーケンスと並行性
1. **Bar Ingestor（Producer）**: `asyncio`タスクで5分足を取得し、`bar_queue`（`asyncio.Queue(maxsize=1)`）に最新バーを投入。過去バーと重複の場合はスキップ。
2. **Pipeline Worker（Consumer）**: 単一ワーカーが`bar_queue.get()`でバーを受け取り、Feature→Regime→Signal→Execution→Risk→Sizing→Ticketの同期パイプラインを実行。各ステージは`PipelineContext`を介して共通キャッシュ/設定にアクセス。
3. **Event Dispatcher**: パイプライン結果を非同期タスクに渡し、Event Bus publish、JSONL書き込み、メール送信を行う。`asyncio.create_task`でバックグラウンド実行。
4. **Snapshot Writer**: パイプライン完了後に`Snapshot Manager`が更新された`AccountState`と未処理チケットを保存。CLIはこのスナップショット/ログを参照するため、パイプラインとは疎結合。
5. **並列性ポリシー**: M1は順次実行（1ワーカー）で整合性優先。将来はステージごとに並列化を検討し、`Signal Engine`を非同期化、`Risk Manager`で排他制御を行う。
6. **サイドタスク**: Emergency Orchestratorは`asyncio.create_task`で常駐し、`HealthState`と`emergency.yaml`監視を行う。Observability ExporterはM1ではバックグラウンドワーカーとしてJSONL書き出しとサマリー生成を担当し、M2+で有効化するHTTPサーバはスタブを保持する。StressTest/Benchmarkジョブは`asyncio.Queue`ベースのワーカーで逐次処理する。

### 3.3 チケット状態遷移（M1）
```
 proposal ──approve──▶ approved ──hand_off──▶ filled
      │                │                       │
      ├─reject────▶ rejected                  └──timeout──▶ expired
      └─ttl_expire──▶ expired
```
- `proposal`: Signal Engine直後の初期状態。TTL監視開始。
- `approved`: ユーザー承認後。手動発注が行われ、`hand_off`イベントで`filled`へ遷移。`oco_set`が真になると完了扱い。
- `rejected`: ユーザー却下時。監査ログに理由を残し、再承認不可（新規シグナルとして再生成）。
- `expired`: TTL切れやSpread/Health要因で無効化。`tradectl ticket revive`（M2+想定）までは再利用不可。
- 状態遷移はAudit Trailに記録し、CLIは現在状態を表示。詳細設計では遷移ごとに検証フック（SL/TP入力確認等）を実装する。

### 3.2 CLI実装ガイド
- **構成**: `src/interfaces/cli/`配下に`__init__.py`と`board.py`, `tickets.py`, `events.py`, `status.py`, `export.py`を配置。`typer`でコマンドグループ化し、`tradectl/__main__.py`でエントリポイントを提供。
- **データアクセス層**: JSON Lines読み込みは`src/infrastructure/log_store.py`で共通化。`iter_events(path: Path, event_type: str | None)`ジェネレータを定義。
- **Board描画**: `rich.table.Table`を利用。共通フォーマッタは`src/interfaces/renderers.py`にまとめ、スコア強調・TTLカラーリングの関数を用意。イベント入力は`logs/events/<YYYYMMDD>.jsonl`命名の最新ファイルを`src/interfaces/cli/board.py`で日付ソートして解決し、見つからない場合は明示的なエラーを返す。`RiskMetricsSnapshot`を受け取った際はヘッダに`R_eff`バナーと通貨バケット別エクスポージャのサマリテーブルを差し込み、Correlation Guard本体（M1.1予定）が同ペイロードを拡張できるよう`correlation_snapshot`構造体を先行導入する。
- **承認系コマンド**: `tickets.py`で `TicketRepository`（persistenceレイヤ）をDI。承認結果を`AuditTrailService.log()`に渡し、成功時はCLIに`Approved ticket <id>`を表示。
- **イベント監視**: `events.py`では`watchdog`等に依存せず、5秒間隔でファイル末尾をtailする簡易実装。M2以降でWebSocket通知に切替可能な構造にする。
- **テスト**: `tests/interfaces/test_cli_board.py`で`CliRunner`を用いたsnapshotテストを追加。サンプルイベントファイルは`tests/fixtures/events/`に配置。
- **メトリクス収集**: CLIコマンド実行時間を`metrics/cli_perf.jsonl`に追記するオプション（`--metrics`) を用意し、運用時にボード表示のレスポンスを計測可能にする。
- **設定優先順位**: `ConfigRegistry`は `CLIフラグ > 環境変数 > profile YAML > デフォルト値`の順に評価。CLIで`--profile`を指定しなければ`config/profile_live.yaml`が既定。環境変数は`CODEX_`プレフィックスで上書き。
- **検証データ支援スクリプト**: `make data-build`でDukascopy→Parquet変換、`make sla-report`で`metrics/pipeline_latency.jsonl`と`metrics/data_ingestion_sla.jsonl`（`phase=fetch|processing`）のSLA集計を実行し、取得遅延・処理遅延・レート制限イベントを分離したレポートを`reports/validation_log/AC-45_sla_<date>.md`へ出力する。月次は自動生成ノートのみを追記し、四半期レビュー時にRunbook承認者がまとめてサインオフする。CIでは`make validation-check`を追加し、Validation Data Playbookのサインオフとハッシュ整合を自動検査する。

## 4. データ構造と保存先
- **マーケットデータ**: Parquet（ローカル）、キー: `{symbol}/{timeframe}`。カラム: ts, open, high, low, close, volume, spread(optional)。
- **特徴量キャッシュ**: Arrow/Parquet（将来）。MVPはオンメモリ計算＋serializeオプション。
- **イベントログ/監査**: JSON Lines（`./logs/events/DATE.jsonl`）。
- **設定**: YAML (`config/*.yaml`) + JSON Schema (`cfg.schema.json`)で検証。
- **バックテスト結果**: SQLiteまたはParquetで保存し、メタ情報（期間・戦略ハッシュ）を付与。
- **レポート**: Markdown/HTML/PDF生成を想定。MVPはMarkdown。
- **ストレステスト結果**: `reports/stress/<scenario>/index.md`および`metrics.json`を出力し、感度別チャート（Plotly PNG）を保存。
- **アカウント台帳**: モード別に保存形式を切替。Backtestは`backtests/results.db`内に`equity_curve`/`positions`テーブル、Paperは`logs/paper_account.jsonl`、Liveはユーザー入力CSVを`data/account/live_account.csv`で管理し、`AccountState`再構築時の入力とする。Live CSVのヘッダは`ticket_id, signal_id, fill_ts, fill_price, quantity, pnl, comment, ...`（将来拡張列は末尾追加）とし、HITLチケットの承認ログと約定実績を`ticket_id`/`signal_id`で突合。取り込み時に監査ログ（`logs/audit/live.jsonl`）へ`actual_fill_imported`/`actual_fill_import_summary`（失敗時は`actual_fill_import_failed`）イベントを追記し、スリッページ（提案価格との差分）や整合結果を保存する。
- **トレードジャーナル**: `data/journal/journal_entries.db`（SQLite）に`tickets`, `notes`, `metrics`テーブルを持ち、コメント/評価/スクリーンショットパスを保存。Markdown出力は`reports/journal/<week>.md`。
- **カレンダーデータ**: `config/calendar/high_impact_events.csv`（経済指標）と`config/calendar/market_holidays.csv`（休日/ロールオーバー/Fix時間帯ルール）。週次で外部API同期（任意）しつつ、最新版CSVを起動時にロードし、Fixは影響度に応じて±15/30分の自動禁止窓を生成（FR-34, FR-40）。
- **カレンダーデータ基準**: CSVは全てUTCで記録し、`config/profile.yaml`の`trading_timezone`（例:JST/NY）へ変換して適用。DSTを持つタイムゾーンは`zoneinfo`で自動補正。
- **換算レート**: `data/account/fx_rates.parquet` に口座通貨換算用レート（5m最新値と日次終値）を保存し、リアルタイム評価と日次集計で使い分ける。
- **ブローカー仕様**: `config/broker_rules.yaml`でpip値、contract size、最小ロット、tick size、stop level/freeze levelを定義し、ロード結果を`BrokerSpecs`キャッシュとして全モジュールで参照。
- **スワップテーブル**: `config/swap_rates.csv`に通貨ペア×方向（long/short）の日次スワップポイント、三倍日フラグ、ロールオーバー時刻を格納。Funding Serviceが`swap_rates.parquet`へ変換し、`positions`テーブルと突合してキャッシュフローへ反映（FR-28）。
- **スプレッドメトリクス**: `data/spread_metrics.parquet`にスプレッド/手数料の観測結果を保存し、イベント影響や時刻別平均を蓄積してSpread Monitor/Riskが参照。バックテスト時はDukascopyティック/分足からBid/Askを再構成し、観測出来ない区間は`broker_rules.yaml`の固定スプレッドテーブルで補完。必須列は`ts(datetime[ns,UTC])`, `symbol(str)`, `bid(float)`, `ask(float)`, `spread_pips(float)`, `provider(str)`。
- **流動性モニター**: `data/liquidity_monitor.parquet`に5分毎のBid/Ask乖離、板厚（推定）指標、更新遅延を記録。必須列は`ts`, `symbol`, `provider_primary`, `provider_secondary`, `spread_primary`, `spread_secondary`, `zscore_spread`, `zscore_depth`, `quote_age_ms`。乖離閾値超過は`liquidity.alert`イベントに記録し、解除操作の監査IDも保持する。
- **執行モデルテーブル**: `config/execution_model.yaml`に時間帯×レジーム×シグナル種別ごとの滑り分布（p10/p50/p90）、Marketable Limit保護幅、IOC扱い可否、Human Delay分布を定義し、Execution Modelが参照。
- **手動入力CSV（`data/account/live_account.csv`）**: ヘッダ`ticket_id, signal_id, fill_ts, fill_price, quantity, pnl, comment`を基本とし、必要に応じて`slippage_override`, `fees`, `tags`等を末尾拡張。`fill_ts`はISO8601(JST)、`quantity`はロット数。
- **相関メトリクス**: `data/correlation/`以下に通貨バケット別エクスポージャ履歴と相関行列（Parquet/PNGヒートマップ）を保存し、リスク検証に利用。初期データセットはValidation Data Playbook（要件定義§8.2, AC-09）で指定した直近30営業日を`data/correlation/initial/bootstrap.parquet`として固定し、Paper運用中は週次（日曜JST）で`tradectl correlation snapshot --window 30d`を実行して`<YYYYWW>_correlation.parquet`/`heatmap.png`を追加する。更新ログは`reports/validation_log/AC-09_<date>.md`に貼り付け、Runbook `docs/runbooks/RUN-RISK-01.md`のチェックリストでサインオフする。
- **パラメータ履歴**: `data/optimization/history/`配下に最適化設定と結果をJSONで保存し、`parameter_drift.parquet`に主要パラメータの時系列を記録。ドリフト検知はここを参照する。
- **ベンチマークデータ**: `data/benchmark_feeds/*.csv`に外部シグナル/指数の履歴を格納。必須列は`timestamp, equity, metric_sharpe, metric_dd`など。取り込み時に`benchmark_registry.json`へメタデータを書き込む。
- **監査ログ**: `logs/events/`配下に日次ローテーション。`event_type`毎に索引ファイルを生成し、`Audit Trail Service`が二重書き込み結果をチェックサムで検証する。
- **設定変更ガバナンス**: `logs/config/changes.jsonl`に`cfg_hash_before/after`、安全/危険分類、適用時刻を記録。週次で`ConfigDriftReport`を生成（FR-23, FR-33）。
- **緊急プロトコル**: `config/emergency.yaml`にシナリオ/条件/アクション列を保持。`config/risk_policy.yaml`と整合性チェックし、ハッシュを`logs/config/emergency_hash.json`へ出力。
- **データマニフェスト/署名**: `reports/data_manifest.json`に利用データセットのハッシュ/期間/取得元/バージョンを列挙し、`reports/data_manifest.sig`にEd25519署名を保存。`tradectl data verify`で検証し、アーカイブZIPへ両ファイルを同梱（FR-25, FR-52）。

### 4.1 Catch-up / Resync フロー
- **開始トリガー**: 起動時・手動`tradectl resync`・データ欠損検知時にSession Managerが`resync`タスクを起動。`Scheduler`が`AsyncOneShotJob`として登録し、他ジョブと排他制御を行う。
- **欠落検知/ジョブ投入**: 最新スナップショットと`logs/events`内の`MarketUpdate`タイムスタンプ差分、`data/runtime/<symbol>.parquet`のギャップ解析を組み合わせて欠落バー区間を特定。欠損期間とティッカー数に応じて`BackfillJob`を分割し、`priority`を`catch_up_lag_minutes`に基づき付与する（30分超=critical、20分超=high、その他=normal）。
- **バックフィル実行**: Data Ingestionが`BackfillJob`を取り出して欠落期間を優先的に取得し、Parquetキャッシュを更新。主要4ペアの`catch_up_lag_minutes`は`metrics/data_ingestion_sla.jsonl`に記録し、30分超過で`HealthMonitor.raise(level='critical', reason='data_latency_catch_up')`を発火してAcceptable Degradation（代替ソース＋手動CSV）フローに切り替える。切替時は`tradectl data failover --mode manual`で承認ログを残す。
- **増分再計算**: Feature Engineはバックフィル区間とTTL=3*TFぶんを再計算し、それ以外はキャッシュ値を再利用。`Workflow Orchestrator`はCatch-upモード中`fast_forward`で順次処理し、失敗したバーは`RetryQueue`へ再投入する。
- **シグナル評価**: 再計算したバーについてRegime/Scoring/Execution/Risk/Sizingを再実行し、TTL切れやドリフト超過のチケットは自動失効マーク。Acceptable Degradation中は`BoardMode=guarded`で新規提案を継続し、`ResyncCompleted`イベント後に通常モードへ自動復帰させる。
- **スナップショット更新**: 処理完了後に`./snapshots`へ状態を保存し、復旧時のレイテンシを最小化。`ResyncCompleted`には`catch_up_elapsed_sec`と`recovered_symbols`を含め、Runbookで承認を記録する。
- **品質ガード連携**: 欠損率>0.5%/日または外れ値比率>0.2%検知で`DataQualityAlert`イベントを発火し、Risk Managerへ`DATA_STOP`フラグを送信。Kill SwitchがSOFT_STOPへ遷移し、新規提案は抑止。復旧後3バー連続で正常値を確認したら自動解除。
- **カレンダー/レート/スプレッド/相関/マニフェスト更新**: Resync完了後に各サービスが差分を検出し、必要な補完・再計算・補間フラグ付与・マニフェスト再集計を実施する。詳細は従来通りだが、Catch-up期間中に生成された代替ソースのハッシュとRunbook承認者IDを`reports/validation_log/AC-45_sla_<date>.md`へ追記する。

### 4.2 マルチタイムフレーム更新
- トリガーTF（既定:5m）のバー確定ごとに、下記リングバッファを更新し上位TFを再構築。
  - 1時間足: 12バーごとにOHLCVを確定し、途中値は局所バッファで累積。
  - 日足（将来拡張）等も同様に`TF_ratio`を用いた集約を準備。
- Feature Engineは`changed_timeframes`セットを保持し、変化したTFのみテクニカル指標を再計算する。
- 欠損や遡り更新が発生した場合は影響範囲（例えば1時間足なら直近3本）を再計算し、その他はキャッシュ値を保持する。
- M1ベース戦略では5分足パーケットと1時間足キャッシュを`data/research/curated/<symbol>/`配下で共通ハッシュ管理し、Backtest時に同一の`multi_tf_joiner`が再利用される。ライブ運用時は直近1時間足バーの確定値が`FeatureFrame.htf_filters`へ差し込まれ、遅延判定（Δt）の補正対象時刻としてExecution Modelへ引き継がれる。

### 4.3 口座通貨換算ポリシー
- **リアルタイム評価**: Live/Paperモードでは最新5分足の終値またはブローカー提供のBid/Ask中央値を使用し、`AccountState`内の証拠金・含み損益を口座通貨へ換算。
- **フォールバック**: リアルタイムレートが取得できない場合は最後に取得した値を保持し、Catch-up時に正式な終値へ補正。
- **日次集計**: レポート/リスク指標の集計には日次終値を利用し、Backtestの結果と一致させる。
- **記録**: リアルタイム換算値と日次終値を両方`fx_rates.parquet`に保存し、監査時に追跡可能とする。
- **クロスレート優先順位**: 直接ティッカーが存在しない場合は`USD`経由（例: EURUSD × USDJPY）を第一優先、次に`JPY`/`EUR`等のバックアップ経路を設定し、経路と適用時刻を`fx_rates.parquet`へ記録する。
- **安定化**: クロスレート経路は`fx_rates.parquet`内に`source_priority`列を持ち、1位ソースとの差異が閾値超過した場合は`RateAnomaly`イベントを`Audit Trail Service`へ送信する（FR-21と整合）。

### 4.4 レート更新スケジュール
- **5分更新**: トリガー足確定時にFX Rate Updaterが必要通貨ペアの最新値を取得し、差異>0.02%または1時間経過で`fx_rates.parquet`を上書き。
- **プロバイダ別更新頻度/再接続**: yfinanceは5秒間隔でHTTPポーリングし、失敗時は`RetryPolicy(max_attempts=3, backoff=1.5)`で最大約17秒まで再試行。連続失敗3回で`HealthMonitor`へ`rates_warning`、10回で`rates_critical`を通知し、`tradectl fx-rate reconnect --provider yfinance`または自動切替でDukascopyへ移行する。Dukascopyは2秒間隔でREST呼び出し、`retry<=5`の指数バックオフ（最大20秒）、WebSocket（M2+）は`ping_interval=15s`/`pong_timeout=5s`で監視し、`tradectl fx-rate reconnect --provider dukascopy`で手動再接続。手動CSVモード時は更新を5分周期に限定し、Runbook承認後に`tradectl fx-rate resume`で自動更新へ戻す。

- **日次補正**: ロールオーバー後に終値ベースのレートを取得し、当日のリアルタイム値との差異を記録。補正後に`AccountState`の過去分も再計算。
- **ソース優先度/手動切替**: 1) yfinance 2) 直近成功値（`fx_rates.parquet`キャッシュ）3) 手動CSV（Runbook承認必要）を既定とし、M2以降はブローカーAPIを追加。`tradectl fx-rate switch --to <provider>`で優先度を一時変更でき、切替操作は`reports/audit/rates/<date>.md`へ記録する。ライセンスや利用制限の確認チェックリストは切替ワークフロー内で必須。
- **ロック戦略**: レート更新は専用`RatesLock`を取得したFX Rate Updaterのみが実行。Spread MonitorとCorrelationバッチも同一ロックを共有し、Resync/バックフィル中は収集タスクを一時停止（ロック待機）して整合性を確保。更新失敗時はロールバックしてロック解放。
- **ヘルスチェック/SLA**: `rates_metrics.jsonl`へ`rates_latency_seconds{provider}`/`rates_success_total{provider}`を記録し、30日ローリングで**yfinance: p95≤60秒・p99≤120秒・成功率≥97.5%／Dukascopy: p95≤15秒・p99≤25秒・成功率≥99.0%**を監視する。`p99`や`success_rate`が閾値を超過/下回った場合は`HealthMonitor.raise('warning','rates_latency', provider=...)`、`latency_sec>60`や連続10失敗で`raise('critical', ...)`を発行し、Reduce-Only Advisorへ縮小提案フラグを通知する。解除後は`tradectl fx-rate ack`でオペレータ承認を記録し、監査ログに回復イベントを残す。

### 4.5 スプレッド観測スケジュール
- **観測ソース/更新間隔**: M1はDukascopyティック/公開CSV/手入力CSVから事前集計したヒストリカル分位を利用し、Spread Monitorは`spread_metrics.parquet`を更新。ライブ時はyfinance/TWAP補助を**5秒間隔**でチェックし、ブローカーフィード（M2+）は**1秒ポーリング**またはWebSocket購読で追記。各ソースは`provider`列で識別し、更新間隔・最終取得時刻を`spread_provider_health.jsonl`に記録する。
- **ヘルスチェック/SLA**: `spread_provider_health.jsonl`に`spread_latency_seconds{provider}`と`spread_success_total{provider}`を記録し、30日ローリングで**yfinance: p95≤60秒・p99≤120秒・成功率≥97.5%／Dukascopy: p95≤15秒・p99≤25秒・成功率≥99.0%**を監視する。閾値超過で`HealthMonitor.raise('warning','spread_latency', provider=...)`、60秒超停止や連続10失敗で`raise('critical', ...)`を発行し、`tradectl spread ack --provider <name>`による承認が完了するまでSpread Monitorは`halt`状態を維持する。
- **フェイルオーバー/手動切替**: `critical`イベント発火時はDukascopy→ブローカーフィード→ローカル統計の順に自動切替し、各ステージを`spread_failover_stage`でトラッキングする。手動で代替ソースへ切り替える場合は`tradectl spread switch --to <provider>`を使用し、理由・承認者を`reports/audit/spread/<date>.md`へ記録する。フェイルオーバー解除は安定化確認（5分連続で閾値内）後に`tradectl spread resume`で実施。
- **アラート/Runbook連携**: `warning`イベントはCLI通知＋メール（M2: Slack）で即時共有し、Runbook `RUN-SPREAD-03`のチェックリストを案内。`critical`イベント時はKill Switchと連動し、新規提案を凍結したうえでオペレータに`tradectl spread ack`とRunbook記録を要求する。毎週の`tradectl spread report`でSLA達成率・フェイルオーバー履歴・ライセンスチェック完了状況をレビューする。
- **イベントタグ付与**: カレンダーイベント発生前後±60分のデータにタグを付け、分析時にイベント影響を評価できるようにする。
- **バックフィル**: Spreadデータ欠損時は公開CSV/自前記録を再取得し、欠損区間の平均/分散を補完。ブローカーフィードが利用可能な環境では補完候補に追加。バックテストではDukascopyティックから再構築し、該当データが無い場合は固定スプレッドで代替。
- **長期集計**: 日次で時間帯別（東京/ロンドン/NY）平均とp95を集計し、Risk/Position Sizerがスプレッドシナリオ検証に利用。バックテストレポートにも同じ集計を出力し、ライブとの差分を監視。
- **健全性ガード連携**: SPRTやKill Switchがアクティブな場合、Spread Monitorはスプレッド閾値を自動引き下げ（例: 10%）て追加保守モードへ移行し、解除時には監査イベントを記録する（FR-22）。SpreadCooldownState解除時はExecution Modelへ通知し、Marketable Limit幅を通常値に復帰させる。
- **マーケットプロファイル**: Spread MonitorはExecution Modelへ時間帯×レジーム別スリッページ分位を提供し、BT/ライブ整合性を強化（FR-27）。

### 4.6 相関評価スケジュール
- **ローリング計算**: 1日単位で通貨バケット別エクスポージャとシンボル相関を30日ローリングで算出し、`CorrelationMatrix`を更新。
- **ライブモニタ**: 新規提案前に最新エクスポージャと相関を即時計算し、許容バケット（例: 通貨別最大2件など）を超える場合はCorrelation Guardがシグナルを抑制。
- **シナリオ検証**: 週次バッチで過去12ヶ月の相関変動レンジを計測し、Riskポリシー（許容相関閾値）の再設定候補をレポート。
- **データ保存**: 生成した相関行列は`data/correlation/`にParquetとPNGで保存し、監査および分析用に残す。
- **Reduce-Only判定**: 相関異常で`R_eff`が`R_cap`を超えた場合はCorrelation GuardがReduce-Only Advisorへ縮小対象候補を提示し、寄与度に基づく優先順位を付ける（FR-37, FR-42〈M2+〉）。

### 4.7 スワップ/ファンディング管理
- **取得経路**: `config/swap_rates.csv`（ユーザー管理）を基軸に、公開CSV/手入力で更新する。M2以降でブローカー提供のCSV/APIを追加し、優先度は `swap_rates.csv > 手入力 > broker_api` を既定とする。取得に失敗した場合は最終成功値を維持しつつ`FundingDegraded`イベントを発火。
- **正規化**: スワップは1ロットあたりの通貨建て値で保持し、`BrokerSpecs.min_lot`と`lot_step`で換算。`pip_size`と`price_decimals`に基づき丸めを行い、Human Errorチェックにも同じ丸め関数を提供。
- **適用タイミング**: Backtest/Paperはバー確定時に日次スワップを計上。Liveではロールオーバー時刻（例: 06:00 JST）に`FundingService.apply_daily_swap()`を発火し、`AccountState`に`swap_realized`を追加。
- **三倍日処理**: `swap_rates.csv`の`triple_day`列で曜日/祝日特例を管理。Funding ServiceはCalendar Serviceと連携して祝日シフトを検出し、該当日のスワップ倍率を補正。
- **シミュレーション設定**: Execution Modelに`funding_cost_curve`を渡し、約定時に想定保有期間×スワップを`ExpectedR`へ反映。Hybridスコアの`PF_recent`/`PF_all`計算でもスワップ控除後の損益を使用し、AC-18/AC-23の耐性評価と整合させる。
- **監査/可観測性**: `logs/events/funding.jsonl`で取得/適用イベントを追跡し、異常値や適用失敗はAlert Dispatcher経由で通知。ダッシュボードでは`swap_realized`と`swap_forecast`を可視化してNFR-06/11の指標に反映。

### 4.9 設定ファイル・モデルサンプル
- **`config/execution_model.yaml`（抜粋）**
```yaml
slippage:
  EURUSD:
    trending:
      p10: 0.3
      p50: 0.8
      p90: 1.6
    ranging:
      p10: 0.2
      p50: 0.5
      p90: 1.2
protection_pips:
  default: 3.0   # FR-39 / AC-32
  high_volatility: 4.5
marketable_limit:
  enable: true
  timeout_sec: 60
```
- **`spread_metrics.parquet`カラム定義**: `ts (datetime[ns, UTC])`, `symbol (str)`, `bid (float)`, `ask (float)`, `spread_pips (float)`, `provider (enum[yfinance,dukascopy,csv,broker])`, `regime (enum[trending,ranging,volatile,calm])`, `source_tag (str)`。
- **`broker_rules.yaml`例**
```yaml
symbols:
  USDJPY:
    pip_size: 0.01
    min_lot: 1000
    lot_step: 1000
    stop_level_pips: 5
    freeze_level_pips: 3
  EURUSD:
    pip_size: 0.0001
    min_lot: 1000
    lot_step: 1000
    stop_level_pips: 4
    freeze_level_pips: 2
```

### 4.8 ファイル/ディレクトリ規約（M1）
- `config/`
  - `profile_<name>.yaml`: ランタイム設定。`config/profile_live.yaml`を既定とし、`cfg_hash`はSHA256。
  - `calendar/high_impact_events.csv`: UTCタイムスタンプ列`event_ts`, `currency`, `impact`, `title`, `window_minutes`。
  - `broker_rules.yaml`: `symbols.<pair>.{pip_size,min_lot,stop_level_pips}`を格納。
- `data/raw/<provider>/<symbol>/<timeframe>.parquet`: 取得済みOHLCV（UTC）。カラム: `ts, open, high, low, close, volume`。
- `data/cache/features/<symbol>_<tf>.parquet`: 指標キャッシュ。カラム: `ts, feature_name...`。マルチTFは`feature_name__tf`で区別。
- `data/spread_metrics.parquet`: カラム`ts, symbol, bid, ask, spread_pips, regime, source`。
- `data/account/fx_rates.parquet`: `ts, pair, mid, source_priority`。
- `logs/events/<YYYYMMDD>.jsonl`: Domainイベント。1行1 JSON、`event_type`と`payload`必須。
- `logs/audit/<YYYYMMDD>.jsonl`: HITL操作痕跡。フィールド`ticket_id, action, user, delta`。
- `logs/ops/*.log`: 手動オペレーション（rates/calendar/spread等）を記録。
- `snapshots/latest/{account_state.json, open_tickets.json}`: 再起動用スナップショット。
- `reports/export/<YYYY-MM-DD>/...`: CLIエクスポートファイル置き場。命名規約`<resource>_<timestamp>.<ext>`。

## 5. 外部インターフェース
- **データ取得IF**:
  - yfinance: REST/HTTP (pandas-datareader API)。APIキー不要。短期保持制約あり。
  - Dukascopy: HTTP/バイナリ。`dukascopy` Pythonライブラリを利用。ローカルキャッシュ必須。
  - CSV: ローカルファイル。ユーザー指定パス。
- **通知**: MVPではメール（SMTP）。Slack WebhookはM2で追加。
- **GUI/WebSocket**: `/ws/signals` エンドポイント（将来）。M1はCLIベース。

## 6. モジュール別機能割り当て
| モジュール | サブ機能 | 主な入力 | 主な出力 |
| --- | --- | --- | --- |
| ingestion | providerアダプタ、キャッシュ、品質監視 | config、APIレスポンス | MarketDataFrame |
| indicators | 時間足変換、テクニカル指標 | MarketDataFrame | FeatureFrame |
| strategies | ルールストラテジ、スコアリング | FeatureFrame, RegimeState | RawSignals |
| regime | レジーム検出、ヒステリシス | FeatureFrame | RegimeState |
| account | 残高・証拠金・ポジション集計（単一口座）。R計算と余力算出を各モード共通ロジックで提供 | TradeLogs, `reports/performance/paper/<run_id>.parquet`, BrokerSnapshot | AccountState |
| account_aggregator | 複数口座統合、口座別Rガード、相関用エクスポージャ算出（FR-58, M2+） | `accounts/<broker>/<account_id>.yaml`, Broker API, Portfolio Parquet | AggregatedAccountState |
| fx_rates | レート取得・クロス計算 | yfinance, fx_rates.parquet, 手入力CSV (M2+: BrokerFeed) | FxRateCache |
| calendar | 経済指標ブロック, 休日/ロールオーバー制御 | events.csv, holidays.csv, API同期 | GateState |
| broker_specs | ブローカー仕様ロード | broker_rules.yaml | BrokerSpecs |
| spread | スプレッド観測・集計・クールダウン制御 | spread_metrics.parquet (Dukascopy/CSV, M1) / BrokerFeed (M2+) | SpreadMetrics, SpreadCooldownState |
| liquidity | マルチソースレート比較・乖離Zスコア計算 | yfinance, Dukascopy, broker API/CSV | LiquiditySnapshot, LiquidityAlerts |
| execution | Fill/滑り/Marketable Limitモデル | MarketData, SpreadMetrics, execution_model.yaml | ExecutionAdjustments |
| scoring | M1: 基本スコアリング（expected\_R, PF\_all） / M2+: ハイブリッド最適化＋Stability | RawSignals, BacktestStats | RankedSignals |
| funding | スワップレート取得・適用・三倍日処理 | swap_rates.csv(公開CSV/手入力, M1), CalendarState (M2+: broker_api) | FundingCurve, FundingEvents |
| risk | 残余リスク計算、Kill Switch、マージン/スプレッド監視 | RankedSignals, AccountState, BrokerSpecs, SpreadMetrics, SpreadCooldownState, FundingCurve | RiskVettedSignals, HealthState |
| correlation | 通貨/シンボル相関評価 | AccountState, MarketData | CorrelationMatrix |
| correlation_guard | 相関ガード・バケット制御 | RiskVettedSignals, CorrelationMatrix | CorrelationFilteredSignals |
| sizing | Fixed Fractional、サイジング検証 | CorrelationFilteredSignals, AccountState, BrokerSpecs, FxRateCache, SpreadMetrics, ExecutionAdjustments | SizedSignals |
| compliance | レバレッジ/建玉/規制検証と代替案提示 | TradeTickets候補, BrokerSpecs, risk_policy.yaml | ComplianceResult, AdjustedTickets |
| capital_guard | VaR/ES監視と提案スロットリング | AccountState, RiskExposure, risk_policy.yaml | CapitalGuardState, RateLimiter |
| reduce_only | Reduce-Only判定・提案（M2+） | SizedSignals, HealthState, GateState | ReduceOnlyTickets |
| ticket | TTL算出、OCO値提案、ヒューマンチェック、監査追跡 | SizedSignals ∪ ReduceOnlyTickets, BrokerSpecs | TradeTickets |
| backtester | シミュレーション、WFA | MarketData, Strategies | PerformanceStats |
| reporter | 指標集計、グラフ化 | PerformanceStats, Logs | Reports |
| persistence | Parquet/SQLite/JSONL管理 | 各種イベント | 永続化ファイル |
| data_provenance | マニフェスト生成・署名・検証 | AssetWriteEvents, HashConfig | Manifest, Signature |

### 6.1 シグナル・リスク・サイジング連携
- **Signal Engine**は`StrategyPlugin`抽象基底クラスを介してルール/モデル（FR-04）をロードし、`evaluate(context)`で`RawSignal`を返却。プラグインは`@strategy_plugin(name="donchian_breakout")`などのデコレータ登録。`m1_baseline_ma_rsi`は`context.features['ema21']`/`['ema55']`/`['rsi14']`/`['ema55_slope']`/`['htf_bias_zscore']`を参照し、IS/OOS検証で固定したパラメータセット（`strategy_manifest.yaml::parameters`）をロードする。評価時に`dataset_hash`が現行Runと不一致の場合は`SignalValidationWarning`を返し、誤ったデータセットでの運用を防ぐ。
- **Execution Model**は`RawSignal`に`ExecutionAdjustments`（滑り補正、Marketable Limit保護幅、IOC有効期限、Human Delay Δt）を付与し、Backtest/Paper/Liveで整合したFill判定を行う（FR-27, FR-29, FR-39）。M1ではTriangular(30,45,75)秒の疑似遅延を既定とし、ライブ承認ログを`latency_samples.jsonl`へ追記してΔt分布を更新する。遅延後の`delayed_entry_price`を基点にATR由来のSL/TP距離を再計算し、OCO提案へ引き継ぐ。
- **Scoring Service**はM1では`BaseScore = α·expected_R + β·PF_all − δ·drawdown_penalty`（既定: α=0.6, β=0.4, δ=0.1）を評価し、単純な期待リターン重み付けでランキングする。`PF_all`は`reports/research/m1_baseline/validation_*.md`の値をキャッシュし、`dataset_hash`と`config_hash`が現行Runと一致しない場合は`score_status=pending`で順位から除外する。ハイブリッドスコア`HybridScore = w_recency·PF_recent + w_global·PF_all − λ·DD_all − γ·(1−Stability)`とStabilityキャッシュは〈M2+〉で有効化し、`scoring.hybrid_enabled` Feature Flagで切り替える。Spread Monitorがクールダウン中の場合はM1/M2いずれも`cooldown_penalty`で減衰させる（FR-41）。
- **Risk Manager**は`RiskPolicy`（per_trade, daily_loss, weekly_loss, SPRT thresholds, margin guard, spread guard）を参照し、Kill SwitchやSPRTフェーズ（FR-05, FR-22, FR-36）に応じて`SignalAction`（allow/defer/block/reduce_only）を出力。運用オペレーションはRunbook `docs/runbooks/RUN-RISK-01.md`（AC-03/AC-09）に沿ってKill Switch発火・解除、R_eff監視、週次レビューを実施する。
- **Risk Manager**は`RiskPolicy`（per_trade, daily_loss, weekly_loss, SPRT thresholds, margin guard, spread guard）を参照し、Kill SwitchやSPRTフェーズ（FR-05, FR-22, FR-36）に応じて`SignalAction`（allow/defer/block/reduce_only）を出力。運用オペレーションはRunbook `docs/runbooks/RUN-RISK-01.md`（AC-03/AC-09）に沿ってKill Switch発火・解除、R_eff監視、週次レビューを実施する。`RiskPolicy`には`base_capital_jpy`/`trade_frequency_estimate`を保持し、月次ジョブ`RiskSimulationJob`が`tradectl risk simulate --trials 10000 --horizon 252d`を実行してモンテカルロ指標（`Prob(max_drawdown>15%)`, `Prob(equity<0.8·base_capital)`）を算出・`reports/risk/capital_adequacy/<YYYYMM>.md`へ出力する。閾値逸脱時は`health.changed(reason=risk_capital_gap)`を発火し、Kill Switch閾値やポジションサイズ変更案をレビュー議題としてRunbookに追記する。
- **Liquidity Intelligence Service**は`quote_snapshot`ストリームから`LiquiditySnapshot`を作成し、`zscore_spread`/`quote_age_ms`が閾値を超えた場合に`liquidity.alert`をRisk Managerへ送信。Risk Managerは該当シグナルを`HOLD`に設定し、解除時は`liquidity.resume`イベントで再開（FR-49, AC-38）。
- **Correlation Guard**は`CorrelationMatrix`と`BrokerSpecs`から`R_eff`を計算し（FR-37）、超過時はリスク比重を削減またはシグナル除外。Reduce-Only Advisorへ優先クローズ候補を通知する。
- **Position Sizer**はFixed Fractionalを基本に、`SpreadMetrics`/`BrokerSpecs`/`FxRateCache`/`ExecutionAdjustments`を用いてR値を整合。`min_stop_distance`未満の場合は`Ticket Builder`へ補正案を返却（FR-38）。
- **Compliance Validator**は`TradeTickets`候補を受け取り、`broker_rules.yaml`の`max_positions`, `netting`, `fifo`, `leverage_limit`と`risk_policy.yaml`の`profile_limits`を照合。違反時は代替案（Reduce-Only/部分クローズ/サイズ調整）を生成し、承認不可としてTicket Builderへ返却（FR-50, AC-39）。
- **Capital Allocation Guard**は`AccountState`のエクスポージャとVaR/ESを計算し、`capital_guard.yaml`または`risk_policy.yaml`の閾値と比較。超過時は`rate_limit`をRisk Managerへ渡し、提案頻度や最大サイズを減衰させる（FR-51, AC-40）。解除条件が満たされると`capital_guard.released`イベントを発行。
- **Reduce-Only Advisor**は`HealthState`/`GateState`/`R_eff`/`free_margin`を監視し、条件一致時にポジション縮小案（Reduce-Only）を生成（FR-42）。M1 Coreでは自動発火を無効化し、Risk Managerが`SignalAction=reduce_only`を返したケースをSignal Boardへバナー表示＋手動チケットテンプレートとして渡す。Runbook `docs/runbooks/RUN-RISK-01.md`に減少サイズの目安（`min(|R_i|, 0.5R)`）とダブルチェック体制を追記し、承認ログは`reports/audit/reduce_only/<date>.md`へ記録する。
- **Ticket Builder**は`HumanErrorChecklist`（桁/丸め/TP/SL/OCO/ReduceOnly分類）を評価し、未充足項目はSignal Boardで赤バッジ表示（FR-30, FR-39）。M1では`oco_recommendation`（ATR倍率・min_stop_distance補正・protect_pips）と`latency_hint_sec`をチケットJSONに含め、Paper/Liveで計測した承認→OCO設定時間を`reports/performance/<mode>/latency_stats.json`へ蓄積しAC-09の判定に利用する。HITL運用・OCO常駐確認・丸め検証はRunbook `docs/runbooks/RUN-HITL-01.md`（AC-02/AC-10/AC-11）に準拠する。
- **Data Provenance Service**は`AssetWriteEvents`から`data_manifest.json`と`data_manifest.sig`を更新し、`tradectl data verify`に必要なハッシュ・署名を提供。検証失敗時は`data_provenance.alert`イベントを発火してHealth Monitorへ連携（FR-52, AC-41）。

## 7. 非機能要件への対応方針
- **性能**: pandasベース処理＋numba/ポリシー最適化と差分再計算キャッシュで5分足ストリーム遅延<100msを目標化。I/Oは非同期キューで平滑化。`perf_counter`計測を`on_bar_in`～`board_render`で常時実施し、p95/p99を`metrics/pipeline.jsonl`へ記録して`tradectl metrics report`で集計しNFR-01/AC-05を監視する。
- **信頼性**: イベントソーシング（JSONL）＋定期スナップショットで再現性を確保し、データ品質ガードとKill Switch、Calendar Gate、FXレート補完、スプレッド監視、相関ガードを統合して異常時やイベント期間中/レート欠損時/相関過多時の自動停止・再開・補正を実現。Resyncフェーズは二相ロックで`MarketData`と`FeatureCache`を凍結し、終了後にSPRTリセット条件を評価する。
- **運用性**: CLIコマンド `tradectl`（想定）で start/stop/status/resync を提供。Spreadクールダウン解除、Reduce-Only解除、Marketable Limit幅調整など執行関連の運用コマンドも整備する。
- **セキュリティ/コンプラ**: HITL前提で助言表示を限定し、`config/secret/*.yaml`はAES-256で暗号化。macOS FileVault + Keychainと連携し、復号操作をAudit Trailへ記録。Compliance Validator/Capital Guardの判定ログも`audit`へ記録し、半期ごとにルールセットをレビュー（NFR-04, NFR-17, NFR-18）。
- **拡張性**: Strategy/Scoring/Riskをプラグイン化（`entry_points` / 自前registry）。
- **再現性**: バックテスト/ライブの乱数seed、cfgハッシュ、データバージョンをレポート出力に埋め込み、`reports/*`のメタヘッダで差分検証可能とする（FR-25）。`FundingCurve`や`SpreadMetrics`など時系列キャッシュはハッシュ化してレポートに添付し、AC-13/AC-17とのトレーサビリティを担保する。
- **可観測性**: SpreadCooldownStateやReduce-Only発動履歴、Execution Modelの未約定率をメトリクス化し、NFR-06/NFR-11のダッシュボードに表示する。
- **ログ基準**: ログ分類を`application.log`(INFO), `debug.log`(DEBUG), `metrics/cli_perf.jsonl`に分離。機微情報（APIキー・個人情報）はログ出力しないガードを`SafeFormatter`で実装し、監査ログは最低1年保存。
- **メトリクス出力**: パイプライン処理時間、成功/失敗件数、SpreadCooldownState滞留時間を`metrics/pipeline.jsonl`へ記録。Prometheus対応の拡張ポイントとして`metrics/exporter.py`を用意し、閾値（例: pipeline p95>250ms, spread mismatch率>5%）超過でAlert Dispatcherが通知する。

### 7.3 セキュリティ・運用ガイドライン（NFR-04/05）
- `config/`以下の秘密情報（APIキー等）は`.env`もしくはmacOS Keychainから読み取り、リポジトリには含めない。設定ファイルは権限`600`で管理。
- 監査ログ(JSONL/SQLite)は改ざん検知のため日次でSHA256ハッシュを計算し`logs/checksums/`へ保存。1年保管、ローテーション時に暗号化バックアップ（将来対応）。
- CLI操作時はKill SwitchやReduce-Only解除など高リスクアクションに二段確認（Y/N＋`--yes`）を求め、操作履歴を`audit`イベントに記録。
- 外部API通信はTLS必須、タイムアウトは5秒既定。失敗時はリトライ回数を超えた段階で`DataDegraded`通知とKill Switchソフト停止を行う。
- ログ/スナップショットディレクトリは定期的に監査し、不正アクセス検知のためにOSレベルの監査（macOS FSEvents）と連携する（将来拡張）。M1はローカル運用を優先し、Slack WebhookやPrometheus Exporterなどの外部連携はM2以降で実装することを前提とする。

### 7.4 データ保全・ローテーション
- **バックアップ**: `data/`と`logs/events/`を日次インクリメンタル（rsync等）で取得し7世代保管。週次でフルバックアップを外部ドライブ/クラウドへ退避。
- **ローテーション**: `logs/events`は30日で圧縮（gz）し`archive/`へ移動。`reports/`は月次でアーカイブ、`snapshots/`は最新3世代を保持。
- **検証**: バックアップ後にSHA256チェックサムを比較し`logs/checksums/`に記録。復元テストは月1回、Runbookに従って実施。
- **オフラインバンドル**: `make bundle-offline`で`dist/offline_bundle/<version>.tar.gz`を生成し、SBOM/ハッシュ/署名を`bundles/<version>/manifest.json`へ記録。`make bundle-verify`でDR演習を行い、結果を`reports/audit/dr/<YYYYMM>.md`に保存する。

### 7.5 設定差分ガバナンス（NFR-25）
- **差分検証コマンド**: `tradectl config diff --profile prod --baseline main`で`dev|paper|prod`の差分を出力し、リスク関連パラメータの±10%超変更に`[WARN]`バッジを付与。`--require-signed`オプションは`config/signatures/<profile>.sig`を照合し、署名不一致時は終了コード`104`で拒否する。
- **CI連携**: `config_diff_test`ジョブがPull Requestで`tradectl config diff --profile prod --baseline origin/main --json`を実行し、リスク・マージン・Kill Switch関連フィールドに±10%超の変更があれば`policy_violation`を返す。承認者は`tradectl config sign --profile prod --approver <name>`で電子署名を更新。
- **監査出力**: 差分結果は`reports/audit/config/<YYYYMMDD>_<profile>.md`に保存し、電子署名メタデータを`config/signatures/ledger.json`に追記。Runbook `GOV-CONFIG-01`でレビュー手順と承認フローを定義する。
- **復元時整合性チェック**: スナップショット復元時は`cfg_hash`/`data_hash`の一致、未処理チケットと監査ログ最終イベントの整合、`HealthState`が`soft_stop`以上の場合の解除手順を確認し、Runbookへ結果をフィードバックする。
- **オフラインバンドル**: リリースごとに`dist/offline_bundle/<version>.tar.gz`を生成し、Wheel/SBOM/ハッシュリスト/`requirements.lock`を同梱。`make bundle-offline`で生成し、`bundles/<version>/manifest.json`にハッシュと作成者を記録。Bundleは暗号化メディアへ二重保管し、`make bundle-verify`でRPO/RTOテスト（4時間以内復旧）を月次実施する（NFR-24）。
### 7.6 レイテンシ測定計画（NFR-01/AC-05）
- **計測ポイント定義**: `SessionManager`起点で`on_bar_in`→`features_ready`→`signal_ranked`→`ticket_emitted`→`board_render`までを`perf_counter_ns`でトレースし、各区間の差分を`metrics/pipeline.jsonl`へ`{"metric":"latency","phase":"bar_to_board","p95_target":0.1,"elapsed_ms":...}`形式で追記する。`BoardMode=guarded`中も同一計測を継続し、代替ソース使用時の遅延を可視化する。
- **CLI応答計測**: `tradectl board`と`tradectl tickets approve`はTyperコマンドラッパで`metrics/cli_perf.jsonl`へ`render_ms`/`fetch_ms`/`persist_ms`を記録。`p95(render_ms)<100ms`, `p99<180ms`、ガード付きフロー時でも`p95<140ms`を受入基準とする。計測はPoetryスクリプト`poetry run python tools/measure_cli_perf.py --runs 50`で自動化し、CIの`make perf-check`で週次実施する。
- **テストと可視化**: `tests/perf/test_pipeline_latency.py`でメトリクスJSONLを読み込み、直近500サンプルのp95/p99が閾値未満か検証。失敗時は`pytest`をFailさせ、Runbook `docs/runbooks/RUN-PERF-01.md`に貼り付けるスパークライン（`tools/render_perf_chart.py`出力）を再生成する。`tradectl metrics report --kind latency --window 7d`で集計値とSLA逸脱サマリをMarkdown化し、週次レビューに添付する。
- **Acceptable Degradation時の運用**: `board_mode=guarded`発生時は`metrics/pipeline.jsonl`へ`board_mode`フィールドを追記し、通常値との差分を`reports/performance/pipeline_latency/<YYYYMMDD>.md`に自動集計。復旧条件は`bar_to_board.p95<100ms`かつ`cli.render_ms.p95<100ms`へ戻ることとし、解除時に`degraded_recovered`イベントへ測定値を添付する。

### 7.7 SLAテレメトリ閾値バリエーション計画
- **目的**: 実測データに基づき`HealthMonitor`の`fetch_delay`/`processing_delay`閾値を柔軟に調整し、季節性やプロバイダ変更時の過検知・過剰許容を防ぐ。
- **しきい値プロファイル管理**: `config/sla_thresholds/<profile>.yaml`を新設し、`provider`,`metric`,`window`別に`target`,`warning`,`critical`を定義。`config/defaults.yaml`の`health.threshold_profile`で読み込むプロファイルを切替え、CLI `tradectl sla profile switch --to <profile>`で即時反映する。
- **計測ベースライン生成**: `tools/sla/generate_profile.py`を追加し、直近30日`metrics/data_ingestion_sla.jsonl`を解析してp50/p75/p95/p99を算出。標準偏差と上限倍率（例: `warn = p95 * 1.15`, `critical = max(p99 * 1.25, p95 + 12s)`）を提示するMarkdownレポートと候補YAMLを出力する。
- **運用フロー**: 週次レビューで`reports/ops/sla_review/<YYYYWW>.md`を更新し、`profile_candidate.yaml`との差分を確認。承認後は`tradectl sla profile apply`で`config/sla_thresholds/active.yaml`へ昇格し、旧プロファイルは`archive/`へ移す。
- **自動チューニング準備**: M2以降に向けて`metrics/data_ingestion_sla.jsonl`へ`profile_version`を付与し、将来のオンライン学習や実績差分（`observed - target`）を蓄積。Deviationが連続3回閾値を超えた場合は`health.changed(reason=sla_threshold_mismatch)`でアラートし、手動レビューを促す。


### 7.1 M1テスト優先度とカバレッジ
- **必須自動テスト（CI）**
  - `pytest`ベースのユニット/統合テスト: データ取得（yfinance/Dukascopyモック）、Feature Engineの指標再計算、Signal→Ticketパイプライン（M1範囲のみ）。
  - プロパティテスト: サイジング単調性、R符号不変（FR-05/AC-09）。
  - バックテスト再現性: 同一`data_hash/config_hash/seed`でPF差±0.1%以内（AC-13）。
- **優先手動/半自動テスト（週次）**
  - CLIボード操作フロー: `tradectl board`→承認/却下/編集→監査ログ出力（AC-10）。
  - Resyncシナリオ: Catch-up後TTL判定と未失効チケットの復元（AC-04）。
  - Spreadクールダウン: ヒストリカル分位で閾値超→`SpreadCooldownState`遷移→解除（AC-34）。
- **M2+でのテスト追加予定**
  - SPRT連動の自動停止（AC-14, AC-29）。
  - Reduce-Only Advisorエンドツーエンド（AC-35）。
  - リアルタイムスプレッドポーリング（AC-34の拡張項目）。
テストケースは`tests/`配下で`test_<module>_m1.py`（M1範囲）と`test_<module>_m2.py`（拡張機能）に分離し、CIでは`pytest -m "not m2plus"`を既定タグとしてM1テストのみ実行する。

### 7.2 Pytestスケルトン指針
- **共通fixture**: `tests/conftest.py`に`data_dir`（`tmp_path`へfixturesコピー）、`event_factory`（典型的な`signal.generated`イベント生成）を定義。
- **戦略テスト**: `tests/strategies/test_ma_rsi_m1.py`でサンプルOHLCVを使った期待シグナル比較。`pytest.mark.m1`を付与。
- **CLIテスト**: `tests/interfaces/test_cli_board.py`で`CliRunner`＋`event_factory`を利用し、`tradectl board`出力をsnapshot比較（`pytest-approvaltests`等を利用可）。
- **パイプライン統合テスト**: `tests/integration/test_signal_pipeline_m1.py`でデータ取得→特徴量→シグナル→チケットの流れをモックデータで確認。`@pytest.mark.m1`。
- **M2+タグ運用**: 拡張機能テストには`@pytest.mark.m2plus`を付与し、CIでは`pytest -m "not m2plus"`、ローカル全実行は`pytest -m "m1 or m2plus"`を推奨。
- **CIセットアップ**: `pyproject.toml`に`[tool.pytest.ini_options] markers = ["m1", "m2plus"]`を追加し、`tox`や`nox`でM1専用セッションを定義する。

### 7.4 データ保全・ローテーション
- **バックアップ**: `data/`と`logs/events/`を日次インクリメンタル（rsync等）で取得し7世代保管。週次でフルバックアップを外部ドライブ/クラウドへ退避。
- **ローテーション**: `logs/events`は30日で圧縮（gz）し`archive/`へ移動。`reports/`は月次でアーカイブ、`snapshots/`は最新3世代を保持。
- **検証**: バックアップ後にSHA256チェックサムを比較し`logs/checksums/`に記録。復元テストは月1回、Runbookに従って実施。

## 8. 環境構成
### 8.1 時刻同期・UTC整合ポリシー（NFR-10）
- **プレフライト検査**: `tradectl preflight`が起動前に`systemsetup -getnetworktimeserver`/`sntp -sS $(config.time.ntp_server)`を実行し、NTP到達性と偏差を取得。`abs(clock_drift_ms)>500`またはNTPサーバ未設定時は`HealthState=degraded(reason=clock_out_of_sync)`を返し、Signal Boardを`board_mode=guarded`へ切り替える。
- **ランタイム監視**: `TimeSyncGuard`が10分間隔で`python -c "import time;print(time.time())"`と`ntpdate -q`（macOSでは`/usr/sbin/sntp -sS`のdry-run）を比較し、結果を`metrics/time_sync.jsonl`へ`{"ts_utc", "clock_drift_ms", "ntp_server", "mode"}`として追記。ドリフト>1500msで`health.changed(reason=clock_out_of_sync)`、>3000msでKill Switch手前アラートを送る。
- **UTC固定のデータ書き込み**: Data Ingestion/Manual CSV/バックテスト出力は全て`datetime64[ns, UTC]`で保存し、CSV入力では`utc_iso`列の存在とタイムゾーン付きISO8601をschema検証。`manual_csv/review`側もUTCで入力し、`ManualCsvReconciler`がJST等へのずれを検出した場合は`clock_mismatch`エラーで取込拒否する。
- **ローカルタイムとの相互運用**: CLI表示はユーザー設定の`config/profile.yaml:display_timezone`で変換し、監査ログとParquetはUTC保持。`TimeSyncGuard`解除手順はRunbook `docs/runbooks/RUN-TIME-01.md`で`sudo sntp -sS time.apple.com`→`tradectl preflight --recheck`→`degraded_recovered`イベント記録を定義する。

- **OS**: macOS (ARM/x86)
- **言語**: Python 3.11
- **主要ライブラリ案**: pandas, numpy, ta-lib/pandas-ta, scikit-learn(将来), numba, typer/rich, sqlalchemy, fastapi（将来GUI用API）。
- **フォルダ構成案**:
```
project_root/
  config/
  data/
    raw/
    cache/
  src/
    core/
    strategies/
    infrastructure/
    interfaces/
      cli/
        __init__.py
        board.py
        tickets.py
        events.py
        status.py
        export.py
  tests/
    conftest.py
    fixtures/
      events/
      market/
  logs/
  reports/
```

- **依存ライブラリ（M1）**: `pandas`, `numpy`, `pyarrow`, `pandas-ta`, `typer`, `rich`, `pydantic`, `pyyaml`, `orjson`, `python-json-logger`, `pytest`, `pytest-mock`, `pytest-approvaltests`（CLI snapshot）、必要に応じ`colorama`。

### 8.2 初期スプリントタスク分割（M1）
1. **プロジェクト基盤**: Poetry/requirements設定、`src/`・`tests/`パッケージ初期化、CIワークフローに`pytest -m "not m2plus"`ジョブ追加。
2. **データレイヤ**: ConfigRegistry＋JSON Schema検証、yfinance/Dukascopyアダプタ、`data/raw/`キャッシュ書き出し、Feature Cache基盤。
3. **戦略パイプライン**: MA+RSI戦略、Execution Model（ヒストリカル分位滑り/Marketable Limit）、Scoring Service（M1: 基本スコアリング / M2+: ハイブリッドスコア＋Stability）。
4. **リスク＆チケット**: Kill Switch, Spread gate（M1仕様）、Ticket BuilderのヒューマンチェックリストとOCO補正。
5. **CLI実装**: `tradectl board/status/events/ticket/export`、JSON Linesレンダラー、Audit Trail連携、snapshotテスト追加。
6. **永続化・運用補助**: Audit Trail Service、Snapshot Manager、`logs/ops`書き込みユーティリティ、Runbook向けドキュメント整備。
依存関係は1→2→3/4（並行可）→5→6を推奨。M2+で予定されているSPRT自動停止やReduce-Only Advisorは別エピックで管理する。

### 8.3 デプロイ／配布戦略
- **パッケージ管理**: Poetryで依存管理。`poetry build`でwheel配布、`poetry run tradectl`で実行。将来Docker対応時は`Dockerfile`でPoetryインストール＋`poetry export`を活用。
- **実行環境**: M1はローカルmacOSを前提とし、`python3.11 -m venv .venv`＋Poetryでセットアップ。`Makefile`に`make setup`, `make lint`, `make test`を定義。
- **設定配布**: `config/profile_*.yaml`はGitで管理し、秘密情報は`.env`/Keychainに保持。配布先環境では`poetry install --no-root`→`tradectl start --profile paper`等の手順をRunbookに明記。
- **レポート命名規約**: CI生成のレポートは`reports/report_<profile>_<YYYYMMDD>.md`、エクスポート結果は`reports/export/<date>/<resource>_<timestamp>.csv`とする。

## 9. 運用・保守
- 起動フロー: 1) config選択 -> 2) `tradectl start --profile live` -> 3) CLIでHeartbeat/Catch-up完了を確認。
- Resync手順: `tradectl resync --since <ts>`で欠落区間を指定可能。完了後に`reports/latest.md`と`logs/events`で再評価結果を確認し、Runbook `docs/runbooks/RUN-DATA-05.md`/`docs/runbooks/RUN-DATA-06.md`（AC-04/AC-45）でTTL・ドリフト・減衰の検証と監査ログ更新を行う。
- アカウント反映: LiveモードではブローカーCSVを`data/account/`へ配置→`tradectl account sync`で残高/証拠金/ポジションを取り込み、Paper/Backtestでは自動更新を確認。
- カレンダー更新: `config/calendar/*.csv`を編集後、`tradectl calendar reload`で再読み込み。外部API同期タスクが成功時はCLIに告知し、運用者が承認後に適用。承認ログを`logs/ops/calendar.log`へ記録。
- 換算レート確認: リアルタイム換算が取得できない場合はCLIが警告し、運用者は`tradectl rates sync`で再取得を試行。最終手段として`data/account/fx_rates.parquet`を手動更新し、実施履歴を`logs/ops/rates.log`に記録。
- スプレッド監視: 異常値アラート後は`tradectl spread inspect`で最新`spread_metrics.parquet`を確認し、必要なら`tradectl spread sync`で再計測。SpreadCooldownStateの解除状況は`tradectl spread cooldown`で確認でき、承認ログを`logs/ops/spread.log`へ記録。
- 相関評価: 週次で`tradectl correlation report`を実行し、通貨バケット閾値の見直しや過剰相関アラートの対応を行う。
- ブローカー仕様: 仕様変更時は`config/broker_rules.yaml`を更新後、`tradectl broker reload`で反映。差分はCLIで確認し、承認後に`BrokerSpecs`へ適用。
- Reduce-Only対応: Reduce-Only発動時は`tradectl reduce-only status`で対象ポジションと理由を確認し、縮小後の再開可否を`tradectl reduce-only release`で操作。操作結果は監査ログに記録。
- 流動性監視: `tradectl liquidity inspect`で乖離ZスコアとHOLD状態を確認。解除時はRunbookのステップIDと再開コメントを`logs/ops/liquidity.log`へ記録（FR-49, AC-38）。
- コンプライアンスチェック: 新規プロファイル投入時は`tradectl compliance dry-run --profile <name>`で100件サンプル検証を行い、違反0を確認してからLive適用（FR-50, AC-39）。
- キャピタルガード: 週次で`tradectl capital status`を確認し、RateLimiter発動中はポジション削減または資金移動方針をRunbookに追記（FR-51, AC-40）。
- データ署名検証: 月次で`tradectl data verify --manifest reports/data_manifest.json --signature reports/data_manifest.sig`を実行し、結果を`logs/ops/data_provenance.log`へ記録（FR-52, AC-41）。

### 9.1 運用スループット試算と自動化ロードマップ
| 作業カテゴリ | 想定頻度 (M1 Core) | 基準タスク | 手作業時間目安 | 自動化/省力化候補 |
| --- | --- | --- | --- | --- |
| データ品質監査 | 平日毎日 | `manual_csv`二重入力レビュー、`health.changed`承認、`reports/validation_log`更新 | 35〜45分/日 | `tradectl data manual-report --template`でCSVチェックリスト自動生成、Slack/メール通知のドラフト化 |
| SLAレビュー | 週1回 | `metrics/data_ingestion_sla.jsonl`集計、逸脱コメント記入 | 60分/週 | `tools/sla/generate_profile.py`によるMarkdown自動生成、`tradectl sla report --window 7d`で差分強調 |
| Kill Switch監視 | 平日毎日 | `Risk Dashboard`確認、`reports/risk/daily_guard.md`更新、承認サイン | 20分/日 | CLI `tradectl risk digest --daily`で自動ドラフト、`board_mode=guarded`時の自動TODO発行 |
| 週次レポート | 週1回 | `Reporter`実行、コメント追記、PO共有 | 90分/週 | `reports/weekly/templates/m1_core.md`への自動差分ハイライト、コメント定型文`snippets/`化 |
| Runbook更新 | 月2回 | インシデント記録、手順差分反映 | 45分/更新 | `docs/runbooks/update_index.py`で差分検出、PRテンプレ連携 |

- **キャパシティ算出**: 上表の作業量を30日ローリングで集計し、運用者が1日あたり約2.2h、週あたり約10.5hを確保できるかチェックする。`reports/ops/workload_<YYYYMM>.md`に実績値を記録し、許容超過時は自動化対象を優先度付けする。
- **アクションアイテム化**: 省力化候補ごとにIssueテンプレ`docs/templates/automation_request.md`を用いて起票し、対象バージョン（M1 Core/M1.1/M2）と期待削減時間を明記する。削減効果>30分/週が見込まれるものから着手し、実績は`reports/ops/automation_effect.md`に追記する。
- **日次TODO生成**: `tradectl ops agenda --date <YYYY-MM-DD>`コマンドを追加し、上表の基準タスクとSLA逸脱/Kill Switch状態をもとに日次TODOをMarkdown出力。CLIは`--export docs/runbooks/daily_agenda/<date>.md`オプションでRunbookにリンクし、手動作業漏れを防止する。

### 9.2 Kill Switchとレポート整合性の強化
- **レポート出力**: 週次レポート（M1 Coreテンプレート）に`daily_loss_threshold`/`weekly_loss_threshold`と実績損失、Kill Switch遷移履歴（`soft_stop/hard_stop`）を自動埋め込み、逸脱時は`[ALERT]`タグを付与する。`Reporter`の`render_weekly_report()`へ`risk_summary`セクションを追加し、`reports/performance/<mode>/<YYYYMMDD>.md`にも同様の表を出力する。
- **Dashboard整合**: `tradectl risk status`に`report_last_synced_at`と`kpi_snapshot_version`を表示し、報告済みしきい値とリアルタイム指標の乖離を運用者が即確認できるようにする。Kill Switch解除時は`risk_summary`を再生成してRunbook `docs/runbooks/RUN-RISK-01.md`へ貼り付ける。
- **承認ワークフロー**: Kill Switch閾値の変更は`config/risk_policy.yaml`修正と同時に`reports/risk/threshold_change_<YYYYMMDD>.md`へ承認サインを残し、週次レポートに変更履歴を引用する。閾値変更後最初の週次レポートには`[THRESHOLD CHANGE]`バナーを表示し、POレビューで差分確認を義務化する。
- **テレメトリ同期**: `metrics/risk_guard.jsonl`に`threshold_version`と`report_reference`を記録し、差分がある状態（例: `threshold_version != report_reference`）が48時間以上継続した場合は`health.changed(reason=risk_report_mismatch)`を発火。Acceptable Degradation中も報告指標が同期されるようにする。

- 障害対応: 重大アラートはメール。Kill Switch発動時は手動で再開判定。Spreadクールダウン中は解除条件（連続Nバー正常化）をCLIで確認可能。Funding Serviceの取得失敗時は`tradectl funding status`で直近値を確認し、手動CSV更新後に`tradectl funding reload`で再取得。
- バージョン管理: Git + Poetry/Pip + `pip --require-hashes` で依存固定。
- テスト: pytest + hypothesis。バックテスト再現性はAC-13遵守。
- ログローテーション: 日次でJSONL圧縮。スナップショットは時間足ごとに保存。
- チューニング・ガバナンス: `tradectl autotune propose`で週次チューニング案を生成し、変更幅±10%・冷却期間2週間（FR-33）を`ConfigRegistry`で検証。承認後に`cfg_change`イベントを発火。

## 10. 要件トレーサビリティ（主要FR対応）
| 要件ID | 対応セクション/コンポーネント |
| --- | --- |
| FR-01, FR-02 | 2.1 Data Ingestion Service / Data Quality Guard, 4.1 Catch-upフロー |
| FR-03 | 2.1 Feature Engine, 4.2 マルチタイムフレーム合成 |
| FR-04 | 6, 6.1 Signal Engine/StrategyPlugin |
| FR-05 | 2.2 Health Monitor, 6.1 Risk Manager |
| FR-06 | 6.1 Position Sizer |
| FR-07, FR-30 | 3. ユースケースフロー(18〜19), 6.1 Ticket Builder |
| FR-08 | 1. システム概要、2.1 Mode Controller |
| FR-09 | 2.1 Optimizer、6. モジュール別機能割り当て |
| FR-10 | 2.1 Reporter、9. 運用・保守 |
| FR-11 | 2.2 Audit Trail Service、4. データ構造 |
| FR-12 | 2.2 Health Monitor、Alert Dispatcher |
| FR-13, FR-34 | 2.1 Calendar Service、4. データ構造、4.6 相関評価 |
| FR-14, FR-23 | 2.2 Configuration Governance、4. データ構造、9. 運用・保守 |
| FR-15 | 2.1 Calendar Service、6. correlation_guard |
| FR-16, FR-18 | 2.2 Snapshot Manager、4.1 Catch-upフロー |
| FR-17, FR-38 | 3. ユースケースフロー(18〜19), 6.1 Ticket Builder |
| FR-19, FR-21 | 6.1 Scoring Service（M2+設計フック）、4.3 口座通貨換算ポリシー |
| FR-20 | 2.1 Regime Detector、6. モジュール別機能割り当て |
| FR-22 | 2.2 Health Monitor、4.5 スプレッド観測スケジュール |
| FR-24 | 2.1 Broker Rules Loader、6.1 Position Sizer |
| FR-25 | 7. 非機能要件、4. データ構造 |
| FR-26 | 2.1 Calendar Service、4. データ構造、3. ユースケースフロー(8) |
| FR-27 | 2.1 Spread Monitor、4.5 スプレッド観測スケジュール、6 execution |
| FR-28 | 2.1 Funding Service、3. ユースケースフロー(6-7,13-14)、4.7 スワップ/ファンディング管理、6. モジュール別機能割り当て |
| FR-29 | 3. ユースケースフロー(11,18)、6 execution |
| FR-31 | 4.3 口座通貨換算ポリシー |
| FR-32 | 2.1 Data Quality Guard、4.1 Catch-upフロー |
| FR-33 | 2.2 Configuration Governance、9. 運用・保守 |
| FR-35 | 6. モジュール別機能割り当て（backtester/ticket）、Execution Model |
| FR-36 | 2.1 Risk Manager、6.1 Risk Manager |
| FR-37 | 2.1 Correlation Guard、6.1 Correlation Guard、4.6 Reduce-Only判定 |
| FR-38 | 3. ユースケースフロー(18)、6.1 Ticket Builder |
| FR-39 | 3. ユースケースフロー(11,18)、4.5 スプレッド観測、6 execution |
| FR-40 | 2.1 Calendar Service、4. データ構造（カレンダー）、9. 運用・保守 |
| FR-41 | 3. ユースケースフロー(13)、4.5 スプレッド観測、6 spread |
| FR-42 | 2.1 Reduce-Only Advisor（M2+）、3. ユースケースフロー〈M2+〉(2)、6 reduce_only |
| FR-49 | 2.1 Liquidity Intelligence Service、2.2 Liquidity Guard Pipeline、3. ユースケースフロー〈M2+〉(1)、6 liquidity |
| FR-50 | 2.1 Compliance Validator、2.2 Compliance & Capital Policy Layer、6 compliance |
| FR-51 | 2.1 Capital Allocation Guard、2.2 Compliance & Capital Policy Layer、6 capital_guard |
| FR-52 | 2.1 Data Provenance Service、2.2 Data Provenance Mesh、4 データ構造（データマニフェスト/署名）、6 data_provenance |
| FR-55 | 2.1 Research Workspace Bridge、3.1 ストラテジーライフサイクル(1〜3)、4 データ構造（research/strategies）、6 research |
| FR-56 | 2.1 Strategy Manifest Manager、3.1 ストラテジーライフサイクル(3〜4)、2.2 Strategy Lifecycle Governance、6 strategy_manifest |
| FR-57 | 2.1 Reporter、3.1 ストラテジーライフサイクル(5)、10. KPI/運用ガバナンス、6 reporter |
| FR-58 | 2.1 Account Aggregator（M2+）、3. ユースケースフロー〈M2+〉(2)、6 account_aggregator、12.1 FR-58設計タスク |

## 11. リスクと未解決課題
- **執行モデルの検証データ**: ブローカーAPI未接続のため、初期は過去手動記録やDukascopyティックから推定する。ライブ移行前に限定サイズでPaper/Livetrade比較検証が必要。
- **Reduce-Only運用負荷**: 連続イベント発火時の運用負荷を抑えるため、優先度キューとCLIバッチ操作のUX検証が必要。
- **SPRTしきい値チューニング**: ヒストリカル性能が乏しい戦略追加時は誤検出リスクがあるため、戦略ごとのベイジアン更新案を検討。

## 12. 今後の拡張ポイント
- ブローカーAPI連携（自動発注化）
- GUI (React + Tauri) の提供
- ボラティリティターゲティング等の高度なサイジング
- 強化学習/機械学習モデルの導入（リスク管理に合わせた段階的適用）

### 12.1 M2設計タスク: FR-58 複数口座統合
- **実装対象**: Account Aggregatorモジュール、`accounts/<broker>/<account_id>.yaml`スキーマ、統合`AccountState`のイベント/監査出力、およびRisk/Correlation/Capital Guardとの連携拡張。
- **受け入れ基準（M2）**:
  - `reports/performance/portfolio/<date>.parquet`で算出した統合残高・証拠金・R_effが、各口座ログ（Paper: `reports/performance/paper/<run_id>.parquet`、Live: ブローカーCSV/API）の合計と±0.05R以内で一致する。
  - `accounts/<broker>/<account_id>.yaml`の`weight`, `currency`, `margin_mode`定義に従い、通貨換算後の有効レバレッジと証拠金維持率が`capital_guard`/`risk`モジュールで同一値となることを自動検証（`make verify-fr58`想定）。
  - 3口座構成（例: USDJPY Paper、EURUSD Live、GBPUSD Paper）のエクスポージャ差分が`reports/performance/portfolio/verification_<date>.md`に記録され、Correlation Guardのバケット警告が統合R_effのしきい値（要件定義FR-58）に基づき発火する。
- **検証データ/証跡**:
  - `reports/performance/portfolio/<date>.parquet`および`verification_<date>.md`をValidation Data Playbookへリンクし、`reports/validation_log/FR-58_<date>.md`にサインオフ（M2）を記録する。
  - `logs/audit/account_aggregator/<date>.jsonl`に統合計算の入力ハッシュ・結果・警告を残し、`tradectl account aggregate --dry-run`実行ログを添付する。
- **運用タスクリード**: M1では単一口座のみを対象とし、複数口座対応のRunbook（`docs/runbooks/RUN-ACCOUNT-02.md`想定）はM2スプリントで策定する。M1のリリースチェックリストやAC-03/AC-11等にはFR-58関連項目を含めない。

## 13. リリース判定チェックリスト（M1）

| 項目 | 判断基準 | 参照セクション | 対応AC |
| --- | --- | --- | --- |
| データパイプライン健全性 | `data_manifest`に全資産のハッシュが記録され、`data verify`で改ざん検知が0件 | §2.1 Data Provenance Service, §7.3 | AC-01, AC-22, AC-42, AC-45 |
| KPI指標整合性 | Reporter出力と`reports/kpi_snapshots.json`の乖離≤0.1% | §2.1 Reporter, §7.1 | AC-01, AC-05, AC-08 |
| リスク/Kill Switch | 1%リスク設定で`Risk Manager`が日次-3%/週次-6%到達時に`soft_stop`遷移し再開は手動承認のみ | §6.1 Risk Manager, §9 | AC-03, AC-21 |
| HITL操作 | 100件操作ログから重大入力ミス0、監査イベント`ticket.approved/rejected`と一致 | §3 ユースケース, §6 Ticket Builder | AC-02, AC-10, AC-20 |
| スナップショット復旧 | `snapshots/latest/`復元後に未処理チケットと`HealthState`が一致し、再稼働後に提案が再開 | §2.2 Snapshot Manager, §7.4 | AC-04, AC-18 |
| アラート/通知 | Spreadクールダウン・データ遅延・Kill Switchでメール通知が確認できる | §2.2 Health Monitor, Alert Dispatcher | AC-34, AC-45 |
| Runbook整備 | KPIレビュー/Kill Switch/Resync/データ署名/緊急プロトコルの手順がRunbookで更新済み | §9 運用・保守 | AC-43, AC-45 |

> **判定手順**: 各項目の結果を`reports/governance/release_checklist_<YYYYMMDD>.md`に記録し、プロダクトオーナーが署名後にM1リリース完了とする。未達項目は`status=pending`で残し、改善計画（担当/期限/対応策）をRunbookの同章へ連携する。

## 14. ナレッジ・ドキュメント統制

- **Runbook構造**: `docs/runbook.md`を親とし、`docs/runbook/ops/*.md`に運用手順、`docs/runbook/incidents/*.md`に障害対応、`docs/runbook/governance/*.md`にレビュー記録を格納する。Git運用でレビュー体制（週次/四半期）が記録されるようPull Requestテンプレートに「Runbook更新有無」を追加。詳細設計キックオフまでに`RUN-DATA-05`/`RUN-DATA-06`/`RUN-RISK-01`/`GOV-AUD-01`のテンプレート骨子（目的・トリガー・チェックリスト・ダブルサイン欄・証跡リンク欄）を作成・コミットし、レビュー結果を`reports/governance/runbook_templates/<YYYYMMDD>.md`に保存する。
- **調査ログ**: 重大な戦略調整やリスク逸脱が発生した場合、`reports/audit/kpi/<ticket>.md`に背景/原因/対策/承認者を記録。データ品質インシデントは`reports/audit/data/<ticket>.md`に集約し、トレーサビリティマトリクスとリンクする。
- **Decision Journal**: キャピタル配分・戦略昇格・Kill Switch解除など重要決定は`reports/governance/decisions/<YYYYMMDD>_<topic>.md`に記録。Decision Journalには関連する`strategy_manifest`やKPIスナップショットへのリンク、承認者、評価結果のフォローアップ予定日を含める。
- **自動生成ドキュメント**: `make docs`でMkDocsをビルドし、`site/`にAPI/CLI/Runbook抜粋を出力。CIで差分ビルドし、未更新ドキュメントがある場合は警告を出す（NFR-13, NFR-16）。
- **ナレッジ移管手順**: 新メンバーオンボーディング時は`docs/onboarding.md`を参照し、システム概要・主要CLI・Runbook参照先・依存ロックの扱いをカバー。1週間以内にバックテスト再現性（AC-01）とResync手順（AC-04）のハンズオンを実施する。
- Validation Data Playbookはテンプレートを共有し、各AC/FRに対応した必須フィールドを事前定義して証跡品質を均一化する。

### 14.1 Validation Data Playbookテンプレート雛形
```
---
id: AC-XX-<YYYYMMDD>
requirement: <FR/AC番号>
dataset: <データセット名 or ファイルパス>
hash: <SHA256>
source: <取得元URL/Runbook手順>
owner: <記録者>
reviewer: <サイン者>
due_date: <YYYY-MM-DD>
status: pending | provisional | confirmed
fallback_applied: true | false
fallback_reason: <欠損補完理由>
linked_runbook: docs/runbooks/RUN-XXXX-YY.md
---

## 1. 受け入れ条件
- [ ] データ期間: <例: 2024-01-01〜2024-01-31>
- [ ] 欠損率 ≤ <閾値>
- [ ] 二重入力ハッシュ一致

## 2. 検証ログ
| チェック | 実施者 | 実施日時 | 結果 | 証跡 |
| --- | --- | --- | --- | --- |
| レコード件数検証 |  |  |  |  |
| スキーマ検証 (`tools/validate_schema.py`) |  |  |  |  |
| ハッシュ再計算 (`tradectl data hash`) |  |  |  |  |

## 3. コメント
-

## 4. サインオフ
- 運用者: <署名/日時>
- PO: <署名/日時>

```
- 上記テンプレートを`reports/validation_log/templates/playbook_entry.md`に配置し、`tradectl validation new --requirement AC-45 --dataset usdjpy_m5_core`でプレイブックエントリを生成するCLIを追加する。
- `status`が`pending`/`provisional`のまま`due_date`を超過した場合、`tradectl validation audit --window 7d`で一覧に赤字表示し、週次レビューで是正アクションを起票する。

