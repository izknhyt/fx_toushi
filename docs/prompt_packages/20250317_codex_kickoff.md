# Prompt Package: 20250317_codex_kickoff

## メタデータ
- Packet/Issue: PKG-CODEX-KICKOFF-20250317
- 作成日: 2025-03-17
- 作成者: Codex Liaison
- 参照セクション: 詳細設計 §0.6.8〜§0.6.9, §3.1, §79.1
- 関連Runbook: RUN-DATA-05, RUN-RISK-01, RUN-HITL-01, OPS-READINESS-01
- エビデンス格納先: `reports/validation_log/CHK-0.6.9_env_setup_20250317.md`, `reports/validation_log/CHK-0.6.9_mode_context_20250317.md`, `reports/validation_log/CHK-0.6.9_risk_schema_20250317.md`, `reports/validation_log/AC-09_funding_20250317.md`

## 1. 依頼サマリ
- 背景/KPI: Codex実装開始前に§0.6.8/§0.6.9の前提条件（CLI起動・スモークテスト・Broker契約検証）を満たし、Runbook/Validation Data Playbookへ証跡をリンクする。
- 期待シナリオ: `poetry install --no-root` → `python -m tradectl --help` → `pytest -k smoke` → `pytest tests/unit/test_broker_adapter_contracts.py` が再現され、`docs/prompt_packages` と Ops Agenda から参照できる。
- 受入条件: エビデンスMarkdown作成、詳細設計 §0.6.8 #4 を ✅ 状態に更新、Issue/PR テンプレートに Packet/CHK ID を引用可能にする。

## 2. 提供プロンプト
```
目的:
  - CHK-0.6.9-1/2 の環境コマンドを再実行し、ログを Validation Data Playbook パスへ貼り付ける。
  - Broker Adapter Contract テスト（詳細設計 §79.1, Task #4）を回し、証跡を同ファイルに追記。
  - `python -m tradectl --help` が成功するようモジュールエントリポイントを提供する。
  - Prompt Package ドキュメントを作成し、Ops Agenda から参照できるようにする。

実装メモ:
  - 追加した `tradectl` モジュールは Typer アプリケーション (`src.interfaces.cli.create_cli_app`) を再利用する。
  - `reports/validation_log/CHK-0.6.9_env_setup_20250317.md` へ各コマンド結果・タイムスタンプを追記する。
  - 詳細設計 §0.6.8 の是正表で Task #4 を `✅ 2025-03-17 / BROKER-CONTRACT-TEST` と更新する。
  - `docs/prompt_packages/20250317_codex_kickoff.md` に本プロンプトとコードスニペットを保存する。

受入のための確認:
  - `poetry run python -m tradectl --help` exit code 0。
  - `poetry run pytest -k smoke` 成功、Spread Monitor スキップ理由がログ化されている。
  - `poetry run pytest tests/unit/test_broker_adapter_contracts.py` 成功。
  - すべての変更が `git status` で追跡され、docs/validation_log へリンク済み。
```

## 3. 添付コードスニペット
```python
# tradectl/__init__.py
from src.interfaces.cli import create_cli_app

_APP = create_cli_app()


def main() -> None:
    """Delegate execution to the Typer application used by ``tradectl``."""

    _APP()
```

## 4. レビューとフィードバック
- 良かった点:
  - [x] must — CLI entrypointを`python -m`互換にできた
  - [x] should — エビデンスログとPacketが即リンク可能
  - [ ] nice
- 改善要望:
  - nice: ModeContext Startup Walkthrough の実機ログは後続タスクで埋める
- 想定外差分: なし

## 5. 次回アクション
- Follow-up Packet/Issue: **完了** — `ModeContext Startup Validation (CHK-0.6.9-6/7)` 実施済み（Evidence: `reports/validation_log/CHK-0.6.9_mode_context_20250317.md`, Ops Agenda `docs/runbooks/daily_agenda/2025-03-17.md`）
- Runbook更新の有無: なし（テンプレ参照のみ）
- 更新者: Ops Manager（2025-03-17）

## 6. 更新履歴
| 日付 | 更新者 | 内容 |
| --- | --- | --- |
| 2025-03-17 | Codex Liaison | 初版作成 |
