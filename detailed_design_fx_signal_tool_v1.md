# FXヒューマン・インザループ投資ツール 詳細設計書 v1.0

## 0. 文書情報
- 作成日: 2025-02-15
- 作成者: Codex AI 支援
- 前提文書: 要件定義 v1.1, 基本設計書 v1.0
- 対象スコープ: マイルストーンM1 (Backtest/Paper/Live 共通基盤)

## 1. システム構成の詳細
```
src/
  app/
    main.py              # エントリーポイント
    cli.py               # Rich CLIコマンド定義
  core/
    session.py           # SessionManager, ModeController
    workflow.py          # Signalワークフローオーケストレーション
    events.py            # DomainEvent定義
  data/
    providers/           # 各データプロバイダ（yfinance, dukascopy, csv）
    cache.py             # Parquet/Arrowキャッシュ
    quality.py           # 欠損/外れ値ガード
  features/
    pipeline.py          # 指標計算パイプライン
    indicators.py        # 個別インジケータ実装
    regime.py            # レジーム検出器
  strategies/
    base.py              # StrategyInterface
    mean_reversion.py    # MA+RSIサンプル
    breakout.py          # Donchianサンプル
  scoring/
    hybrid.py            # w_recency 等の計算
    stability.py         # 摂動テスト
  risk/
    manager.py           # リスク制御、KillSwitch
    sprt.py              # SPRT検定
  sizing/
    fractional.py        # Fixed Fractional sizing
  ticket/
    builder.py           # 注文チケット構築
    validator.py         # Brokerルール適合検証
  backtest/
    engine.py            # 共通バックテストエンジン
    walkforward.py       # Walk-Forward
  report/
    generator.py         # 週次/成績レポート
  infra/
    persistence.py       # JSONL/SQLite書き込み
    scheduler.py         # イベントスケジューラ
    notifier.py          # メール通知
    config.py            # 設定読み込み/検証
```

## 2. コンポーネント仕様

### 2.1 SessionManager / ModeController (`core/session.py`)
- **責務**: アプリケーションライフサイクル、プロファイル選択、Catch-up処理。
- **主要クラス**:
  - `SessionManager`: `start(profile)`, `stop()`, `status()`, `resync()`。
  - `ModeController`: `set_mode(mode: Mode)`, `current_mode`, `mode_context`。
- **初期化手順**:
  1. 設定読み込み (`config.load_profile(profile)`)
  2. `catch_up()` で `resync` キュー投入
  3. モード別に `workflow.run()` をバックグラウンド実行
- **エラーハンドル**: 重大例外は `AlertDispatcher` へ通知後、`KillSwitch` と連携して新規提案停止。

### 2.2 Workflow Orchestrator (`core/workflow.py`)
- **責務**: 各フレーム（バー確定時）で pipeline を順次実行。
- **シーケンス**:
  1. `MarketDataService.fetch_latest()`
  2. `FeaturePipeline.recompute()`
  3. `StrategyRegistry.run_all()`
  4. `ScoringService.rank()`
  5. `RiskManager.filter()`
  6. `SizingService.size()`
  7. `TicketBuilder.build()` → イベント発火
- **実装詳細**:
  - イベントループ: `asyncio` で5分毎（Trigger TF）に実行。
  - 各段階で `DomainEvent` (例: `SignalCandidateGenerated`) を生成し、`EventBus` にpublish。

### 2.3 Data Provider 層 (`data/providers/`)
| クラス | 説明 | 主な関数 | 例外 |
| --- | --- | --- | --- |
| `YahooFinanceProvider` | yfinance経由で5分足取得 | `fetch(symbol, start, end)` | `ProviderError` |
| `DukascopyProvider` | Dukascopy HTTPバイナリ取得 | `fetch(symbol, start, end, timeframe)` | `ProviderError` |
| `CsvProvider` | ローカルCSV読み込み | `fetch(path)` | `FileNotFoundError` |

