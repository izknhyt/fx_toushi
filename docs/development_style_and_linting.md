# 開発スタイルとリンティングガイド

本書はFXヒューマン・インザループ投資ツールで採用する言語/フレームワークのスタイル規約とリンター設定を集約する。詳細設計書 (§0.6 Codex開発ハンドオフガイド) から参照され、Codex/開発者は本書に従って実装/レビュー/自動チェックを行う。

## 1. Pythonドメインロジック
- **スタイル基準**: [PEP 8](https://peps.python.org/pep-0008/) と [PEP 484](https://peps.python.org/pep-0484/) の型ヒントを厳守し、公開APIは必ず型注釈を付与する。関数/メソッドにはOne-lineサマリ＋I/O/エラー記述を含むGoogleスタイルDocstringを付ける。
- **アーキテクチャ指針**: サービス層 (`src/<domain>/*.py`) はPure Function志向で副作用をModeContextに閉じ込める。イベント/DTOは`dataclass(slots=True)`または`pydantic.BaseModel`で定義し、`schema_version`/`source`などのメタ情報を持たせる。
- **例外処理**: ドメイン例外は`src/core/exceptions.py`に集約し、CLI層では`typer.Exit(code=...)`へマッピング。再試行/フォールバックは`Tenacity`ではなく専用リトライユーティリティ（M2+予定）導入まで`with backoff_logic(...)`ヘルパを利用する。
- **フォーマッタ**: `black` 23.12+ を使用し、`line-length=100` を上限とする。複数行リテラルは括弧で折り返し、文字列補間は `f"..."` を優先する。
- **静的解析**: `mypy` は `--strict` を基本とし、暫定例外は `mypy.ini` の `[[tool.mypy.overrides]]` にコメント付きで登録する。型未解決を`# type: ignore`で回避する場合は理由をDocstringに記載する。

### 1.1 Ruff設定
`pyproject.toml` に以下を追加する。
```toml
[tool.ruff]
line-length = 100
select = ["E", "F", "I", "N", "UP", "B", "A", "C4", "SIM", "T20"]
ignore = ["E203", "ANN101", "ANN102"]
src = ["src", "tests"]

[tool.ruff.lint.isort]
known-first-party = ["core", "data", "features", "interfaces", "persistence", "reporter", "risk", "strategies", "ticket"]
combine-as-imports = true
```
- `pyproject.toml` が存在しない状態では `poetry init` 後に適用する。`ruff format` は利用せず `black` を唯一のフォーマッタとする。
- `pre-commit` では `ruff check --fix` と `ruff check --unsafe-fixes` を分離し、CI では前者のみを実行して安全な自動修正に限定する。

## 2. Typer + Rich CLI
- **構造**: 各コマンドは `src/interfaces/cli/<topic>.py` に配置し、`app = typer.Typer()` へサブコマンドとして登録する。CLIエントリは同期関数で定義し、非同期処理は`anyio.from_thread.run`経由で呼び出す。
- **スタイル**: コマンド関数名は `<verb>_<noun>`（例: `show_board`）、オプションは長いケバブケース（`--risk-window-min`）。リッチテーブルカラムは`style="cyan"`などのキーワードを定数化して`CLI_THEME`モジュールに保持する。
- **Docstring/ヘルプ**: `typer.Option(help=...)` と `typer.Argument(help=...)` でユーザ向け説明を提供。ヘルプはRunbook参照（`docs/runbooks/*.md`）を含め、CLI内ではURLではなく`docs/...`パスを表示する。
- **リンティング**: CLI層では `ruff` の `T20` (print statement) を必須とし、標準出力は `rich.console.Console` 経由で統制する。副作用テストは`pytest`の`CliRunner`フィクスチャで実施し、Snapshot差分には`pytest-approvaltests`を使用する。

## 3. Pydantic/設定ファイル
- **モデル指針**: `BaseModel` は `model_config = ConfigDict(extra="forbid", populate_by_name=True)` を基本とし、`Field(description=..., examples=[...])`で自己記述性を確保する。
- **バリデーション**: 設定ロードは`src/config/loader.py::load_settings`（予定）を通し、`.yaml`/`.json`は`ruamel.yaml`または`orjson`で読み込む。環境依存値は`env_prefix="FXT_"`の`BaseSettings`派生で上書き可能とする。
- **スキーマ互換**: 将来変更時は`schema_version`をインクリメントし、古いバージョンは`upgrade_<version>()`関数でマイグレーションを定義する。Codexにはマイグレーション手順とテストケースを必ず提示する。

## 4. Pandas/数値計算
- **コーディングスタイル**: `DataFrame` 操作はチェーン不可読性を避け、`assign`/`pipe`を活用して手順を明示する。カラム名はスネークケース、タイムスタンプは`UTC`に正規化する。
- **パフォーマンス**: ループ処理は`np.where`/`pd.Series.where`を優先、シグナル計算は`numba` (M2+) 導入余地を確保するためベクトル化前提のAPIを維持する。
- **テスト**: 数値比較は`pytest.approx`で相対/絶対誤差を指定。大型Fixtureは`data/test_vectors/*.parquet`に格納し、10MBを超える場合は`git-lfs`を利用する。

## 5. テストコード（pytest）
- **配置**: `tests/unit`, `tests/integration`, `tests/approval` の3階層。`conftest.py`にはFixture依存を最小化し、重いI/Oは`scope="module"`でキャッシュする。
- **命名規約**: テスト関数は`test_<function>_<scenario>`。期待例外は`with pytest.raises(ExpectedError):`で明示する。
- **リンター**: `ruff` の `PT`, `PYI` ルールセットを無効化し（テスト特例）、`pytest` プラグイン`pytest-icdiff`で失敗時の差分視認性を高める。

## 6. コマンドサマリ
| 対象 | コマンド | 実行タイミング |
| --- | --- | --- |
| 事前整備 | `poetry run pre-commit install` | 開発環境セットアップ時 |
| フォーマット | `poetry run black src tests` | 変更前後 |
| リンティング | `poetry run ruff check src tests` | PR前 (CIで必須) |
| 型チェック | `poetry run mypy src` | ドメイン層変更時は必須 |
| CLIスナップショット | `poetry run pytest tests/approval -k cli` | CLI差分発生時 |

---
- 例外的なスタイル逸脱は`docs/change_requests/`に設計裁量として記録し、プロダクトオーナーと運用担当の承認を得ること。
- 本書の更新は詳細設計書の改訂履歴 (§0.1) に反映させ、該当コミットに`style-guide`ラベルを付与する。
