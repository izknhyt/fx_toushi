# FXヒューマン・インザループ投資ツール 基本設計書 v1.1

## 0. 文書情報
- 作成日: 2025-02-20
- 作成者: Codex AI 支援
- 参照文書: `要件定義（テンプレ形式）v_1.md`
- 想定リリース: マイルストーンM1（MVP）

### 0.1 改訂履歴
| 版 | 日付 | 改訂概要 |
| --- | --- | --- |
| v1.1 | 2025-02-20 | 要件差分レビュー結果を反映。コスト/執行モデル、ヒューマンエラー抑止、スプレッドクールダウン、Reduce-Onlyセーフティ等の設計を具体化し、トレーサビリティを拡充。 |
| v1.0 | 2025-02-15 | 初版作成 |

## 1. システム概要
- 目的: 主要FXペアに対する裁量支援（HITL）トレードを自動化された分析と提案で補助し、Sharpe/Sortino/最大DDなどのKPIを達成する。
- ユーザー: 個人トレーダー（プロダクトオーナー）
- 運用形態: macOS上でPython 3.11アプリケーションとして稼働。PC稼働時のみオンライン。
- 稼働モード: Backtest / PaperTrade / LiveTrade の3モードを共通コードベースで提供。
- 投資対象: USDJPY, EURUSD, GBPUSD, EURJPY (MVP)。

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
│  FX Rate Updater -> Spread Monitor -> Execution Model -> Calendar Gate -> Scoring -> Risk Manager -> Correlation Guard -> Position Sizer -> Reduce-Only Advisor │
│  Ticket Builder -> Audit & Persistence  │
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
| CLI/Signal Board | 提案表示・操作入力 | Rich CLI（M1）、将来React GUI |
| Session Manager | アプリ全体の起動・終了、Catch-up調整 | Python service |
| Mode Controller | Backtest/Paper/Liveの振る舞い切替 | Stateパターン |
| Data Ingestion Service | データ取得・キャッシュ管理 | yfinance, Dukascopy, CSV |
| Data Quality Guard | 欠損/外れ値判定、再取得制御 | Pandas/Numpy |
| Feature Engine | インジケータ計算・マルチTF合成 | pandas-ta/custom |
| Regime Detector | レジーム分類（ADX等） | 独自ロジック |
| Account Service | 残高/証拠金/ポジション集計・相関用エクスポージャ算出 | Backtest台帳, Paperログ, Live CSV |
| Funding Service | スワップ/ファンディングレートの取得と適用 | broker_rules.yaml, swap_rates.csv |
| FX Rate Updater | 口座通貨換算レート取得/保存 | yfinance, ブローカーフィード, CSV |
| Calendar Service | 経済指標/休日スケジュール配信（出力: GateState） | ローカルCSV, 外部API同期 |
| Broker Rules Loader | ブローカー仕様読み込み（pip値/contract等） | YAML loader (`broker_rules.yaml`) |
| Spread Monitor | スプレッド/コスト観測・クールダウン制御 | Broker API + `spread_metrics.parquet` |
| Execution Model | スリッページ/ロールオーバー/Fill判定モデル | MarketData, SpreadMetrics, broker_rules.yaml |
| Correlation Guard | 通貨/シンボル相関制御 | Rule-based filter |
| Signal Engine | ルール/モデルプラグインIF | Strategyプラグイン |
| Risk Manager | リスク制約・Kill Switch・スプレッド制御 | Policy engine |
| Position Sizer | Fixed Fractionalロジック | Python class |
| Reduce-Only Advisor | 収縮提案生成（閾値到達時） | Python service |
| Ticket Builder | 注文チケット生成・ヒューマンエラーチェック | JSON Lines |
| Persistence & Audit | イベント/ログ/設定履歴 | SQLite/Parquet/JSON |
| Optimizer | グリッド/ランダム/WFA | SciPy/自作 |
| Reporter | 週次/エクイティ/メトリクス出力 | Markdown/HTML |
| Alert Dispatcher | メール通知 | SMTPライブラリ |