- **キャッシュ**: `MarketCache` が `to_parquet`/`read_parquet` を提供、TTLは設定値（既定: 1日）。
- **品質処理**: `DataQualityGuard.validate(df)` で欠損率、外れ値（Z-score）を評価し、閾値越え時 `DataQualityAlert` を発火。

### 2.4 Feature Pipeline (`features/pipeline.py`)
- **入力**: `MarketFrame` （MultiIndex: datetime×symbol）。
- **処理**:
  - 時間足変換: `resample()` により上位TF生成。
  - インジケータ: `IndicatorSet`（MA/EMA/RSI/MACD/ATR/BB/Donchian）。
  - マルチTF合成: `join_features(trigger_tf, ref_tfs)`。
- **出力**: `FeatureFrame` （列: feature名、欠損は`forward_fill`、初期バー不可はマスク）。
- **性能対策**: pandas rollingを極力共通化。Numba実装可否を flag で切替。

### 2.5 Regime Detector (`features/regime.py`)
- **手法**: ADX、TrueRange、自己相関、標準偏差等を複合→Softmaxでレジームスコア。
- **ロジック**: 直近Nバー（例: 60バー）で特徴量を算出→`RegimeState` dataclass (trend_strength, range_strength, volatility_level)。
- **ヒステリシス**: レジームスイッチ時は±Δしきい値を設け、短期ノイズで切り替わらないよう調整。

### 2.6 Strategy Interface (`strategies/base.py`)
```python
class Strategy(Protocol):
    id: str
    metadata: StrategyMetadata

    def generate_signals(self, features: FeatureFrame, regime: RegimeState,
                         context: StrategyContext) -> list[RawSignal]:
        ...
```
- `StrategyContext`: mode, profile,最近成績、スコア重み等を保持。
- 戦略アウトプット: `RawSignal` (symbol, side, confidence, entry, sl, tp, ttl_hint, evidence)。
- M1実装: `MaRsiStrategy`, `DonchianBreakoutStrategy`。

### 2.7 Scoring Service (`scoring/hybrid.py`)
- **目的**: FR-19, FR-21 を満たすスコア付与。
- **手順**:
  1. `BacktestStats`（recent/global）からPF、DD、stabilityを取得。
  2. `score = w_recency * pf_recent + w_global * pf_all - λ * max_dd - γ * (1 - stability)`。
  3. `stability` は ±10% 摂動での成績分散から算出。
- **出力**: `RankedSignal` (raw_signal, score, rank, badges)。

### 2.8 RiskManager (`risk/manager.py`)
- **評価項目**:
  - 1トレードリスク: `per_trade` 設定とATR/SL距離からポジション上限チェック。
  - 日次/週次ドローダウン: `DrawdownTracker` が損益ログから集計。
  - SPRT (`risk/sprt.py`): ライブ勝率の逐次検定。
  - 相関/同時ポジション: シンボルカテゴリ毎に上限設定。
- **API**:
```python
class RiskManager:
    def filter(self, ranked_signals: list[RankedSignal],
               account: AccountState) -> list[RiskVettedSignal]:
        ...
    def evaluate_kill_switch(self, pnl_log: PnLLog) -> KillSwitchState:
        ...
```
- **Kill Switch**: 状態遷移 `ACTIVE -> SOFT_STOP -> HARD_STOP`。解除は手動 + cooldown。

### 2.9 Sizing Service (`sizing/fractional.py`)
- **ロジック**:
  - `risk_per_trade = equity * per_trade`
  - `position_size = risk_per_trade / (abs(entry - sl) * pip_value)`
  - ブローカー仕様に合わせて丸め (`BrokerRules.round_lot`).
- **出力**: `SizedSignal` (size, risk_R, oco_values)。
- **検証**: `validator.py` が stop_level, freeze_level 遵守を確認。

