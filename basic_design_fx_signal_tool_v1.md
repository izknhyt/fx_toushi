# FXヒューマン・インザループ投資ツール 基本設計書 v1.2

## 0. 文書情報
- 作成日: 2025-02-20
- 作成者: Codex AI 支援
- 参照文書: `要件定義（テンプレ形式）v_1.md`
- 想定リリース: マイルストーンM1（MVP）

### 0.1 改訂履歴
| 版 | 日付 | 改訂概要 |
| --- | --- | --- |
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

### 1.1 マイルストーン適用範囲
- **M1 (MVP)**: データ取得/品質管理、基礎インジケータ、MA+RSI中心の戦略、リスク/Kill Switch、HITLチケット、Resync & Snapshot、設定ガバナンス（Schema検証/ホットリロード）、ヒストリカル分位に基づくコスト・スリッページモデル、`fx_rates.parquet`によるP&L通貨正規化、Stop/Freeze距離検証、`emergency.yaml`ベースの即時停止ハンドラ、運用健全性サマリ表示（CLI）。
- **M2 (強化フェーズ)**: ハイブリッド最適化、レジーム検出、Stabilityペナルティ、SPRTによるライブ健全性自動制御、経済カレンダー動的拡張、リアルタイムスプレッド/API連携、Reduce-Onlyアドバイザ本運用、スプレッドクールダウン/イベント窓拡張の自動可変化、ストレステスト/ジャーナル/ドリフト検知の自動化。
- **M3 (拡張フェーズ)**: マージン/レバレッジ自動制御の高度化、相関合算Rによるポートフォリオ制御、GUI/Tauri化、ブローカーAPIによる自動発注への拡張、ベンチマークリプレイ+差分可視化、運用健全性ダッシュボードの高度化。

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
| コンポーネント | 役割 | 技術/形式 |
| --- | --- | --- |
| CLI/Signal Board | 提案表示・操作入力 | Rich CLI（M1: `tradectl board`コマンド、JSON Lines入力）／将来React GUI |
| Session Manager | アプリ全体の起動・終了、Catch-up調整 | Python service |
| Mode Controller | Backtest/Paper/Liveの振る舞い切替 | Stateパターン |
| Data Ingestion Service | データ取得・キャッシュ管理 | yfinance, Dukascopy, CSV |
| Data Quality Guard | 欠損/外れ値判定、再取得制御 | Pandas/Numpy |
| Feature Engine | インジケータ計算・マルチTF合成 | pandas-ta/custom |
| Regime Detector | レジーム分類（ADX等） | 独自ロジック |
| Account Service | 残高/証拠金/ポジション集計・相関用エクスポージャ算出 | Backtest台帳, Paperログ, Live CSV |
| Funding Service | スワップ/ファンディングレートの取得と適用 | broker_rules.yaml, swap_rates.csv (手入力/公開CSV, M1) |
| FX Rate Updater | 口座通貨換算レート取得/保存 | yfinance, 手入力CSV, (M2+: ブローカーフィード) |
| Calendar Service | 経済指標/休日スケジュール配信（出力: GateState） | ローカルCSV, 外部API同期 |
| Broker Rules Loader | ブローカー仕様読み込み（pip値/contract等） | YAML loader (`broker_rules.yaml`) |
| Spread Monitor | スプレッド/コスト観測・クールダウン制御 | `spread_metrics.parquet`(Dukascopy/公開CSV, M1) / Broker API(M2+) |
| Execution Model | スリッページ/ロールオーバー/Fill判定モデル | MarketData, SpreadMetrics, broker_rules.yaml |
| Liquidity Intelligence Service | 複数レートソースの乖離検知・板厚監視・HOLD判定 | yfinance, Dukascopy, broker API/CSV, `liquidity_monitor.parquet` |
| Correlation Guard | 通貨/シンボル相関制御 | Rule-based filter |
| Signal Engine | ルール/モデルプラグインIF | Strategyプラグイン |
| Risk Manager | リスク制約・Kill Switch・スプレッド制御 | Policy engine |
| Position Sizer | Fixed Fractionalロジック | Python class |
| Compliance Validator | チケット承認前のレバレッジ/建玉/規制確認と代替案提示 | `broker_rules.yaml`, `risk_policy.yaml`, 監査ログ |
| Capital Allocation Guard | VaR/ESモニタリングと提案スロットリング | Portfolio PnL, `risk_policy.yaml`, Exposure metrics |
| Reduce-Only Advisor | 収縮提案生成（閾値到達時、M2+） | Python service |
| Emergency Orchestrator | `emergency.yaml`に基づく緊急アクション実行（Kill Switch連携、Reduce-Only指示） | Policy/Playbook Runner |
| Ticket Builder | 注文チケット生成・ヒューマンエラーチェック | JSON Lines |
| Persistence & Audit | イベント/ログ/設定履歴 | SQLite/Parquet/JSON |
| Optimizer | グリッド/ランダム/WFA | SciPy/自作 |
| Reporter | 週次/エクイティ/メトリクス出力 | Markdown/HTML |
| Trade Journal Service | トレード/コメント管理、振り返りダッシュボード | SQLite/Markdown |
| Benchmark Analyzer | 外部ベンチマークデータとの比較、ギャップ算出 | Pandas/Plotly |
| Data Provenance Service | `data_manifest.json`生成・署名・検証、アーカイブ連携 | `manifest.sig`, ハッシュ計算, WORMストレージ |