### 2.2 クロスカッティング・コンポーネント
- **Configuration Governance**: `ConfigRegistry`（シングルトン）でYAMLプロファイルを管理し、JSON Schema検証（FR-23）とバージョンハッシュを計算。安全項目はPub/Subでホットリロードし、危険項目は`NextBarChangeQueue`で遅延適用する。
- **Event Bus**: Domain層間の疎結合を保つために`DomainEventBus`を採用。同期処理はコアフロー、非同期処理（レポート生成、Slack通知など）はワーカーキューに委譲する。`MarketableLimitApplied`や`ReduceOnlyIssued`など執行関連イベントも同バスで配信する。
- **Snapshot Manager**: `./snapshots/latest/*.json`にセッション状態（Open Tickets、AccountState、GateState、CfgHash）を周期保存し、再起動時にSession Managerがリプレイ（FR-18）。
- **Health Monitor**: SPRT評価（FR-22）、Kill Switch（FR-05）、連続エラー検出（FR-12）を統合して`HealthState`を更新し、Signal Engine/Mode Controllerへブロードキャスト。
- **Audit Trail Service**: 監査イベント（FR-11）を受け取ってJSONL/SQLiteへ二重書き込みし、書き込み失敗時はWrite-Aheadログでロールフォワード可能にする（ERROR-C04対策）。`HumanCheckFailed`等のヒューマンエラー検知もここで証跡化する。

## 3. ユースケースフロー（MVP）
1. アプリ起動 -> Session Managerが設定読み込み・Catch-upキュー投入->履歴データ同期。
2. Data Ingestionが所定ティッカーの新規バーを取得し、キャッシュを更新。
3. Broker Rules Loaderが`broker_rules.yaml`をロードし、pip値/contract size/最小ロット/tick制約を`BrokerSpecs`として共有キャッシュに展開。
4. FX Rate Updaterが口座通貨換算レート（5m最新値＋日次終値）を取得し、差分があれば`fx_rates.parquet`を更新（排他ロック付与）。
5. Spread Monitorがブローカーフィードからスプレッド/手数料データを収集し、`SpreadMetrics`としてキャッシュ。
6. Funding Serviceが`broker_rules.yaml`で定義されたスワップ計算ルールを読み込み、`swap_rates.csv`およびブローカーフィードから当日分のロング/ショートスワップ（Wednesday\_NYの3倍など）を取得し、`FundingCurve`を生成。
7. Account Serviceがモード別データソース（Backtest: シミュレーション台帳 / Paper: 仮想約定ログ / Live: ユーザー入力またはブローカーCSV）と最新レートを用いてアカウント状態を集計し、通貨バケット別エクスポージャと相関エクスポージャを算出して`AccountState`を更新。スワップは`FundingCurve`を日次で織り込んだキャッシュフローとして反映し、バックテストでも同一ロジックを適用する（FR-28）。
8. Calendar Serviceが経済指標CSV/休日CSVをUTC基準でロードし、設定された`trading_timezone`（既定:JST）に変換した上で現在時刻に対するブロック/解除ウィンドウを判定して`GateState`を更新。イベント強度に応じた±15/30分の動的拡張ルールもここで適用する。
9. Feature Engineが差分計算で新規バー分の指標を更新し、必要な区間のみ再計算。
10. Regime Detectorが最新特徴量からレジームスコアを更新し、ヒステリシスを適用。
11. Signal Engineが戦略プラグインを順に評価し、候補シグナルを生成。
12. Execution Modelがヒューマン遅延Δt・Fillモデル（Marketable Limit/IOC）・滑り分布を適用し、想定約定価格・失効条件・コストを補正（FR-27, FR-29, FR-39）。
13. Calendar Serviceの`GateState`によりイベントや休日でブロック対象となるシグナルを除外。
14. Scoring Serviceがハイブリッドスコアと安定性ペナルティで順位付けし、Spread Monitorがスプレッドクールダウン状態の場合はスコアを減衰（FR-41）。Funding Serviceが`swap_penalty`を供給し、保有期間が長期化するストラテジにはスワップコストをシミュレーション時のスコアに反映する。
15. Risk Managerが`AccountState`、`BrokerSpecs`、`SpreadMetrics`、`FundingCurve`を参照しつつリスク制約（ドローダウン/連敗/SPRT/スプレッド上限/マージン/日次スワップ）をチェック。閾値到達時はHealth Monitorへステータスを送信（FR-05, FR-22, FR-28, FR-36）。
16. Correlation Guardが通貨バケット相関・シンボル相関行列を評価し、許容度を超えるシグナルを抑制。
17. Position Sizerが`AccountState`・`BrokerSpecs`・最新レート・スプレッド・Execution Model補正を用いて推奨ロットサイズとOCO値を決定。
18. Reduce-Only Advisorが`HealthState`とマージン閾値・イベント窓情報から新規提案可否を判断し、必要時は`ReduceOnlyTicket`を生成（FR-42）。
19. Ticket Builderが`BrokerSpecs`を用いた桁/最小距離検証、Marketable Limit提示、TTL/ドリフト監視設定、ヒューマンエラーチェックリスト（ダブルチェック/SLTP/OCO）を付与し、Signal Boardへ配信（FR-30, FR-38, FR-39）。
20. ユーザーがチケットを承認/却下/編集->監査ログ記録。承認後のSL/TP未入力やTTL超過は自動アラート。
21. Reporterが定期的にレポート/ログを出力し、Spread/Correlation/Resync結果も含めてダッシュボードに反映。
22. Kill Switchまたはアラート条件が発火した場合、Mode Controllerが新規提案を停止し、Reduce-Only Advisorへ縮小提案を指示。
23. Configuration Governanceが安全項目のホットリロードを配信し、Signal Engine/リスク管理へ反映。危険項目は`NextBarChangeQueue`に保留し、次バー確定時にSession Managerが適用して監査イベントを出力。