### 2.10 TicketBuilder (`ticket/builder.py`)
- **入力**: `SizedSignal`, `Mode`, `ttl_factor`, `drift_max_R`。
- **処理**:
  - TTL算出: `ttl = timeframe_seconds * ttl_factor`。
  - ドリフト監視: 現行価格とentry差分が `drift_max_R` 超過で失効。
  - 監査情報: `TicketAuditRecord` を生成し JSONL に書き込み。
- **出力**: `TradeTicket` JSON
```json
{
  "id": "UUID",
  "symbol": "USDJPY",
  "side": "LONG",
  "entry": 151.23,
  "size": 41000,
  "sl": 151.00,
  "tp": 151.59,
  "ttl_sec": 900,
  "badges": ["ALIGN","VOL"],
  "score": 84.2,
  "mode": "LIVE",
  "expires_at": "2025-02-15T12:20:00+09:00"
}
```

### 2.11 Backtest Engine (`backtest/engine.py`)
- **設計**:
  - イベント駆動: 各バーで `Strategy.generate_signals`→`Risk/Sizing`→仮想約定。
  - Fillロジック: 成行（bar内平均）、指値（High/Low判定）をサポート。
  - コスト: spread, slippage (configurable)。
- **Walk-Forward**: `walkforward.py` が `TrainWindow`, `TestWindow` を生成し、PF/Sharpeを記録。
- **再現性**: `seed` を設定し、ランダム要素を固定。

### 2.12 Reporter (`report/generator.py`)
- **週次レポート**: 期間PF、WinRate、MaxDD、エクイティ曲線PNG（matplotlib）。
- **インフラ**: レポートファイルを `reports/YYYY-WW.md` に保存し、メール添付（任意）。
- **Paper/LIVE**: 未約定チケット、Kill Switch状態、SPRT状態も含め出力。

### 2.13 Persistence (`infra/persistence.py`)
- **イベント種別**: `MarketUpdate`, `SignalGenerated`, `TicketIssued`, `TicketAction(HITL)`, `KillSwitchChanged`, `ConfigChanged`。
- **保存**:
  - JSONL: `logs/events/2025-02-15.jsonl`
  - SQLite: `logs/audit.db`（`tickets`, `signals`, `pnl`, `settings` テーブル）
- **再開処理**: スナップショットファイル (`snapshots/YYYYMMDD-HHMM.json`) を読み込み、SessionManagerがステートを復元。

## 3. データモデル

### 3.1 MarketFrame
| フィールド | 型 | 説明 |
| --- | --- | --- |
| `timestamp` | `DatetimeIndex` | UTC基準 (内部) |
| `symbol` | `Categorical` | 主要4ペア + 拡張 |
| `open/close/high/low` | `float64` | 価格 |
| `volume` | `float64` (optional) | 出来高 |
| `spread` | `float32` | スプレッドpips |
| `quality_flag` | `int` | 欠損補完/外れ値マーク |

### 3.2 FeatureFrame
| 列名例 | 型 | 備考 |
| --- | --- | --- |
| `ma_fast`, `ma_slow` | `float64` | 移動平均 |
| `ema_12`, `ema_26` | `float64` | EMA |
| `rsi_14` | `float32` | RSI |
| `macd`, `macd_signal` | `float32` | MACD |
| `atr_14` | `float32` | ATR |
| `bb_upper`, `bb_lower` | `float32` | ボリンジャーバンド |
| `donchian_high`, `donchian_low` | `float64` | Donchian Channel |
| `adx_14` | `float32` | ADX |
| `volatility_regime` | `category` | low/medium/high |

### 3.3 RawSignal / RankedSignal / TradeTicket
- `RawSignal`: symbol, side(enum), entry_mode (close/limit), entry_price, sl_price, tp_price, confidence, context_tags。
- `RankedSignal`: raw_signal, score, rank, stability, badges。
- `RiskVettedSignal`: ranked_signal + kill_switch_state, limit_flags。
- `SizedSignal`: risk_vetted_signal + size, risk_R, margin_estimate。
- `TradeTicket`: sized_signal + ttl, drift_guard, audit_id。

