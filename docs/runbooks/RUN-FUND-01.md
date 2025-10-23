# RUN-FUND-01: Funding CSV日次更新

## 目的
Paper/Paper+Live運用におけるスワップレートの正確性維持と監査証跡確保。

## トリガー
- 平日 15:00 JST にOps担当へSlackリマインド。
- 祝日前営業日は 12:00 JST に前倒しリマインド。

## 手順
1. `config/swap_rates.csv`の最新レートをブローカー提供値から取得し、Ops担当がドラフトを更新する。
2. Risk担当は独立に`reports/funding/swap_rates_shadow.csv`へ同値を入力し、差分が無いことを目視確認する。
3. Ops担当が下記コマンドを実行し、CLIプロンプトへOps/Risk/POのイニシャルを入力する。
   ```console
   tradectl funding sync --shadow reports/funding/swap_rates_shadow.csv
   ```
4. CLI出力を保存し、`funding_state.json`と`reports/validation_log/AC-09_funding_<date>.md`を更新する。
5. POが`reports/validation_log/AC-09_funding_<date>.md`の「Daily Sign-off」にイニシャルを記入し、`docs/implementation_packets/<packet>/evidence/`へCLIログとハッシュ値を保管する。

## チェックポイント
- `funding_state.json.last_synced_at`が24時間以内か。
- `csv_sha256`と`shadow_sha256`が一致しているか。
- `reports/validation_log/AC-09_funding_<date>.md`にOps/Risk/POの三重署名が揃っているか。

## 付録
- 参考コマンド: `tradectl funding status --json`。
- 参照セクション: §3.12.1, §5.15.1。