#### Reporter/Benchmark MonitorのKPI評価ガイド
- **キャッシュ保持期間**: Sharpe/Sortino/最大DD/年率は要件定義の評価期間に合わせ、最低でも**直近252営業日＋安全マージン10営業日**の取引履歴とエクイティカーブをキャッシュする。四半期レビュー用に**直近90営業日ローリング**のサマリも常備し、`metrics/kpi_cache.parquet`に`window={252d,90d}`単位で保管する。
- **前処理ルール**: ReporterとBenchmark Monitorは共通のData Qualityフィルタを適用し、**欠損バー率≤0.5%/日・連続欠損≤3バー・異常イベント（`flash_crash`, `manual_exclusion`タグ）除外**後のデータセットのみをメトリクス計算に渡す。閾値を超えた場合は当該期間をドロップし、`data_quality_report.md`を添付した上で`HealthState`へ`data_gapped`理由を通知する。
- **再計算トリガー**: 週次レポート生成（`Reporter.run(schedule=weekly)`）と四半期レビュー（`calendar.quarter_review`イベントまたは`tradectl benchmark compare --quarterly`）の2系統で再計算を走らせる。どちらも**最新バー更新時（5分足確定）→キャッシュ更新→メトリクス再集計**の順に非同期ジョブを投入し、完了後に`kpi_snapshot.json`を上書きする。
- **統計検証**: Reporterは**BCaブートストラップ（1,000回）**で`PF_recent`/Sharpe/Sortino/年率の信頼区間を算出し、Benchmark Monitorはベンチマーク差分に対して**差分年率とSharpeギャップの95%信頼区間**を算出する。信頼区間下限が要件を割り込む場合は`benchmark_gap`イベントに`confidence_breach=true`を付加し、受け入れ基準AC-07〜AC-09の検証ログに残す。
- **リトライ戦略**: KPI再計算ジョブが失敗した場合は`RetryPolicy`を継承した`KpiRecalcRetry`を使用し、**max_attempts=3, initial_delay=30s, backoff=2.0**で再実行。3回失敗時は`Reporter`が`Critical`ログを出力し、`HealthState`を`soft_stop`へ遷移させる。Benchmark Monitor側では最新成功スナップショットを保持し、復旧後に差分を自動再算出する。
- **サンプルサイズ監視**: 90営業日ウィンドウで**取引数<60**、252営業日ウィンドウで**取引数<180**の場合はメトリクス算出結果を`insufficient_sample`フラグ付きで返し、受け入れ基準の判定を`pending`に設定する。ReporterはRunbookに自動追記して人間レビューを促す。
| StressTest Engine | 指定シナリオの再生と感度分析、結果レポート生成 | Backtest Runner拡張 |
| Parameter Drift Monitor | 最適化パラメータと最新指標のドリフト監視 | Numpy/Scipy |
| Observability Exporter | メトリクス収集とPrometheus互換エンドポイント | `prometheus_client` |
| Alert Dispatcher | メール通知 | SMTPライブラリ |

### 2.2 クロスカッティング・コンポーネント
- **Configuration Governance**: `ConfigRegistry`（シングルトン）でYAMLプロファイルを管理し、JSON Schema検証（FR-23）とバージョンハッシュを計算。安全項目はPub/Subでホットリロードし、危険項目は`NextBarChangeQueue`で遅延適用する。
- **Event Bus**: Domain層間の疎結合を保つために`DomainEventBus`を採用。同期処理はコアフロー、非同期処理（レポート生成、Slack通知など）はワーカーキューに委譲する。`MarketableLimitApplied`や`ReduceOnlyIssued`など執行関連イベントも同バスで配信する。イベントはJSON (`event_type`, `ts`, `payload`) 形式で`logs/events/DATE.jsonl`へ記録し、CLIの`tradectl events tail --type=signal`等で監視。主なイベントpayloadは以下の通り:
- **Event Bus**: Domain層間の疎結合を保つために`DomainEventBus`を採用。同期処理はコアフロー、非同期処理（レポート生成、Slack通知など）はワーカーキューに委譲する。`MarketableLimitApplied`や`ReduceOnlyIssued`など執行関連イベントも同バスで配信する。イベントはJSON (`event_type`, `ts`, `payload`) 形式で`logs/events/DATE.jsonl`へ記録し、CLIの`tradectl events tail --type=signal`等で監視。主なイベントpayload仕様は以下の通り:
- **Liquidity Guard Pipeline**: Liquidity Intelligence Serviceが`quote_snapshot`イベントを5分足ごとに発行。`spread`, `quote_age`, `book_depth`のZスコアを算出し、閾値超過時は`liquidity.alert`イベントを発火。Risk ManagerとCompliance Validatorが同イベントをサブスクライブし、`HOLD`/サイズ縮小を同期的に適用する。
- **Compliance & Capital Policy Layer**: Compliance ValidatorとCapital Allocation Guardは`ticket.intent`イベントをフックし、`broker_rules.yaml`と`risk_policy.yaml`を参照して承認前検証を行う。結果は`ticket.intent_validated`イベントとしてTicket Builderへ返却し、監査ログに残す。
- **Data Provenance Mesh**: Data Provenance ServiceはData Ingestion/Persistence/Auditから`data.asset_written`イベントを受け取り、`data_manifest.json`と`manifest.sig`を更新する。アーカイブ時は`archive.created`イベントを発火し、外部WORM媒体へのコピー状況を`ops archive status`で可視化する。
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
- **Health Monitor**: SPRT評価（FR-22）、Kill Switch（FR-05）、連続エラー検出（FR-12）を統合して`HealthState`を更新し、Signal Engine/Mode Controllerへブロードキャスト。`HealthState`は`{"status":"ok|soft_stop|hard_stop","reasons":[...]}`形式で保持し、CLIの`tradectl health show`で確認。状態遷移と運用アクションは以下。

