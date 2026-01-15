# RUN-FUND-01: Funding CSV日次更新

> **最終更新日**: 2026-01-12
> **最終更新者**: Codex (Doc Maintainer)

## 目的
Paper/Paper+Live運用におけるスワップレートの正確性維持と監査証跡確保。

## トリガー
- 平日 15:00 JST にOps担当へSlackリマインド。
- 祝日前営業日は 12:00 JST に前倒しリマインド。
- `docs/archive/risk_review/20250318_prelaunch.md`は参照のみとし、フォローアップ（自動化・ダブルチェック）は`docs/development_plan.md#update-log-utc`へ記録する。

## ファイル構成
| ファイル/ディレクトリ | 用途 | 更新者 |
| --- | --- | --- |
| `config/swap_rates.csv` | Ops担当が更新するメインCSV | Ops |
| `reports/funding/swap_rates_shadow.csv` | Risk担当の独立入力（双子CSV） | Risk |
| `reports/funding/api_snapshot/<date>.csv` | 自動取得/エクスポートした生データ（任意） | Ops/Risk |
| `reports/validation_log/AC-09_funding_<date>.md` | 日次Evidence・署名 | Ops/Risk/PO |
| `reports/funding/daily_hash_log.md` | ハッシュ/ログ一覧 | Ops |
| `data/state/funding_state.json` | `tradectl funding sync`が書き込む最新状態 | CLI |

## 手順
1. `config/swap_rates.csv`の最新レートをブローカー提供値から取得し、Ops担当がドラフトを更新する。自動取得が可能な場合は下記「自動取得パイロット」を参照して`reports/funding/api_snapshot/<date>.csv`へ保存してから整形する。
2. Risk担当は独立に`reports/funding/swap_rates_shadow.csv`へ同値を入力し、`git diff reports/funding/swap_rates_shadow.csv`で更新範囲を確認する。
3. Ops/Riskは両CSVのソート・小数桁を合わせるため、`python -m tradectl data manual-template --provider funding --symbol ALL --date <YYYY-MM-DD> --timeframe 1d > reports/funding/templates/swap_rates_<date>.csv`（M1ではテンプレCSVをコピーする運用で代替）を起点にフォーマットを揃える。
4. Ops担当が下記コマンドを実行し、CLIプロンプトへOps/Risk/POのイニシャルを入力する。
   ```console
   tradectl funding sync --shadow reports/funding/swap_rates_shadow.csv
   ```
5. CLI出力を保存し、`data/state/funding_state.json`と`reports/validation_log/AC-09_funding_<date>.md`を更新する。併せて`reports/funding/daily_hash_log.md`へ当日のハッシュ値・証跡リンクを追記する（手順は後述）。
6. POが`reports/validation_log/AC-09_funding_<date>.md`の「Daily Sign-off」にイニシャルを記入し、CLIログとハッシュ値は`reports/validation_log/`と`reports/funding/`に保管する。進捗は`docs/development_plan.md#update-log-utc`に記録する。
7. リスクレビューの記録は`docs/archive/risk_review/`を参照しつつ、現行の進捗は`docs/development_plan.md`へ記録する。

### ハッシュ記録 & Evidence
1. メイン/シャドー双方でSHA-256を取得する。
   ```bash
   shasum -a 256 config/swap_rates.csv | cut -d' ' -f1
   shasum -a 256 reports/funding/swap_rates_shadow.csv | cut -d' ' -f1
   ```
2. `reports/funding/daily_hash_log.md`に日付、2つのハッシュ、CLIログパス (`reports/validation_log/AC-09_funding_<date>.md`) を追記する。
3. `reports/validation_log/AC-09_funding_<date>.md`には上記ハッシュと`tradectl funding status --json`の出力抜粋を貼り、Ops/Risk/POの三重署名を取得する。

### 自動取得パイロット（M1.1準備）
- `reports/funding/api_snapshot/<date>.csv` にベンダーAPIやSFTPからダウンロードした原本を保存する。ダウンロード方法はOps日次ノートに記録し、`reports/risk/20250318_prelaunch/R02_oncall_readiness.md`へリンクする。
- `python tools/check_dataset_hash.py --manifest reports/data_manifest.json --strategy m1_baseline_ma_rsi --write reports/risk/20250318_prelaunch/funding_auto_hash.md --append` を実行し、原本と`config/swap_rates.csv`のハッシュ比較ログを残す（本手順は一時的に`m1_baseline_ma_rsi`戦略を流用）。
- 将来的に`tradectl funding sync`へ`--source reports/funding/api_snapshot/<date>.csv`オプションを追加するため、仮に手動でマージした場合でも差分を`reports/funding/api_snapshot/README.md`へ記録する。

## チェックポイント
- `funding_state.json.last_synced_at`が24時間以内か。
- `csv_sha256`と`shadow_sha256`が一致しているか。
- `reports/validation_log/AC-09_funding_<date>.md`にOps/Risk/POの三重署名が揃っているか。

## 付録
- 参考コマンド: `tradectl funding status --json`。
- 参照セクション: §3.12.1, §5.15.1。
