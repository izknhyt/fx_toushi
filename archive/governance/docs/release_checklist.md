# Release Checklist (Personal Use)

個人利用の shadow / live candidate 出荷前チェック。  
多人数承認や重い監査パックは前提にしない。必要なのは「壊れていないこと」「再現できること」「すぐ止められること」。

このチェックリストは `tradectl release prepare --version <tag>` から参照される前提で維持する。

## 1. Architecture And Scope
- [ ] 変更内容が [FX Portfolio Operating System](architecture/fx_portfolio_operating_system.md) と矛盾していない
- [ ] `docs/development_plan.md` に対象タスクの結果、証跡、残課題が反映されている
- [ ] 今回の変更が `standalone` 改善なのか `portfolio` 改善なのかを明確に言える

## 2. Tests And Reproducibility
- [ ] 実行した `pytest` / backtest / shadow コマンドを記録した
- [ ] 重要な結果の evidence path が残っている
- [ ] seed, cost assumptions, manifest/profile が再現可能な形で固定されている

## 3. Data And Config
- [ ] 変更した `config/` は必要な validation を通した
- [ ] 利用するデータの最終 timestamp と source が把握できている
- [ ] `snapshots/latest/` または同等の復旧起点が存在する

## 4. Runtime Safety
- [ ] `tradectl status --json` か同等の確認で kill switch / spread / provider 状態に致命傷がない
- [ ] stop / rollback 手順を 1-2 分で説明できる
- [ ] shadow から上げる場合、shadow 乖離が許容内である

## 5. Operator Sign-Off
- [ ] Operator confirmation: ____________________ Date: __________
- [ ] Rollback note/path: _______________________________________

## Notes
- 旧来の Product Owner / Ops Manager / Risk Officer 承認欄は personal-use default から外す。
- 監査用の補助資料が必要なら任意で追加してよいが、通常リリースの必須条件にはしない。