| 現状態 | トリガー | 次状態 | オペレータ対応 |
| --- | --- | --- | --- |
| ok | Kill Switch閾値到達（daily_loss/weekly_loss） | soft_stop | 新規提案停止。`tradectl status`で原因確認、`tradectl health resume`で解除するまでReduce-Onlyのみ（M2+）。
| ok | Spread guard発火（連続閾値超） | soft_stop | `tradectl spread cooldown`で解除条件を監視。強制解除は不可。 
| ok | DataDegraded（欠損>閾値） | soft_stop | `tradectl resync`で復旧し、正常バー3本確認後に自動復帰。
| soft_stop | オペレータ確認後、復帰コマンド | ok | `tradectl health resume`で復帰。Kill Switchの手動解除はRunbookに従う。
| 任意 | `tradectl stop`/manual emergency、クリティカル例外 | hard_stop | プロセス停止。再起動前に原因調査、`tradectl start`で立ち上げ直し。
| hard_stop | 再起動完了 | ok | スナップショットから復旧、`tradectl status`で整合性確認。
- **Audit Trail Service**: 監査イベント（FR-11）を受け取ってJSONL/SQLiteへ二重書き込みし、書き込み失敗時はWrite-Aheadログでロールフォワード可能にする（ERROR-C04対策）。`HumanCheckFailed`等のヒューマンエラー検知もここで証跡化する。CLIからは`tradectl audit export --date 2025-02-20`で抽出。
- **Logging Strategy**: `logging.config.dictConfig`を用い、モジュール別ロガーを定義（例: `core.signal`, `infrastructure.ingestion`, `interfaces.cli`）。デフォルトレベルINFO、`metrics`/`debug`チャンネルは`logs/app.log`へ、監査・イベントはJSONLへ出力。例外は`logger.exception`でトレースを記録し、再試行が必要なケースはRetryPolicyへ委譲。
- **RetryPolicy**: インフラ層でユニット化し、yfinance/Dukascopy取得は`max_attempts=3`, `backoff=1.5`倍増。取得失敗は`DataDegraded`イベントで通知し、閾値超えでKill Switchへ連携。CLIコマンドは即時エラーとし、非ゼロ終了コードでユーザーへ通知。
- **Emergency Orchestrator**: `emergency.yaml`を`pydantic`でロードし、シナリオ→アクション（Kill Switch遷移、Reduce-Only提案、通知、再接続リトライ）を状態マシンとして実行（FR-47, AC-38）。`tradectl emergency dry-run`で手順検証、`tradectl emergency trigger <scenario>`で手動発火（保護付き）。
- **Trade Journal Service**: チケット承認イベントと実績（Backtest/Paper/Live）を`journal_entries.db`へ保存し、週次レポート生成時にMarkdownテンプレートへレンダリング（FR-44）。CLIは`tradectl journal add-note --ticket <id>`でコメント追記、`tradectl journal review`で直近レビューを表示。
- **StressTest Orchestrator**: `scenarios/*.yaml`のイベントセットと感度パラメータ（spread_multiplier, slip_bias, decision_delay）をBacktest Runnerへ注入し、結果を`reports/stress/<scenario>/index.md`へまとめる（FR-43, AC-36）。
- **Benchmark Monitor**: `benchmark_feeds/*.csv`を取り込み、自戦略のエクイティ・KPIと差分チャートを生成。`tradectl benchmark compare --from 2023-01-01`で比較実行し、差分が閾値超過の場合はHealth Monitorへ`benchmark_gap`理由を追加（FR-46, FR-48）。
- **Observability Exporter**: `prometheus_client`で`/metrics`（ローカルHTTPサーバ、デフォルト`127.0.0.1:9108`）を公開し、`signal_latency_ms`, `spread_guard_state`, `benchmark_gap_pct`などのGauge/Histogramを登録（NFR-06, NFR-15）。CLIから`tradectl metrics push`で手動スナップショット出力も可能。