## 4. データ構造と保存先
- **マーケットデータ**: Parquet（ローカル）、キー: `{symbol}/{timeframe}`。カラム: ts, open, high, low, close, volume, spread(optional)。
- **特徴量キャッシュ**: Arrow/Parquet（将来）。MVPはオンメモリ計算＋serializeオプション。
- **イベントログ/監査**: JSON Lines（`./logs/events/DATE.jsonl`）。
- **設定**: YAML (`config/*.yaml`) + JSON Schema (`cfg.schema.json`)で検証。
- **バックテスト結果**: SQLiteまたはParquetで保存し、メタ情報（期間・戦略ハッシュ）を付与。
- **レポート**: Markdown/HTML/PDF生成を想定。MVPはMarkdown。
- **アカウント台帳**: モード別に保存形式を切替。Backtestは`backtests/results.db`内に`equity_curve`/`positions`テーブル、Paperは`logs/paper_account.jsonl`、Liveはユーザー入力CSVを`data/account/live_account.csv`で管理し、`AccountState`再構築時の入力とする。
- **カレンダーデータ**: `config/calendar/high_impact_events.csv`（経済指標）と`config/calendar/market_holidays.csv`（休日/ロールオーバー/Fix時間帯ルール）。週次で外部API同期（任意）しつつ、最新版CSVを起動時にロードし、Fixは影響度に応じて±15/30分の自動禁止窓を生成（FR-34, FR-40）。
- **カレンダーデータ基準**: CSVは全てUTCで記録し、`config/profile.yaml`の`trading_timezone`（例:JST/NY）へ変換して適用。DSTを持つタイムゾーンは`zoneinfo`で自動補正。
- **換算レート**: `data/account/fx_rates.parquet` に口座通貨換算用レート（5m最新値と日次終値）を保存し、リアルタイム評価と日次集計で使い分ける。
- **ブローカー仕様**: `config/broker_rules.yaml`でpip値、contract size、最小ロット、tick size、stop level/freeze levelを定義し、ロード結果を`BrokerSpecs`キャッシュとして全モジュールで参照。
- **スワップテーブル**: `config/swap_rates.csv`に通貨ペア×方向（long/short）の日次スワップポイント、三倍日フラグ、ロールオーバー時刻を格納。Funding Serviceが`swap_rates.parquet`へ変換し、`positions`テーブルと突合してキャッシュフローへ反映（FR-28）。
- **スプレッドメトリクス**: `data/spread_metrics.parquet`にスプレッド/手数料の観測結果を保存し、イベント影響や時刻別平均を蓄積してSpread Monitor/Riskが参照。バックテスト時はDukascopyティック/分足からBid/Askを再構成し、観測出来ない区間は`broker_rules.yaml`の固定スプレッドテーブルで補完。
- **執行モデルテーブル**: `config/execution_model.yaml`に時間帯×レジーム×シグナル種別ごとの滑り分布（p10/p50/p90）、Marketable Limit保護幅、IOC扱い可否、Human Delay分布を定義し、Execution Modelが参照。
- **相関メトリクス**: `data/correlation/`以下に通貨バケット別エクスポージャ履歴と相関行列（Parquet/PNGヒートマップ）を保存し、リスク検証に利用。
- **監査ログ**: `logs/events/`配下に日次ローテーション。`event_type`毎に索引ファイルを生成し、`Audit Trail Service`が二重書き込み結果をチェックサムで検証する。
- **設定変更ガバナンス**: `logs/config/changes.jsonl`に`cfg_hash_before/after`、安全/危険分類、適用時刻を記録。週次で`ConfigDriftReport`を生成（FR-23, FR-33）。

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
- **ソース優先度**: 1) ブローカー提供API 2) yfinance 3) 手動CSV。上位が失敗した場合は警告イベントをログし、下位ソースで補完。
- **ロック戦略**: レート更新は専用`RatesLock`を取得したFX Rate Updaterのみが実行。Spread MonitorとCorrelationバッチも同一ロックを共有し、Resync/バックフィル中は収集タスクを一時停止（ロック待機）して整合性を確保。更新失敗時はロールバックしてロック解放。
- **ヘルスチェック**: 連続失敗回数が閾値を超えた場合はHealth Monitorへ`RATES_DEGRADED`を送信し、Reduce-Only Advisorへ新規縮小提案フラグを通知。解除後は監査ログに回復イベントを記録。

