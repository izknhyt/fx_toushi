# CI Artifacts

`python_smoke.xml` はGitHub Actions `python_smoke` ワークフローが生成するJUnit XMLです。ローカル検証時は以下で生成できます。

```bash
poetry run pytest -k "smoke" --maxfail=1 --disable-warnings -q --junitxml=reports/ci/python_smoke.xml
```

Codex開始チェックリスト（§0.6.9）では直近実行ログを添付することを必須とします。