## 3. ユースケースフロー（MVP）
※ 本節ではM2以降に有効となる機能を〈M2+〉と明記しています。
1. アプリ起動 -> Session Managerが設定読み込み・Catch-upキュー投入->履歴データ同期。
2. Data Ingestionが所定ティッカーの新規バーを取得し、キャッシュを更新。
3. Broker Rules Loaderが`broker_rules.yaml`をロードし、pip値/contract size/最小ロット/tick制約を`BrokerSpecs`として共有キャッシュに展開。
4. FX Rate Updaterが口座通貨換算レート（5m最新値＋日次終値）を取得し、差分があれば`fx_rates.parquet`を更新（排他ロック付与）。
5. Spread Monitorが`spread_metrics.parquet`（M1: Dukascopyティック/公開CSV/手入力CSVから事前集計、M2+: ブローカーフィード連携）をロード・更新し、`SpreadMetrics`としてキャッシュ。CLIからは`tradectl spread ingest`でヒストリカル分位を生成し、`tradectl spread watch`でリアルタイムポーリングを開始する（M2+）。
6. Liquidity Intelligence Serviceが`quote_snapshot`を生成し、二重取得レートの乖離・板厚を集計。`liquidity_monitor.parquet`へ書き込み、閾値超過時は`liquidity.alert`をRisk Managerへ送出（FR-49, AC-38）。CLIの`tradectl liquidity inspect`で可視化し、解除条件メモをRunbookに追記。

7. Funding Serviceが`broker_rules.yaml`で定義されたスワップ計算ルールを読み込み、`swap_rates.csv`（M1: 手入力/公開CSV、M2+: ブローカーフィード統合）から当日分のロング/ショートスワップ（Wednesday\_NYの3倍など）を取得し、`FundingCurve`を生成。CLIは`tradectl funding sync`でCSV読み込み、`tradectl funding status`で最新値を照会。
8. Account Serviceがモード別データソース（Backtest: シミュレーション台帳 / Paper: 仮想約定ログ / Live: ユーザー入力またはブローカーCSV）と最新レートを用いてアカウント状態を集計し、通貨バケット別エクスポージャと相関エクスポージャを算出して`AccountState`を更新。スワップは`FundingCurve`を日次で織り込んだキャッシュフローとして反映し、バックテストでも同一ロジックを適用する（FR-28）。
9. Calendar Serviceが経済指標CSV/休日CSVをUTC基準でロードし、設定された`trading_timezone`（既定:JST）に変換した上で現在時刻に対するブロック/解除ウィンドウを判定して`GateState`を更新。イベント強度に応じた±15/30分の動的拡張ルールもここで適用する。
10. Feature Engineが差分計算で新規バー分の指標を更新し、必要な区間のみ再計算。
11. Regime Detectorが最新特徴量からレジームスコアを更新し、ヒステリシスを適用。
12. Signal Engineが戦略プラグインを順に評価し、候補シグナルを生成。
13. Execution Modelがヒューマン遅延Δt・Fillモデル（Marketable Limit/IOC）・滑り分布を適用し、想定約定価格・失効条件・コストを補正（FR-27, FR-29, FR-39）。
14. Calendar Serviceの`GateState`によりイベントや休日でブロック対象となるシグナルを除外。
15. Scoring Serviceがハイブリッドスコアと安定性ペナルティで順位付けし、Spread Monitorがスプレッドクールダウン状態の場合はスコアを減衰（FR-41）。Funding Serviceが`swap_penalty`を供給し、保有期間が長期化するストラテジにはスワップコストをシミュレーション時のスコアに反映する。
16. Risk Managerが`AccountState`、`BrokerSpecs`、`SpreadMetrics`、`FundingCurve`を参照しつつリスク制約（ドローダウン/連敗/スプレッド上限/マージン/日次スワップ）をチェック。SPRTベースのライブ健全性ガードはM2以降で有効化し、適用時はHealth Monitorへステータスを送信（FR-05, FR-22〈M2+〉, FR-28, FR-36）。
17. Correlation Guardが通貨バケット相関・シンボル相関行列を評価し、許容度を超えるシグナルを抑制。
18. Position Sizerが`AccountState`・`BrokerSpecs`・最新レート・スプレッド・Execution Model補正を用いて推奨ロットサイズとOCO値を決定。
19. Reduce-Only Advisor（M2+）が`HealthState`とマージン閾値・イベント窓情報から新規提案可否を判断し、必要時は`ReduceOnlyTicket`を生成。M1は同条件での手動レビューのみ。
20. Ticket Builderが`BrokerSpecs`を用いた桁/最小距離検証、Marketable Limit提示、TTL/ドリフト監視設定、ヒューマンエラーチェックリスト（ダブルチェック/SLTP/OCO）を付与し、Signal Boardへ配信（FR-30, FR-38, FR-39）。
21. ユーザーがチケットを承認/却下/編集->監査ログ記録。承認後のSL/TP未入力やTTL超過は自動アラート。
22. Trade Journal Serviceが承認/却下イベントとユーザーコメントを`journal_entries.db`へ保存し、戦略/レジーム別メタデータを更新（FR-44, AC-37）。
23. Parameter Drift Monitor（M2+）が最新最適化結果と現行パラメータを比較し、KLダイバージェンスしきい値を超えた場合は`benchmark_gap`同様にHealth Monitorへ理由を追加（FR-45）。
24. Benchmark MonitorがベンチマークCSVとの差分を計算し、`benchmark_gap_pct`を更新。ギャップ>5%（設定値）でアラートを発火し、運用健全性ダッシュボードにハイライト（FR-46, FR-48）。
25. Reporterが定期的にレポート/ログを出力し、Spread/Correlation/Resync/StressTest/Journal要約も含めてダッシュボードに反映（FR-10, FR-43, FR-44）。
26. Observability Exporterが最新メトリクスを`/metrics`へ公開し、必要に応じて`tradectl metrics push`でスナップショットをRunbookへ添付（NFR-06, NFR-15）。
27. Kill Switchまたはアラート条件が発火した場合、Emergency Orchestratorが`emergency.yaml`に基づきアクション（Reduce-Only提案、通知、再接続リトライ）を実行し、Mode Controllerが新規提案を停止（FR-47）。
28. Configuration Governanceが安全項目のホットリロードを配信し、Signal Engine/リスク管理へ反映。危険項目は`NextBarChangeQueue`に保留し、次バー確定時にSession Managerが適用して監査イベントを出力。