### 4.5 スプレッド観測スケジュール
- **リアルタイム収集**: ブローカーフィードからBid/Askを60秒間隔でポーリングし、Spread Monitorが`spread_metrics.parquet`へ追記。スプレッド上限超過を検知した場合は即座にRiskへ通知し、`SpreadCooldownState`（連続N分正常化条件）を起動（FR-41）。
- **イベントタグ付与**: カレンダーイベント発生前後±60分のデータにタグを付け、分析時にイベント影響を評価できるようにする。
- **バックフィル**: Spreadデータ欠損時はブローカー提供履歴もしくは自前記録を再取得し、欠損区間の平均/分散を補完。バックテストではDukascopyティックから再構築し、該当データが無い場合は固定スプレッドで代替。
- **長期集計**: 日次で時間帯別（東京/ロンドン/NY）平均とp95を集計し、Risk/Position Sizerがスプレッドシナリオ検証に利用。バックテストレポートにも同じ集計を出力し、ライブとの差分を監視。
- **健全性ガード連携**: SPRTやKill Switchがアクティブな場合、Spread Monitorはスプレッド閾値を自動引き下げ（例: 10%）て追加保守モードへ移行し、解除時には監査イベントを記録する（FR-22）。SpreadCooldownState解除時はExecution Modelへ通知し、Marketable Limit幅を通常値に復帰させる。
- **マーケットプロファイル**: Spread MonitorはExecution Modelへ時間帯×レジーム別スリッページ分位を提供し、BT/ライブ整合性を強化（FR-27）。

### 4.6 相関評価スケジュール
- **ローリング計算**: 1日単位で通貨バケット別エクスポージャとシンボル相関を30日ローリングで算出し、`CorrelationMatrix`を更新。
- **ライブモニタ**: 新規提案前に最新エクスポージャと相関を即時計算し、許容バケット（例: 通貨別最大2件など）を超える場合はCorrelation Guardがシグナルを抑制。
- **シナリオ検証**: 週次バッチで過去12ヶ月の相関変動レンジを計測し、Riskポリシー（許容相関閾値）の再設定候補をレポート。
- **データ保存**: 生成した相関行列は`data/correlation/`にParquetとPNGで保存し、監査および分析用に残す。
- **Reduce-Only判定**: 相関異常で`R_eff`が`R_cap`を超えた場合はCorrelation GuardがReduce-Only Advisorへ縮小対象候補を提示し、寄与度に基づく優先順位を付ける（FR-37, FR-42）。