## 4. ワークフロー詳細

### 4.1 Backtestモード
1. `BacktestRunner` 初期化 (`config.backtest` + データ区間を指定)。
2. 各バーで `Strategy`→`Risk`→`Sizing`→`Ticket`→仮想約定。
3. 約定結果は `PnLTracker` でR単位集計。
4. セッション終了後 `BacktestStats` を更新 (PF, Sharpe, Sortino, MaxDD, Stability)。

### 4.2 Paper/LIVEモード
1. `SessionManager` が `mode=LIVE` で `LiveLoop` を起動。
2. `LiveLoop` は 1) 市場データ更新タスク 2) シグナル処理タスク 3) ガードタスク に分割。
3. シグナル処理タスクは `Workflow Orchestrator` と同様のステップを非同期ジョブで実行。
4. `TicketIssued` イベントに対し、CLI/GUIが `Approve/Reject/Edit` を受け取る。
5. `Approve` で `TicketAction` ログ、`oco_set` 確認リマインダ（2分以内）。
6. `KillSwitchState` が `STOP` の場合、新規シグナルを `drop`。

## 5. エラーハンドリング / リカバリ
- **データ欠損**: `DataQualityGuard` が補完 or `ProviderFallback` を発動。閾値超過で `KillSwitch` に `DATA_STOP`。
- **API失敗**: リトライ戦略 (指数バックオフ)。継続失敗でアラート。
- **スナップショット復旧**: 起動時に最新スナップショットをロードし、`Catch-up` で欠落バーを埋める。
- **ハング監視**: `Heartbeat` メカニズム（30秒）。停止でアラート送信。

## 6. 設定ファイルとバリデーション
- `config/profile.yaml`
```yaml
profile: live
provider: dukascopy
timeframes:
  trigger: 5m
  regime_ref: 1h
risk:
  per_trade: 0.01
  sl_atr_mult: 1.5
  tp_R: 1.8
gates:
  spread_max_pips: 1.5
  news_block_minutes: 15
  drift_max_R: 0.5
  ttl_factor: 3
sprt:
  alpha: 0.05
  beta: 0.10
  uplift: 0.05
strategies:
  - id: ma_rsi
    weight: 0.6
  - id: donchian_breakout
    weight: 0.4
notifications:
  email:
    enabled: true
    to: trader@example.com
```
- バリデーション: `jsonschema` + 独自チェック（丸め、最小ロット）。

## 7. 監査・ログ
- **イベントフォーマット** (`events.py`): dataclass + `asdict()`。
- **ログ粒度**:
  - INFO: バー処理開始/終了、チケット生成
  - WARN: データ補完、Spread上限超
  - ERROR: プロバイダ障害、Kill Switch発火
- **監査追跡**:
  - `TicketAction`: {ticket_id, action(approve/reject/edit), user_note, timestamp}
  - `ConfigChanged`: {diff, user, reason}
  - `KillSwitchChanged`: {from, to, trigger}

## 8. テスト計画概要
- **ユニットテスト**: 各サービスのIFをpytestでテスト。
- **統合テスト**: 5分足CSVを使用したリプレイテスト。resyncシナリオ3件。
- **性能テスト**: 100提案/日の負荷で遅延測定。プロファイラでボトルネック排除。
- **回帰テスト**: `BacktestStats` 比較で ±0.1% の差異を許容範囲とし検証。

## 9. 暗黙的な制約と今後の課題
- 分析モジュールは単一スレッド前提。将来はマルチプロセス化を検討。
- SPRT閾値は設定値依存。OCO未設定抑止(AC-30)はチケットモニタに実装。
- GUI化フェーズでAPI境界 (`/api/v1/signals`, `/ws/signals`) を拡張。