### 3.1 CLIインターフェース仕様（M1）
- **`tradectl board`**: Signal Board表示コマンド。入力として`logs/events/signal_today.jsonl`をストリームし、最新バーごとに表形式レンダリング。出力列は`symbol, side, entry, size, sl, tp, score, ttl, badges`。`--filter symbol=USDJPY`や`--view open_tickets`などのフィルタ/ビュー切替を提供。
- **`tradectl ticket approve|reject|edit`**: チケット操作。引数は`--id <ticket_id>`とし、`edit`時は`--field sl=151.20`のように複数指定可。処理結果は`audit`イベントとして`logs/events/DATE.jsonl`に追記される。
- **`tradectl events tail`**: Event Bus監視。`--type`で`signal|risk|execution|health|audit`を絞り込み、デフォルトは`signal`。出力フォーマットは`[ts][type] payload_json`。
- **`tradectl status`**: セッションのヘルスと統計を表示。`HealthState`（`status`, `reasons`）と`Snapshot`のハッシュ、現在のSpreadCooldownStateや未処理Reduce-Onlyチケット数、`benchmark_gap_pct`、直近ジャーナルハイライト（最新コメント/評価）を含む。
- **`tradectl export --what tickets|signals|account`**: 指定リソースをCSV/JSONにエクスポート。既定は`csv`で`--format json`指定可。出力パスは`reports/export/<date>/<what>.<ext>`。
- **`tradectl emergency trigger <scenario>` / `dry-run`**: `emergency.yaml`に定義されたシナリオを実行/検証。`--force`は確認プロンプトを無効化（Runbook承認が必要）。
- **`tradectl journal review`**: 直近の承認チケットとユーザーコメント、戦略別KPIを表形式で表示。`--weeks 4`等で期間指定。
- **`tradectl benchmark compare`**: ベンチマークCSVと最新エクイティを比較し、ギャップと指標差を出力。`--plot`で差分チャートを生成。
- **`tradectl stress run <scenario>`**: ストレステストシナリオを実行し、結果を`reports/stress/<scenario>/index.md`へ書き出す。`--sensitivity spread=1.5`等で感度上書き。
- **`tradectl metrics serve|push`**: Prometheus互換メトリクスエンドポイントを起動/ワンショット出力。`serve`はローカルHTTPサーバを起動、`push`はJSON/Markdownレポートに埋め込む。
- **JSON Linesインターフェース**: CLIコマンドは`stdout`にJSON Linesを返し、他ツール（例: `jq`）との連携を容易にする。例:`tradectl board --view json`で同一データをJSON Linesとして出力。
- **エラー挙動**: コマンド実行失敗時は非ゼロ終了コードを返却し、`stderr`に`[ERROR] <message>`形式で出力。必要に応じて`--no-prompt`（確認ダイアログ無効化）や`--yes`（承認操作の即時実行）を提供し、HITL確認はデフォルトでY/Nプロンプトを表示。
- **終了コードガイド**: `0=Success`, `10x=Validation/入力エラー`, `20x=I/O・データ欠損`, `30x=内部例外（トレース表示）` とし、Runbook・テストケースで参照する。