### 4.7 スワップ/ファンディング管理
- **取得経路**: `config/swap_rates.csv`（ユーザー管理）とブローカー提供のCSV/APIの双方に対応し、優先度 `broker_api > swap_rates.csv > 手動入力` で Funding Service が選択する。取得に失敗した場合は最終成功値を維持しつつ`FundingDegraded`イベントを発火。
- **正規化**: スワップは1ロットあたりの通貨建て値で保持し、`BrokerSpecs.min_lot`と`lot_step`で換算。`pip_size`と`price_decimals`に基づき丸めを行い、Human Errorチェックにも同じ丸め関数を提供。
- **適用タイミング**: Backtest/Paperはバー確定時に日次スワップを計上。Liveではロールオーバー時刻（例: 06:00 JST）に`FundingService.apply_daily_swap()`を発火し、`AccountState`に`swap_realized`を追加。
- **三倍日処理**: `swap_rates.csv`の`triple_day`列で曜日/祝日特例を管理。Funding ServiceはCalendar Serviceと連携して祝日シフトを検出し、該当日のスワップ倍率を補正。
- **シミュレーション設定**: Execution Modelに`funding_cost_curve`を渡し、約定時に想定保有期間×スワップを`ExpectedR`へ反映。Hybridスコアの`PF_recent`/`PF_all`計算でもスワップ控除後の損益を使用し、AC-18/AC-23の耐性評価と整合させる。
- **監査/可観測性**: `logs/events/funding.jsonl`で取得/適用イベントを追跡し、異常値や適用失敗はAlert Dispatcher経由で通知。ダッシュボードでは`swap_realized`と`swap_forecast`を可視化してNFR-06/11の指標に反映。

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
| fx_rates | レート取得・クロス計算 | yfinance, BrokerFeed, fx_rates.parquet | FxRateCache |
| calendar | 経済指標ブロック, 休日/ロールオーバー制御 | events.csv, holidays.csv, API同期 | GateState |
| broker_specs | ブローカー仕様ロード | broker_rules.yaml | BrokerSpecs |
| spread | スプレッド観測・集計・クールダウン制御 | BrokerFeed, spread_metrics.parquet | SpreadMetrics, SpreadCooldownState |
| execution | Fill/滑り/Marketable Limitモデル | MarketData, SpreadMetrics, execution_model.yaml | ExecutionAdjustments |
| scoring | Hybird最適化スコア、Stability | RawSignals, BacktestStats | RankedSignals |
| funding | スワップレート取得・適用・三倍日処理 | swap_rates.csv, broker_api, CalendarState | FundingCurve, FundingEvents |
| risk | 残余リスク計算、Kill Switch、マージン/スプレッド監視 | RankedSignals, AccountState, BrokerSpecs, SpreadMetrics, SpreadCooldownState, FundingCurve | RiskVettedSignals, HealthState |
| correlation | 通貨/シンボル相関評価 | AccountState, MarketData | CorrelationMatrix |
| correlation_guard | 相関ガード・バケット制御 | RiskVettedSignals, CorrelationMatrix | CorrelationFilteredSignals |
| sizing | Fixed Fractional、サイジング検証 | CorrelationFilteredSignals, AccountState, BrokerSpecs, FxRateCache, SpreadMetrics, ExecutionAdjustments | SizedSignals |
| reduce_only | Reduce-Only判定・提案 | SizedSignals, HealthState, GateState | ReduceOnlyTickets |
| ticket | TTL算出、OCO値提案、ヒューマンチェック、監査追跡 | SizedSignals ∪ ReduceOnlyTickets, BrokerSpecs | TradeTickets |
| backtester | シミュレーション、WFA | MarketData, Strategies | PerformanceStats |
| reporter | 指標集計、グラフ化 | PerformanceStats, Logs | Reports |
| persistence | Parquet/SQLite/JSONL管理 | 各種イベント | 永続化ファイル |