### 3.2 処理シーケンスと並行性
1. **Bar Ingestor（Producer）**: `asyncio`タスクで5分足を取得し、`bar_queue`（`asyncio.Queue(maxsize=1)`）に最新バーを投入。過去バーと重複の場合はスキップ。
2. **Pipeline Worker（Consumer）**: 単一ワーカーが`bar_queue.get()`でバーを受け取り、Feature→Regime→Signal→Execution→Risk→Sizing→Ticketの同期パイプラインを実行。各ステージは`PipelineContext`を介して共通キャッシュ/設定にアクセス。
3. **Event Dispatcher**: パイプライン結果を非同期タスクに渡し、Event Bus publish、JSONL書き込み、メール送信を行う。`asyncio.create_task`でバックグラウンド実行。
4. **Snapshot Writer**: パイプライン完了後に`Snapshot Manager`が更新された`AccountState`と未処理チケットを保存。CLIはこのスナップショット/ログを参照するため、パイプラインとは疎結合。
5. **並列性ポリシー**: M1は順次実行（1ワーカー）で整合性優先。将来はステージごとに並列化を検討し、`Signal Engine`を非同期化、`Risk Manager`で排他制御を行う。
6. **サイドタスク**: Emergency Orchestratorは`asyncio.create_task`で常駐し、`HealthState`と`emergency.yaml`監視を行う。Observability Exporterは別スレッドのHTTPサーバでメトリクスを公開し、StressTest/Benchmarkジョブは`asyncio.Queue`ベースのワーカーで逐次処理する。

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
- **Board描画**: `rich.table.Table`を利用。共通フォーマッタは`src/interfaces/renderers.py`にまとめ、スコア強調・TTLカラーリングの関数を用意。
- **承認系コマンド**: `tickets.py`で `TicketRepository`（persistenceレイヤ）をDI。承認結果を`AuditTrailService.log()`に渡し、成功時はCLIに`Approved ticket <id>`を表示。
- **イベント監視**: `events.py`では`watchdog`等に依存せず、5秒間隔でファイル末尾をtailする簡易実装。M2以降でWebSocket通知に切替可能な構造にする。
- **テスト**: `tests/interfaces/test_cli_board.py`で`CliRunner`を用いたsnapshotテストを追加。サンプルイベントファイルは`tests/fixtures/events/`に配置。
- **メトリクス収集**: CLIコマンド実行時間を`metrics/cli_perf.jsonl`に追記するオプション（`--metrics`) を用意し、運用時にボード表示のレスポンスを計測可能にする。
- **設定優先順位**: `ConfigRegistry`は `CLIフラグ > 環境変数 > profile YAML > デフォルト値`の順に評価。CLIで`--profile`を指定しなければ`config/profile_live.yaml`が既定。環境変数は`CODEX_`プレフィックスで上書き。

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
- **相関メトリクス**: `data/correlation/`以下に通貨バケット別エクスポージャ履歴と相関行列（Parquet/PNGヒートマップ）を保存し、リスク検証に利用。
- **パラメータ履歴**: `data/optimization/history/`配下に最適化設定と結果をJSONで保存し、`parameter_drift.parquet`に主要パラメータの時系列を記録。ドリフト検知はここを参照する。
- **ベンチマークデータ**: `data/benchmark_feeds/*.csv`に外部シグナル/指数の履歴を格納。必須列は`timestamp, equity, metric_sharpe, metric_dd`など。取り込み時に`benchmark_registry.json`へメタデータを書き込む。
- **監査ログ**: `logs/events/`配下に日次ローテーション。`event_type`毎に索引ファイルを生成し、`Audit Trail Service`が二重書き込み結果をチェックサムで検証する。
- **設定変更ガバナンス**: `logs/config/changes.jsonl`に`cfg_hash_before/after`、安全/危険分類、適用時刻を記録。週次で`ConfigDriftReport`を生成（FR-23, FR-33）。
- **緊急プロトコル**: `config/emergency.yaml`にシナリオ/条件/アクション列を保持。`config/risk_policy.yaml`と整合性チェックし、ハッシュを`logs/config/emergency_hash.json`へ出力。
- **データマニフェスト/署名**: `reports/data_manifest.json`に利用データセットのハッシュ/期間/取得元/バージョンを列挙し、`reports/data_manifest.sig`にEd25519署名を保存。`tradectl data verify`で検証し、アーカイブZIPへ両ファイルを同梱（FR-25, FR-52）。

### 4.1 Catch-up / Resync フロー
- **開始トリガー**: 起動時・手動`tradectl resync`・データ欠損検知時にSession Managerが`resync`タスクを起動。
- **欠落検知**: 最新スナップショットと`logs/events`内の`MarketUpdate`タイムスタンプを突合し、欠落バー区間を特定。
- **バックフィル**: Data Ingestionが欠落期間を優先的に取得し、Parquetキャッシュを更新。プロバイダ障害時は代替ソースへフォールバック。
- **増分再計算**: Feature Engineはバックフィル区間とTTL=3*TFぶんを再計算し、それ以外はキャッシュ値を再利用。
- **シグナル評価**: 再計算したバーについてRegime/Scoring/Execution/Risk/Sizingを再実行し、TTL切れやドリフト超過のチケットは自動失効マーク。
- **スナップショット更新**: 処理完了後に`./snapshots`へ状態を保存し、復旧時のレイテンシを最小化。
- **品質ガード連携**: 欠損率>0.5%/日または外れ値比率>0.2%検知で`DataQualityAlert`イベントを発火し、Risk Managerへ`DATA_STOP`フラグを送信。Kill SwitchがSOFT_STOPへ遷移し、新規提案は抑止。復旧後3バー連続で正常値を確認したら自動解除。
- **カレンダー更新**: Resync完了後にCalendar ServiceがCSVの更新日時を確認し、差分があれば`GateState`を再生成。外部API同期は日次タスクで実行し、成功時にCSVを上書きする。DST境界のイベントはUTC→`trading_timezone`再変換で再評価。
- **レート更新**: Resync対象期間に為替レート欠損があればFX Rate Updaterが再取得し、`fx_rates.parquet`を補完。フォールバック経路を用いたクロスレート再計算も同タイミングで実施。
- **スプレッド補完**: Spread Monitorがイベントログと照合し、欠損区間のBid/Askを再取得。取得不能な区間は直近ヒストリカル統計で補間し、補間フラグを付与。
- **相関再計算**: Resyncで約定履歴が変わった場合、Account Serviceが通貨バケット別エクスポージャ履歴を再構築し、Correlation Guard用の相関行列/ヒートマップを更新。
- **マニフェスト更新**: Resync完了時に`DataManifestBuilder`が対象期間・利用データソース・ハッシュを再集計し、`reports/data_manifest.json`とZIPパッケージを更新（FR-25）。

### 4.2 マルチタイムフレーム更新
- トリガーTF（既定:5m）のバー確定ごとに、下記リングバッファを更新し上位TFを再構築。
  - 1時間足: 12バーごとにOHLCVを確定し、途中値は局所バッファで累積。
  - 日足（将来拡張）等も同様に`TF_ratio`を用いた集約を準備。
- Feature Engineは`changed_timeframes`セットを保持し、変化したTFのみテクニカル指標を再計算する。
- 欠損や遡り更新が発生した場合は影響範囲（例えば1時間足なら直近3本）を再計算し、その他はキャッシュ値を保持する。

### 4.3 口座通貨換算ポリシー
- **リアルタイム評価**: Live/Paperモードでは最新5分足の終値またはブローカー提供のBid/Ask中央値を使用し、`AccountState`内の証拠金・含み損益を口座通貨へ換算。
- **フォールバック**: リアルタイムレートが取得できない場合は最後に取得した値を保持し、Catch-up時に正式な終値へ補正。
- **日次集計**: レポート/リスク指標の集計には日次終値を利用し、Backtestの結果と一致させる。
- **記録**: リアルタイム換算値と日次終値を両方`fx_rates.parquet`に保存し、監査時に追跡可能とする。
- **クロスレート優先順位**: 直接ティッカーが存在しない場合は`USD`経由（例: EURUSD × USDJPY）を第一優先、次に`JPY`/`EUR`等のバックアップ経路を設定し、経路と適用時刻を`fx_rates.parquet`へ記録する。
- **安定化**: クロスレート経路は`fx_rates.parquet`内に`source_priority`列を持ち、1位ソースとの差異が閾値超過した場合は`RateAnomaly`イベントを`Audit Trail Service`へ送信する（FR-21と整合）。

### 4.4 レート更新スケジュール
- **5分更新**: トリガー足確定時にFX Rate Updaterが必要通貨ペアの最新値を取得し、差異>0.02%または1時間経過で`fx_rates.parquet`を上書き。
- **日次補正**: ロールオーバー後に終値ベースのレートを取得し、当日のリアルタイム値との差異を記録。補正後に`AccountState`の過去分も再計算。
- **ソース優先度**: 1) yfinance 2) 直近成功値（`fx_rates.parquet`キャッシュ）3) 手動CSV。M2以降でブローカーAPIを追加ソースとして統合し、優先順位はユーザー設定で切替可能。
- **ロック戦略**: レート更新は専用`RatesLock`を取得したFX Rate Updaterのみが実行。Spread MonitorとCorrelationバッチも同一ロックを共有し、Resync/バックフィル中は収集タスクを一時停止（ロック待機）して整合性を確保。更新失敗時はロールバックしてロック解放。
- **ヘルスチェック**: 連続失敗回数が閾値を超えた場合はHealth Monitorへ`RATES_DEGRADED`を送信し、Reduce-Only Advisorへ新規縮小提案フラグを通知。解除後は監査ログに回復イベントを記録。