### 6.1 シグナル・リスク・サイジング連携
- **Signal Engine**は`StrategyPlugin`抽象基底クラスを介してルール/モデル（FR-04）をロードし、`evaluate(context)`で`RawSignal`を返却。プラグインは`@strategy_plugin(name="donchian_breakout")`などのデコレータ登録。
- **Execution Model**は`RawSignal`に`ExecutionAdjustments`（滑り補正、Marketable Limit保護幅、IOC有効期限、Human Delay Δt）を付与し、Backtest/Paper/Liveで整合したFill判定を行う（FR-27, FR-29, FR-39）。
- **Scoring Service**は`RawSignal`に対して`HybridScore = w_recency·PF_recent + w_global·PF_all − λ·DD_all − γ·(1−Stability)`（FR-19, FR-21）を評価し、`Stability`は±10%摂動のドローダウン差分から算出。Spread Monitorがクールダウン中の場合は`HybridScore`を`cooldown_penalty`で縮小する（FR-41）。
- **Risk Manager**は`RiskPolicy`（per_trade, daily_loss, weekly_loss, SPRT thresholds, margin guard, spread guard）を参照し、Kill SwitchやSPRTフェーズ（FR-05, FR-22, FR-36）に応じて`SignalAction`（allow/defer/block/reduce_only）を出力。
- **Correlation Guard**は`CorrelationMatrix`と`BrokerSpecs`から`R_eff`を計算し（FR-37）、超過時はリスク比重を削減またはシグナル除外。Reduce-Only Advisorへ優先クローズ候補を通知する。
- **Position Sizer**はFixed Fractionalを基本に、`SpreadMetrics`/`BrokerSpecs`/`FxRateCache`/`ExecutionAdjustments`を用いてR値を整合。`min_stop_distance`未満の場合は`Ticket Builder`へ補正案を返却（FR-38）。
- **Reduce-Only Advisor**は`HealthState`/`GateState`/`R_eff`/`free_margin`を監視し、条件一致時にポジション縮小案（Reduce-Only）を生成（FR-42）。
- **Ticket Builder**は`HumanErrorChecklist`（桁/丸め/TP/SL/OCO/ReduceOnly分類）を評価し、未充足項目はSignal Boardで赤バッジ表示（FR-30, FR-39）。

## 7. 非機能要件への対応方針
- **性能**: pandasベース処理＋numba/ポリシー最適化と差分再計算キャッシュで5分足ストリーム遅延<100msを目標化。I/Oは非同期キューで平滑化。`perf_counter`計測を`on_bar_in`～`board_render`で常時実施し、p95/p99を`metrics/perf.json`に出力してNFR-01/AC-05を監視する。
- **信頼性**: イベントソーシング（JSONL）＋定期スナップショットで再現性を確保し、データ品質ガードとKill Switch、Calendar Gate、FXレート補完、スプレッド監視、相関ガードを統合して異常時やイベント期間中/レート欠損時/相関過多時の自動停止・再開・補正を実現。Resyncフェーズは二相ロックで`MarketData`と`FeatureCache`を凍結し、終了後にSPRTリセット条件を評価する。
- **運用性**: CLIコマンド `tradectl`（想定）で start/stop/status/resync を提供。Spreadクールダウン解除、Reduce-Only解除、Marketable Limit幅調整など執行関連の運用コマンドも整備する。
- **セキュリティ/コンプラ**: HITL前提で助言表示を限定。設定変更・操作ログを全て監査保存。
- **拡張性**: Strategy/Scoring/Riskをプラグイン化（`entry_points` / 自前registry）。
- **再現性**: バックテスト/ライブの乱数seed、cfgハッシュ、データバージョンをレポート出力に埋め込み、`reports/*`のメタヘッダで差分検証可能とする（FR-25）。`FundingCurve`や`SpreadMetrics`など時系列キャッシュはハッシュ化してレポートに添付し、AC-13/AC-17とのトレーサビリティを担保する。
- **可観測性**: SpreadCooldownStateやReduce-Only発動履歴、Execution Modelの未約定率をメトリクス化し、NFR-06/NFR-11のダッシュボードに表示する。

## 8. 環境構成
- **OS**: macOS (ARM/x86)
- **言語**: Python 3.11
- **主要ライブラリ案**: pandas, numpy, ta-lib/pandas-ta, scikit-learn(将来), numba, click/rich, sqlalchemy, fastapi（将来GUI用API）。
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
  logs/
  reports/
```

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
| FR-42 | 2.1 Reduce-Only Advisor、3. ユースケースフロー(17,21)、6 reduce_only |

## 11. リスクと未解決課題
- **執行モデルの検証データ**: ブローカーAPI未接続のため、初期は過去手動記録やDukascopyティックから推定する。ライブ移行前に限定サイズでPaper/Livetrade比較検証が必要。
- **Reduce-Only運用負荷**: 連続イベント発火時の運用負荷を抑えるため、優先度キューとCLIバッチ操作のUX検証が必要。
- **SPRTしきい値チューニング**: ヒストリカル性能が乏しい戦略追加時は誤検出リスクがあるため、戦略ごとのベイジアン更新案を検討。

## 12. 今後の拡張ポイント
- ブローカーAPI連携（自動発注化）
- GUI (React + Tauri) の提供
- ボラティリティターゲティング等の高度なサイジング
- 強化学習/機械学習モデルの導入（リスク管理に合わせた段階的適用）