### 4.5 スプレッド観測スケジュール
- **観測ソース**: M1はDukascopyティック/公開CSV/手入力CSVから事前集計したヒストリカル分位を利用し、Spread Monitorは`spread_metrics.parquet`を更新。M2以降はブローカーフィードを60秒間隔でポーリングしてリアルタイム追記。
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
| account | 残高・証拠金・ポジション集計 | TradeLogs, BrokerSnapshot | AccountState |
| fx_rates | レート取得・クロス計算 | yfinance, fx_rates.parquet, 手入力CSV (M2+: BrokerFeed) | FxRateCache |
| calendar | 経済指標ブロック, 休日/ロールオーバー制御 | events.csv, holidays.csv, API同期 | GateState |
| broker_specs | ブローカー仕様ロード | broker_rules.yaml | BrokerSpecs |
| spread | スプレッド観測・集計・クールダウン制御 | spread_metrics.parquet (Dukascopy/CSV, M1) / BrokerFeed (M2+) | SpreadMetrics, SpreadCooldownState |
| liquidity | マルチソースレート比較・乖離Zスコア計算 | yfinance, Dukascopy, broker API/CSV | LiquiditySnapshot, LiquidityAlerts |
| execution | Fill/滑り/Marketable Limitモデル | MarketData, SpreadMetrics, execution_model.yaml | ExecutionAdjustments |
| scoring | Hybird最適化スコア、Stability | RawSignals, BacktestStats | RankedSignals |
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
- **Signal Engine**は`StrategyPlugin`抽象基底クラスを介してルール/モデル（FR-04）をロードし、`evaluate(context)`で`RawSignal`を返却。プラグインは`@strategy_plugin(name="donchian_breakout")`などのデコレータ登録。
- **Execution Model**は`RawSignal`に`ExecutionAdjustments`（滑り補正、Marketable Limit保護幅、IOC有効期限、Human Delay Δt）を付与し、Backtest/Paper/Liveで整合したFill判定を行う（FR-27, FR-29, FR-39）。
- **Scoring Service**は`RawSignal`に対して`HybridScore = w_recency·PF_recent + w_global·PF_all − λ·DD_all − γ·(1−Stability)`（FR-19, FR-21）を評価し、`Stability`は±10%摂動のドローダウン差分から算出。Spread Monitorがクールダウン中の場合は`HybridScore`を`cooldown_penalty`で縮小する（FR-41）。
- **Risk Manager**は`RiskPolicy`（per_trade, daily_loss, weekly_loss, SPRT thresholds, margin guard, spread guard）を参照し、Kill SwitchやSPRTフェーズ（FR-05, FR-22, FR-36）に応じて`SignalAction`（allow/defer/block/reduce_only）を出力。
- **Liquidity Intelligence Service**は`quote_snapshot`ストリームから`LiquiditySnapshot`を作成し、`zscore_spread`/`quote_age_ms`が閾値を超えた場合に`liquidity.alert`をRisk Managerへ送信。Risk Managerは該当シグナルを`HOLD`に設定し、解除時は`liquidity.resume`イベントで再開（FR-49, AC-38）。
- **Correlation Guard**は`CorrelationMatrix`と`BrokerSpecs`から`R_eff`を計算し（FR-37）、超過時はリスク比重を削減またはシグナル除外。Reduce-Only Advisorへ優先クローズ候補を通知する。
- **Position Sizer**はFixed Fractionalを基本に、`SpreadMetrics`/`BrokerSpecs`/`FxRateCache`/`ExecutionAdjustments`を用いてR値を整合。`min_stop_distance`未満の場合は`Ticket Builder`へ補正案を返却（FR-38）。
- **Compliance Validator**は`TradeTickets`候補を受け取り、`broker_rules.yaml`の`max_positions`, `netting`, `fifo`, `leverage_limit`と`risk_policy.yaml`の`profile_limits`を照合。違反時は代替案（Reduce-Only/部分クローズ/サイズ調整）を生成し、承認不可としてTicket Builderへ返却（FR-50, AC-39）。
- **Capital Allocation Guard**は`AccountState`のエクスポージャとVaR/ESを計算し、`capital_guard.yaml`または`risk_policy.yaml`の閾値と比較。超過時は`rate_limit`をRisk Managerへ渡し、提案頻度や最大サイズを減衰させる（FR-51, AC-40）。解除条件が満たされると`capital_guard.released`イベントを発行。
- **Reduce-Only Advisor**は`HealthState`/`GateState`/`R_eff`/`free_margin`を監視し、条件一致時にポジション縮小案（Reduce-Only）を生成（FR-42）。
- **Ticket Builder**は`HumanErrorChecklist`（桁/丸め/TP/SL/OCO/ReduceOnly分類）を評価し、未充足項目はSignal Boardで赤バッジ表示（FR-30, FR-39）。
- **Data Provenance Service**は`AssetWriteEvents`から`data_manifest.json`と`data_manifest.sig`を更新し、`tradectl data verify`に必要なハッシュ・署名を提供。検証失敗時は`data_provenance.alert`イベントを発火してHealth Monitorへ連携（FR-52, AC-41）。

## 7. 非機能要件への対応方針
- **性能**: pandasベース処理＋numba/ポリシー最適化と差分再計算キャッシュで5分足ストリーム遅延<100msを目標化。I/Oは非同期キューで平滑化。`perf_counter`計測を`on_bar_in`～`board_render`で常時実施し、p95/p99を`metrics/perf.json`に出力してNFR-01/AC-05を監視する。
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
- **復元時整合性チェック**: スナップショット復元時は`cfg_hash`/`data_hash`の一致、未処理チケットと監査ログ最終イベントの整合、`HealthState`が`soft_stop`以上の場合の解除手順を確認し、Runbookへ結果をフィードバックする。

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
3. **戦略パイプライン**: MA+RSI戦略、Execution Model（ヒストリカル分位滑り/Marketable Limit）、Scoring Service（ハイブリッドスコア＋Stability）。
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
- Resync手順: `tradectl resync --since <ts>`で欠落区間を指定可能。完了後に`reports/latest.md`と`logs/events`で再評価結果を確認。
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
| FR-19, FR-21 | 6.1 Scoring Service、4.3 口座通貨換算ポリシー |
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
| FR-42 | 2.1 Reduce-Only Advisor（M2+）、3. ユースケースフロー(17,21※M2+)、6 reduce_only |
| FR-49 | 2.1 Liquidity Intelligence Service、2.2 Liquidity Guard Pipeline、3. ユースケースフロー(6)、6 liquidity |
| FR-50 | 2.1 Compliance Validator、2.2 Compliance & Capital Policy Layer、6 compliance |
| FR-51 | 2.1 Capital Allocation Guard、2.2 Compliance & Capital Policy Layer、6 capital_guard |
| FR-52 | 2.1 Data Provenance Service、2.2 Data Provenance Mesh、4 データ構造（データマニフェスト/署名）、6 data_provenance |

## 11. リスクと未解決課題
- **執行モデルの検証データ**: ブローカーAPI未接続のため、初期は過去手動記録やDukascopyティックから推定する。ライブ移行前に限定サイズでPaper/Livetrade比較検証が必要。
- **Reduce-Only運用負荷**: 連続イベント発火時の運用負荷を抑えるため、優先度キューとCLIバッチ操作のUX検証が必要。
- **SPRTしきい値チューニング**: ヒストリカル性能が乏しい戦略追加時は誤検出リスクがあるため、戦略ごとのベイジアン更新案を検討。

## 12. 今後の拡張ポイント
- ブローカーAPI連携（自動発注化）
- GUI (React + Tauri) の提供
- ボラティリティターゲティング等の高度なサイジング
- 強化学習/機械学習モデルの導入（リスク管理に合わせた段階的適用）
