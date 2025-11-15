# M1 Test & CLI Gap Analysis (2025-03-13)

本ファイルは詳細設計書§9, §22〜§31, §87〜§92で定義されたテストIDおよびCLIコマンドの実装状況を整理したギャップ表です。

「実装状況」列は`実装済み`/`未実装 (M1整備予定)`/`未実装 (M1.1+)`のいずれかで表記し、Runbookと証跡ファイルの紐づけ状況を記載しています。

M1整備対象は即時着手候補として`未実装 (M1整備予定)`で明示し、それ以外はM1.1以降のバックログとして`未実装 (M1.1+)`としています。


## §9 テスト計画

* 依頼元Runbook既定: -


### テストID

| バックログID | テストID | 実装状況 | 依頼元Runbook | 証跡ファイル/備考 |

| --- | --- | --- | --- | --- |

| BL-0001 | FUT-SCORE-01 | 未実装 (M1.1+) | - | - |

| BL-0002 | FUT-SCORE-02 | 未実装 (M1.1+) | - | - |

| BL-0003 | FUT-SPRT-01 | 未実装 (M1.1+) | - | - |

| BL-0004 | IT-COR-01 | 未実装 (M1.1+) | - | - |

| BL-0005 | IT-FUND-01 | 未実装 (M1.1+) | - | - |

| BL-0006 | IT-GAME-01 | 未実装 (M1整備予定) | - | - |

| BL-0007 | IT-KILL-01 | 未実装 (M1.1+) | - | - |

| BL-0008 | IT-PIPE-01 | 未実装 (M1.1+) | - | - |

| BL-0009 | IT-RESYNC-01 | 未実装 (M1.1+) | - | - |

| BL-0010 | IT-RISK-02 | 未実装 (M1.1+) | - | - |

| BL-0011 | IT-RL-01 | 未実装 (M1.1+) | - | - |

| BL-0012 | IT-SPREAD-01 | 未実装 (M1.1+) | - | - |

| BL-0013 | MVP-FR-01 | 未実装 (M1.1+) | - | - |

| BL-0014 | PT-BT-01 | 未実装 (M1.1+) | - | - |

| BL-0015 | PT-CLI-01 | 未実装 (M1整備予定) | - | - |

| BL-0016 | UT-CFG-01 | 未実装 (M1.1+) | - | - |

| BL-0017 | UT-EXEC-01 | 未実装 (M1.1+) | - | - |

| BL-0018 | UT-FEAT-01 | 未実装 (M1.1+) | - | - |

| BL-0019 | UT-GAME-01 | 未実装 (M1整備予定) | - | - |

| BL-0020 | UT-ING-01 | 未実装 (M1.1+) | - | - |

| BL-0021 | UT-RISK-01 | 未実装 (M1.1+) | - | - |

| BL-0022 | UT-RL-01 | 未実装 (M1.1+) | - | - |

| BL-0023 | UT-SIZE-01 | 未実装 (M1.1+) | - | - |

| BL-0024 | UT-STR-01 | 未実装 (M1.1+) | - | - |

| BL-0025 | UT-TKT-01 | 未実装 (M1.1+) | - | - |


### CLIコマンド

| バックログID | コマンド | 実装状況 | 依頼元Runbook | 証跡ファイル/備考 |

| --- | --- | --- | --- | --- |

| BL-0026 | `make qa-report` | 未実装 (M1.1+) | - | - |

| BL-0027 | `make qa-report --ci` | 未実装 (M1.1+) | - | - |

| BL-0028 | `pytest -m "not m2plus"` | 未実装 (M1.1+) | - | - |

| BL-0029 | `pytest tests/integration/test_pipeline_end_to_end.py` | 未実装 (M1.1+) | - | - |

| BL-0030 | `pytest tests/unit/test_rate_limit_guard.py` | 未実装 (M1.1+) | - | - |

| BL-0031 | `pytest-approvaltests` | 未実装 (M1.1+) | - | - |

| BL-0032 | `tools/make_fixture.py` | 未実装 (M1.1+) | - | - |

| BL-0033 | `tradectl backtest run --strategy m1_baseline_ma_rsi --profile paper-m1-baseline --from 2021-01-01 --to 2023-06-30 --out reports/backtest/m1_baseline/is` | 未実装 (M1.1+) | - | - |

| BL-0034 | `tradectl backtest run --strategy m1_baseline_ma_rsi --profile paper-m1-baseline --from 2023-07-01 --to 2024-12-31 --out reports/backtest/m1_baseline/oos` | 未実装 (M1.1+) | - | - |

| BL-0035 | `tradectl backtest run ... --what-if spread=1.5,slip=1.5` | 未実装 (M1.1+) | - | - |

| BL-0036 | `tradectl board` | 未実装 (M1整備予定) | - | - |

| BL-0037 | `tradectl data rate-limit stage` | 未実装 (M1.1+) | - | - |

| BL-0038 | `tradectl diagnostics risk --strategy m1_baseline_ma_rsi --from 2023-07-01 --to 2024-12-31 --mode backtest` | 未実装 (M1.1+) | - | - |

| BL-0039 | `tradectl game run --seed 123` | 未実装 (M1整備予定) | - | - |

| BL-0040 | `tradectl metrics latency --mode paper --from 2024-01-01 --to 2024-12-31` | 未実装 (M1.1+) | - | - |

| BL-0041 | `tradectl preflight` | 未実装 (M1.1+) | - | - |

| BL-0042 | `tradectl report weekly --since 7d` | 未実装 (M1.1+) | - | - |

| BL-0043 | `tradectl scenario run --id AC-45 --profile paper-m1-core` | 未実装 (M1.1+) | - | - |


## §22 Opsシミュレーションゲーム

* 依頼元Runbook既定: RUN-OPS-02 (ゲーム演習)


### CLIコマンド

| バックログID | コマンド | 実装状況 | 依頼元Runbook | 証跡ファイル/備考 |

| --- | --- | --- | --- | --- |

| BL-0044 | `make game-audit` | 未実装 (M1.1+) | RUN-OPS-02 (ゲーム演習) | - |

| BL-0045 | `make game-smoke` | 未実装 (M1整備予定) | RUN-OPS-02 (ゲーム演習) | - |

| BL-0046 | `pytest -k game` | 未実装 (M1整備予定) | RUN-OPS-02 (ゲーム演習) | - |

| BL-0047 | `pytest-approvaltests` | 未実装 (M1.1+) | RUN-OPS-02 (ゲーム演習) | - |

| BL-0048 | `tradectl game run` | 未実装 (M1整備予定) | RUN-OPS-02 (ゲーム演習) | - |

| BL-0049 | `tradectl game run --seed 123 --days 3 --dry-run` | 未実装 (M1整備予定) | RUN-OPS-02 (ゲーム演習) | - |

| BL-0050 | `tradectl game run --seed 42 --days 3 --dry-run` | 未実装 (M1.1+) | RUN-OPS-02 (ゲーム演習) | - |

| BL-0051 | `tradectl review degraded` | 未実装 (M1.1+) | RUN-OPS-02 (ゲーム演習) | - |


## §23 Evidence Graph

* 依頼元Runbook既定: RUN-GOV-01 (Evidenceリンク整備)


### テストID

| バックログID | テストID | 実装状況 | 依頼元Runbook | 証跡ファイル/備考 |

| --- | --- | --- | --- | --- |

| BL-0052 | IT-EVG-01 | 未実装 (M1.1+) | RUN-GOV-01 (Evidenceリンク整備) | - |

| BL-0053 | IT-EVG-02 | 未実装 (M1.1+) | RUN-GOV-01 (Evidenceリンク整備) | - |

| BL-0054 | IT-EVG-03 | 未実装 (M1.1+) | RUN-GOV-01 (Evidenceリンク整備) | - |

| BL-0055 | IT-EVG-04 | 未実装 (M1.1+) | RUN-GOV-01 (Evidenceリンク整備) | - |

| BL-0056 | UT-EVG-01 | 未実装 (M1.1+) | RUN-GOV-01 (Evidenceリンク整備) | - |

| BL-0057 | UT-EVG-02 | 未実装 (M1.1+) | RUN-GOV-01 (Evidenceリンク整備) | - |

| BL-0058 | UT-EVG-03 | 未実装 (M1.1+) | RUN-GOV-01 (Evidenceリンク整備) | - |

| BL-0059 | UT-EVG-04 | 未実装 (M1.1+) | RUN-GOV-01 (Evidenceリンク整備) | - |


### CLIコマンド

| バックログID | コマンド | 実装状況 | 依頼元Runbook | 証跡ファイル/備考 |

| --- | --- | --- | --- | --- |

| BL-0060 | `make ci-lite` | 未実装 (M1.1+) | RUN-GOV-01 (Evidenceリンク整備) | - |

| BL-0061 | `make evidence-audit` | 未実装 (M1.1+) | RUN-GOV-01 (Evidenceリンク整備) | - |

| BL-0062 | `pytest -k evidence_graph` | 未実装 (M1.1+) | RUN-GOV-01 (Evidenceリンク整備) | - |

| BL-0063 | `tradectl degradation report` | 未実装 (M1.1+) | RUN-GOV-01 (Evidenceリンク整備) | - |

| BL-0064 | `tradectl evidence` | 未実装 (M1.1+) | RUN-GOV-01 (Evidenceリンク整備) | - |

| BL-0065 | `tradectl evidence ...` | 未実装 (M1.1+) | RUN-GOV-01 (Evidenceリンク整備) | - |

| BL-0066 | `tradectl evidence audit` | 未実装 (M1.1+) | RUN-GOV-01 (Evidenceリンク整備) | - |

| BL-0067 | `tradectl evidence export` | 未実装 (M1.1+) | RUN-GOV-01 (Evidenceリンク整備) | - |

| BL-0068 | `tradectl evidence graph build` | 未実装 (M1.1+) | RUN-GOV-01 (Evidenceリンク整備) | - |

| BL-0069 | `tradectl evidence graph build --window <...> --dry-run` | 未実装 (M1.1+) | RUN-GOV-01 (Evidenceリンク整備) | - |

| BL-0070 | `tradectl evidence inspect` | 未実装 (M1.1+) | RUN-GOV-01 (Evidenceリンク整備) | - |

| BL-0071 | `tradectl evidence link ...` | 未実装 (M1.1+) | RUN-GOV-01 (Evidenceリンク整備) | - |

| BL-0072 | `tradectl evidence query` | 未実装 (M1.1+) | RUN-GOV-01 (Evidenceリンク整備) | - |

| BL-0073 | `tradectl evidence query --format graphviz --open` | 未実装 (M1.1+) | RUN-GOV-01 (Evidenceリンク整備) | - |


## §24 AD Analytics & Recovery

* 依頼元Runbook既定: RUN-DATA-05 / RUN-RISK-01 (AD対応)


### テストID

| バックログID | テストID | 実装状況 | 依頼元Runbook | 証跡ファイル/備考 |

| --- | --- | --- | --- | --- |

| BL-0074 | IT-DEG-01 | 未実装 (M1.1+) | RUN-DATA-05 / RUN-RISK-01 (AD対応) | - |

| BL-0075 | IT-DEG-02 | 未実装 (M1.1+) | RUN-DATA-05 / RUN-RISK-01 (AD対応) | - |

| BL-0076 | IT-DEG-03 | 未実装 (M1.1+) | RUN-DATA-05 / RUN-RISK-01 (AD対応) | - |

| BL-0077 | OPS-DEG-01 | 未実装 (M1.1+) | RUN-DATA-05 / RUN-RISK-01 (AD対応) | - |

| BL-0078 | OPS-RL-03 | 未実装 (M1.1+) | RUN-DATA-05 / RUN-RISK-01 (AD対応) | - |

| BL-0079 | UT-DEG-01 | 未実装 (M1.1+) | RUN-DATA-05 / RUN-RISK-01 (AD対応) | - |

| BL-0080 | UT-DEG-02 | 未実装 (M1.1+) | RUN-DATA-05 / RUN-RISK-01 (AD対応) | - |

| BL-0081 | UT-DEG-03 | 未実装 (M1.1+) | RUN-DATA-05 / RUN-RISK-01 (AD対応) | - |


### CLIコマンド

| バックログID | コマンド | 実装状況 | 依頼元Runbook | 証跡ファイル/備考 |

| --- | --- | --- | --- | --- |

| BL-0082 | `make ci-lite` | 未実装 (M1.1+) | RUN-DATA-05 / RUN-RISK-01 (AD対応) | - |

| BL-0083 | `pytest -k degradation` | 未実装 (M1.1+) | RUN-DATA-05 / RUN-RISK-01 (AD対応) | - |

| BL-0084 | `tradectl degradation` | 未実装 (M1.1+) | RUN-DATA-05 / RUN-RISK-01 (AD対応) | - |

| BL-0085 | `tradectl degradation ...` | 未実装 (M1.1+) | RUN-DATA-05 / RUN-RISK-01 (AD対応) | - |

| BL-0086 | `tradectl degradation episode list` | 未実装 (M1.1+) | RUN-DATA-05 / RUN-RISK-01 (AD対応) | - |

| BL-0087 | `tradectl degradation episode show <id>` | 未実装 (M1.1+) | RUN-DATA-05 / RUN-RISK-01 (AD対応) | - |

| BL-0088 | `tradectl degradation recommend` | 未実装 (M1.1+) | RUN-DATA-05 / RUN-RISK-01 (AD対応) | - |

| BL-0089 | `tradectl degradation recommend --severity high --push-to-bundle` | 未実装 (M1.1+) | RUN-DATA-05 / RUN-RISK-01 (AD対応) | - |

| BL-0090 | `tradectl degradation report` | 未実装 (M1.1+) | RUN-DATA-05 / RUN-RISK-01 (AD対応) | - |

| BL-0091 | `tradectl degradation report --window 1d --format json --push-to-bundle --dry-run` | 未実装 (M1.1+) | RUN-DATA-05 / RUN-RISK-01 (AD対応) | - |

| BL-0092 | `tradectl degradation report --window 1d --include-evidence` | 未実装 (M1.1+) | RUN-DATA-05 / RUN-RISK-01 (AD対応) | - |

| BL-0093 | `tradectl degradation report --window 7d` | 未実装 (M1.1+) | RUN-DATA-05 / RUN-RISK-01 (AD対応) | - |

| BL-0094 | `tradectl degradation sync-evidence` | 未実装 (M1.1+) | RUN-DATA-05 / RUN-RISK-01 (AD対応) | - |

| BL-0095 | `tradectl review digest` | 未実装 (M1.1+) | RUN-DATA-05 / RUN-RISK-01 (AD対応) | - |

| BL-0096 | `tradectl scenario run --id OPS-DEG-01 --dry-run` | 未実装 (M1.1+) | RUN-DATA-05 / RUN-RISK-01 (AD対応) | - |


## §25 Delivery Control Tower

* 依頼元Runbook既定: RUN-OPS-02


### テストID

| バックログID | テストID | 実装状況 | 依頼元Runbook | 証跡ファイル/備考 |

| --- | --- | --- | --- | --- |

| BL-0097 | IT-DEL-01 | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0098 | IT-DEL-02 | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0099 | UT-DEL-01 | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0100 | UT-DEL-02 | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0101 | UT-DEL-03 | 未実装 (M1.1+) | RUN-OPS-02 | - |


### CLIコマンド

| バックログID | コマンド | 実装状況 | 依頼元Runbook | 証跡ファイル/備考 |

| --- | --- | --- | --- | --- |

| BL-0102 | `make ci-lite` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0103 | `pytest -k delivery` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0104 | `tradectl delivery ...` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0105 | `tradectl delivery alerts` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0106 | `tradectl delivery export` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0107 | `tradectl delivery forecast` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0108 | `tradectl delivery forecast --include-degradation --window 3d` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0109 | `tradectl delivery status` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0110 | `tradectl delivery status --include-alerts` | 未実装 (M1.1+) | RUN-OPS-02 | - |


## §26 フィードバック循環

* 依頼元Runbook既定: RUN-OPS-02


### テストID

| バックログID | テストID | 実装状況 | 依頼元Runbook | 証跡ファイル/備考 |

| --- | --- | --- | --- | --- |

| BL-0111 | IT-FB-01 | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0112 | IT-FB-02 | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0113 | IT-FB-03 | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0114 | UT-FB-01 | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0115 | UT-FB-02 | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0116 | UT-FB-03 | 未実装 (M1.1+) | RUN-OPS-02 | - |


### CLIコマンド

| バックログID | コマンド | 実装状況 | 依頼元Runbook | 証跡ファイル/備考 |

| --- | --- | --- | --- | --- |

| BL-0117 | `pytest --snapshot-update --maxfail=1` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0118 | `pytest -k feedback` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0119 | `tradectl feedback ...` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0120 | `tradectl feedback ack` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0121 | `tradectl feedback export` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0122 | `tradectl feedback export --include-degradation` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0123 | `tradectl feedback route` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0124 | `tradectl feedback route --destination ux` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0125 | `tradectl feedback summarize` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0126 | `tradectl feedback summarize --window 1d --strategy core_ma_rsi` | 未実装 (M1.1+) | RUN-OPS-02 | - |


## §27 流動性・スリッページ診断

* 依頼元Runbook既定: RUN-SPREAD-03


### テストID

| バックログID | テストID | 実装状況 | 依頼元Runbook | 証跡ファイル/備考 |

| --- | --- | --- | --- | --- |

| BL-0127 | IT-SLP-01 | 未実装 (M1.1+) | RUN-SPREAD-03 | - |

| BL-0128 | IT-SLP-02 | 未実装 (M1.1+) | RUN-SPREAD-03 | - |

| BL-0129 | IT-SLP-03 | 未実装 (M1.1+) | RUN-SPREAD-03 | - |

| BL-0130 | IT-SLP-04 | 未実装 (M1.1+) | RUN-SPREAD-03 | - |

| BL-0131 | OPS-DEG-01 | 未実装 (M1.1+) | RUN-SPREAD-03 | - |

| BL-0132 | PT-SLP-01 | 未実装 (M1.1+) | RUN-SPREAD-03 | - |

| BL-0133 | UT-SLP-01 | 未実装 (M1.1+) | RUN-SPREAD-03 | - |

| BL-0134 | UT-SLP-02 | 未実装 (M1.1+) | RUN-SPREAD-03 | - |

| BL-0135 | UT-SLP-03 | 未実装 (M1.1+) | RUN-SPREAD-03 | - |


### CLIコマンド

| バックログID | コマンド | 実装状況 | 依頼元Runbook | 証跡ファイル/備考 |

| --- | --- | --- | --- | --- |

| BL-0136 | `make ci-lite` | 未実装 (M1.1+) | RUN-SPREAD-03 | - |

| BL-0137 | `pytest -k "slippage or liquidity"` | 未実装 (M1.1+) | RUN-SPREAD-03 | - |

| BL-0138 | `tradectl account import` | 未実装 (M1.1+) | RUN-SPREAD-03 | - |

| BL-0139 | `tradectl liquidity` | 未実装 (M1.1+) | RUN-SPREAD-03 | - |

| BL-0140 | `tradectl liquidity ...` | 未実装 (M1.1+) | RUN-SPREAD-03 | - |

| BL-0141 | `tradectl liquidity analyze` | 未実装 (M1.1+) | RUN-SPREAD-03 | - |

| BL-0142 | `tradectl liquidity analyze --format json --push-evidence` | 未実装 (M1.1+) | RUN-SPREAD-03 | - |

| BL-0143 | `tradectl liquidity analyze --window 14d` | 未実装 (M1.1+) | RUN-SPREAD-03 | - |

| BL-0144 | `tradectl liquidity analyze --window 14d --format table` | 未実装 (M1.1+) | RUN-SPREAD-03 | - |

| BL-0145 | `tradectl liquidity analyze --window 7d` | 未実装 (M1.1+) | RUN-SPREAD-03 | - |

| BL-0146 | `tradectl liquidity analyze --window 7d --format markdown --include-news` | 未実装 (M1.1+) | RUN-SPREAD-03 | - |

| BL-0147 | `tradectl liquidity export-samples` | 未実装 (M1.1+) | RUN-SPREAD-03 | - |

| BL-0148 | `tradectl liquidity replay` | 未実装 (M1.1+) | RUN-SPREAD-03 | - |

| BL-0149 | `tradectl liquidity suggest-adjustment` | 未実装 (M1.1+) | RUN-SPREAD-03 | - |

| BL-0150 | `tradectl scenario run OPS-DEG-01 --step-to slippage_review` | 未実装 (M1.1+) | RUN-SPREAD-03 | - |


## §28 緊急対応オーケストレータ

* 依頼元Runbook既定: RUN-OPS-02


### テストID

| バックログID | テストID | 実装状況 | 依頼元Runbook | 証跡ファイル/備考 |

| --- | --- | --- | --- | --- |

| BL-0151 | IT-EMG-01 | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0152 | IT-EMG-02 | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0153 | IT-EMG-03 | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0154 | PT-EMG-01 | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0155 | UT-EMG-01 | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0156 | UT-EMG-02 | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0157 | UT-EMG-03 | 未実装 (M1.1+) | RUN-OPS-02 | - |


### CLIコマンド

| バックログID | コマンド | 実装状況 | 依頼元Runbook | 証跡ファイル/備考 |

| --- | --- | --- | --- | --- |

| BL-0158 | `make ci-lite` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0159 | `pytest -k "emergency"` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0160 | `src/emergency/
  orchestrator.py        # EmergencyOrchestrator (Facade)
  detectors.py           # DataStop/FillDrift/ProviderOutage検知器
  actions.py             # ReduceOnlyProposal, AlertDispatch, ManualCsvDrill 等
  registry.py            # Feature Flag判定とDIハンドラ
  plans.py               # EmergencyPlanテンプレ/Runbookマッピング
  cli.py                 # tradectl emergency ...
  persistence.py         # IncidentLedger JSONL` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0161 | `tradectl board --guarded` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0162 | `tradectl broker report` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0163 | `tradectl broker report --status down` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0164 | `tradectl emergency ack <id> --board-mode guarded` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0165 | `tradectl emergency ack <incident_id>` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0166 | `tradectl emergency execute <incident_id> <action_id>` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0167 | `tradectl emergency export <incident_id>` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0168 | `tradectl emergency list` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0169 | `tradectl emergency show <incident_id>` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0170 | `tradectl emergency simulate` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0171 | `tradectl emergency simulate <scenario_id>` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0172 | `tradectl emergency simulate EMG-DATA-01 --with-scenario-runner` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0173 | `tradectl liquidity analyze` | 未実装 (M1.1+) | RUN-OPS-02 | - |


## §29 運用健全性ダッシュボード

* 依頼元Runbook既定: RUN-OPS-02


### テストID

| バックログID | テストID | 実装状況 | 依頼元Runbook | 証跡ファイル/備考 |

| --- | --- | --- | --- | --- |

| BL-0174 | IT-DASH-01 | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0175 | IT-DASH-02 | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0176 | IT-DASH-03 | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0177 | OPS-BENCH-01 | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0178 | PT-DASH-01 | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0179 | UT-DASH-01 | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0180 | UT-DASH-02 | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0181 | UT-DASH-03 | 未実装 (M1.1+) | RUN-OPS-02 | - |


### CLIコマンド

| バックログID | コマンド | 実装状況 | 依頼元Runbook | 証跡ファイル/備考 |

| --- | --- | --- | --- | --- |

| BL-0182 | `make ci-lite` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0183 | `pytest -k "ops_dashboard"` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0184 | `src/ops_dashboard/
  service.py            # OpsDashboardService
  widgets.py            # WidgetBaseと具体ウィジェット実装
  layout.py             # Widget配置ロジック/レイアウトテンプレ
  telemetry.py          # メトリクス/イベントフェッチャ
  cli.py                # tradectl ops dashboard
  renderer.py           # Rich Table/Panel生成` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0185 | `tradectl benchmark compare` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0186 | `tradectl board --guarded` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0187 | `tradectl degradation summarize` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0188 | `tradectl feedback ack <id>` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0189 | `tradectl ops dashboard` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0190 | `tradectl ops dashboard --format markdown` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0191 | `tradectl ops dashboard --format table` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0192 | `tradectl ops dashboard --watch` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0193 | `tradectl ops dashboard diff` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0194 | `tradectl ops dashboard snapshot` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0195 | `tradectl ops dashboard snapshot --summary` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0196 | `tradectl ops dashboard widget-info <widget_id>` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0197 | `tradectl runbook lint` | 未実装 (M1.1+) | RUN-OPS-02 | - |


## §30 Release Readiness

* 依頼元Runbook既定: RUN-OPS-02


### テストID

| バックログID | テストID | 実装状況 | 依頼元Runbook | 証跡ファイル/備考 |

| --- | --- | --- | --- | --- |

| BL-0198 | IT-REL-01 | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0199 | IT-REL-02 | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0200 | IT-REL-03 | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0201 | UT-REL-01 | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0202 | UT-REL-02 | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0203 | UT-REL-03 | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0204 | UT-REL-04 | 未実装 (M1.1+) | RUN-OPS-02 | - |


### CLIコマンド

| バックログID | コマンド | 実装状況 | 依頼元Runbook | 証跡ファイル/備考 |

| --- | --- | --- | --- | --- |

| BL-0205 | `make ci-lite` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0206 | `pytest -k release_readiness` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0207 | `tradectl release ...` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0208 | `tradectl release blockers` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0209 | `tradectl release blockers --export` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0210 | `tradectl release blockers --severity fail` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0211 | `tradectl release checklist` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0212 | `tradectl release checklist --profile live-core` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0213 | `tradectl release export` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0214 | `tradectl release export --scope live --include-ci --out reports/release/readiness/live_<date>.md` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0215 | `tradectl release readiness` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0216 | `tradectl release readiness --dry-run` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0217 | `tradectl release readiness --scope live --window 7d` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0218 | `tradectl release readiness --scope paper --format markdown --include-evidence` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0219 | `tradectl release simulate` | 未実装 (M1.1+) | RUN-OPS-02 | - |


## §87 強化ブロック整合ハブ

* 依頼元Runbook既定: CHK-0.6.9


### CLIコマンド

| バックログID | コマンド | 実装状況 | 依頼元Runbook | 証跡ファイル/備考 |

| --- | --- | --- | --- | --- |

| BL-0220 | `make sla-report` | 未実装 (M1.1+) | CHK-0.6.9 | - |

| BL-0221 | `pytest` | 未実装 (M1.1+) | CHK-0.6.9 | - |

| BL-0222 | `pytest --snapshot-update` | 未実装 (M1.1+) | CHK-0.6.9 | - |

| BL-0223 | `pytest -k board_renderer` | 未実装 (M1.1+) | CHK-0.6.9 | - |

| BL-0224 | `pytest -k feature_pipeline` | 未実装 (M1.1+) | CHK-0.6.9 | - |

| BL-0225 | `pytest -k health_state` | 未実装 (M1.1+) | CHK-0.6.9 | - |

| BL-0226 | `pytest -k risk_manager` | 未実装 (M1.1+) | CHK-0.6.9 | - |

| BL-0227 | `pytest -k strategy_determinism` | 未実装 (M1.1+) | CHK-0.6.9 | - |

| BL-0228 | `pytest -k ticket_builder` | 未実装 (M1.1+) | CHK-0.6.9 | - |

| BL-0229 | `tradectl backtest run` | 未実装 (M1.1+) | CHK-0.6.9 | - |

| BL-0230 | `tradectl board --guarded` | 未実装 (M1.1+) | CHK-0.6.9 | - |

| BL-0231 | `tradectl correlation snapshot` | 未実装 (M1.1+) | CHK-0.6.9 | - |

| BL-0232 | `tradectl data failover --mode manual` | 未実装 (M1.1+) | CHK-0.6.9 | - |

| BL-0233 | `tradectl data health` | 未実装 (M1.1+) | CHK-0.6.9 | - |

| BL-0234 | `tradectl data rate-limit stage inspect|set` | 未実装 (M1.1+) | CHK-0.6.9 | - |

| BL-0235 | `tradectl diagnostics risk` | 未実装 (M1.1+) | CHK-0.6.9 | - |

| BL-0236 | `tradectl kill-switch engage|release` | 未実装 (M1.1+) | CHK-0.6.9 | - |

| BL-0237 | `tradectl metrics latency --mode paper` | 未実装 (M1.1+) | CHK-0.6.9 | - |

| BL-0238 | `tradectl report ack` | 未実装 (M1.1+) | CHK-0.6.9 | - |

| BL-0239 | `tradectl report status` | 未実装 (M1.1+) | CHK-0.6.9 | - |

| BL-0240 | `tradectl risk summary` | 未実装 (M1.1+) | CHK-0.6.9 | - |

| BL-0241 | `tradectl status --history kill-switch` | 未実装 (M1.1+) | CHK-0.6.9 | - |

| BL-0242 | `tradectl ticket queue --summary` | 未実装 (M1.1+) | CHK-0.6.9 | - |

| BL-0243 | `tradectl ticket simulate|approve|inspect|checklist` | 未実装 (M1.1+) | CHK-0.6.9 | - |


## §88 EP-01 DataLag Mitigation

* 依頼元Runbook既定: RUN-DATA-05


### テストID

| バックログID | テストID | 実装状況 | 依頼元Runbook | 証跡ファイル/備考 |

| --- | --- | --- | --- | --- |

| BL-0244 | IT-RL-01 | 未実装 (M1.1+) | RUN-DATA-05 | - |

| BL-0245 | OPS-DEG-01 | 未実装 (M1.1+) | RUN-DATA-05 | - |

| BL-0246 | SCN-ING-01 | 未実装 (M1.1+) | RUN-DATA-05 | - |


### CLIコマンド

| バックログID | コマンド | 実装状況 | 依頼元Runbook | 証跡ファイル/備考 |

| --- | --- | --- | --- | --- |

| BL-0247 | `pytest -k data_pipeline` | 未実装 (M1.1+) | RUN-DATA-05 | - |

| BL-0248 | `pytest -k rate_limit_guard` | 未実装 (M1.1+) | RUN-DATA-05 | - |

| BL-0249 | `tradectl board guard --release` | 未実装 (M1.1+) | RUN-DATA-05 | - |

| BL-0250 | `tradectl data ack --provider <name>` | 未実装 (M1.1+) | RUN-DATA-05 | - |

| BL-0251 | `tradectl data failover --mode manual` | 未実装 (M1.1+) | RUN-DATA-05 | - |

| BL-0252 | `tradectl data failover --mode manual --to <provider>` | 未実装 (M1.1+) | RUN-DATA-05 | - |

| BL-0253 | `tradectl data health --symbol <pair>` | 未実装 (M1.1+) | RUN-DATA-05 | - |

| BL-0254 | `tradectl data jobs enqueue` | 未実装 (M1.1+) | RUN-DATA-05 | - |

| BL-0255 | `tradectl data jobs enqueue --task manual_csv` | 未実装 (M1.1+) | RUN-DATA-05 | - |

| BL-0256 | `tradectl data jobs enqueue --task manual_csv ...` | 未実装 (M1.1+) | RUN-DATA-05 | - |

| BL-0257 | `tradectl data manual-template` | 未実装 (M1.1+) | RUN-DATA-05 | - |

| BL-0258 | `tradectl data rate-limit stage set` | 未実装 (M1.1+) | RUN-DATA-05 | - |

| BL-0259 | `tradectl data validate-csv` | 未実装 (M1.1+) | RUN-DATA-05 | - |

| BL-0260 | `tradectl resync --since <ts>` | 未実装 (M1.1+) | RUN-DATA-05 | - |

| BL-0261 | `tradectl status --detail` | 未実装 (M1.1+) | RUN-DATA-05 | - |


## §89 EP-02 Strategy Determinism

* 依頼元Runbook既定: RUN-OPS-02


### CLIコマンド

| バックログID | コマンド | 実装状況 | 依頼元Runbook | 証跡ファイル/備考 |

| --- | --- | --- | --- | --- |

| BL-0262 | `make data-build symbol=<symbol> ...` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0263 | `pytest -k feature_pipeline` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0264 | `pytest -k strategy_determinism` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0265 | `tradectl backtest run --seed 123` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0266 | `tradectl backtest run --strategy m1_baseline_ma_rsi ...` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0267 | `tradectl report ack --strategy ... --state approved` | 未実装 (M1.1+) | RUN-OPS-02 | - |

| BL-0268 | `tradectl report status --strategy m1_baseline_ma_rsi` | 未実装 (M1.1+) | RUN-OPS-02 | - |


## §90 EP-03 Guardrails

* 依頼元Runbook既定: RUN-RISK-01


### テストID

| バックログID | テストID | 実装状況 | 依頼元Runbook | 証跡ファイル/備考 |

| --- | --- | --- | --- | --- |

| BL-0269 | RISK-KS-05 | 未実装 (M1.1+) | RUN-RISK-01 | - |

| BL-0270 | SCN-SPR-02 | 未実装 (M1.1+) | RUN-RISK-01 | - |


### CLIコマンド

| バックログID | コマンド | 実装状況 | 依頼元Runbook | 証跡ファイル/備考 |

| --- | --- | --- | --- | --- |

| BL-0271 | `pytest -k health_state` | 未実装 (M1.1+) | RUN-RISK-01 | - |

| BL-0272 | `pytest -k risk_manager` | 未実装 (M1.1+) | RUN-RISK-01 | - |

| BL-0273 | `tradectl board --guarded` | 未実装 (M1.1+) | RUN-RISK-01 | - |

| BL-0274 | `tradectl board --guarded --reason spread` | 未実装 (M1.1+) | RUN-RISK-01 | - |

| BL-0275 | `tradectl correlation diff --base ...` | 未実装 (M1.1+) | RUN-RISK-01 | - |

| BL-0276 | `tradectl correlation snapshot --window 30d --out ...` | 未実装 (M1.1+) | RUN-RISK-01 | - |

| BL-0277 | `tradectl diagnostics risk --from -7d --mode paper` | 未実装 (M1.1+) | RUN-RISK-01 | - |

| BL-0278 | `tradectl kill-switch engage` | 未実装 (M1.1+) | RUN-RISK-01 | - |

| BL-0279 | `tradectl kill-switch engage --mode paper --reason drawdown` | 未実装 (M1.1+) | RUN-RISK-01 | - |

| BL-0280 | `tradectl kill-switch release` | 未実装 (M1.1+) | RUN-RISK-01 | - |

| BL-0281 | `tradectl risk limits show --mode paper` | 未実装 (M1.1+) | RUN-RISK-01 | - |

| BL-0282 | `tradectl risk override --block --reason r_eff_breach --duration 60m` | 未実装 (M1.1+) | RUN-RISK-01 | - |

| BL-0283 | `tradectl risk summary --week` | 未実装 (M1.1+) | RUN-RISK-01 | - |

| BL-0284 | `tradectl status --history kill-switch --limit 7` | 未実装 (M1.1+) | RUN-RISK-01 | - |


## §91 EP-04 Ticket Clarity

* 依頼元Runbook既定: RUN-HITL-01


### CLIコマンド

| バックログID | コマンド | 実装状況 | 依頼元Runbook | 証跡ファイル/備考 |

| --- | --- | --- | --- | --- |

| BL-0285 | `pytest --snapshot-update` | 未実装 (M1.1+) | RUN-HITL-01 | - |

| BL-0286 | `pytest -k board_renderer` | 未実装 (M1.1+) | RUN-HITL-01 | - |

| BL-0287 | `pytest -k ticket_builder` | 未実装 (M1.1+) | RUN-HITL-01 | - |

| BL-0288 | `tradectl board --filter symbol=USDJPY` | 未実装 (M1.1+) | RUN-HITL-01 | - |

| BL-0289 | `tradectl status --mode paper --detail` | 未実装 (M1.1+) | RUN-HITL-01 | - |

| BL-0290 | `tradectl ticket approve --id ...` | 未実装 (M1.1+) | RUN-HITL-01 | - |

| BL-0291 | `tradectl ticket check-batch --csv tests/fixtures/broker_rounding_cases.csv` | 未実装 (M1.1+) | RUN-HITL-01 | - |

| BL-0292 | `tradectl ticket check-size --pair <pair> --size <lot> --account paper` | 未実装 (M1.1+) | RUN-HITL-01 | - |

| BL-0293 | `tradectl ticket checklist --id <ticket_id>` | 未実装 (M1.1+) | RUN-HITL-01 | - |

| BL-0294 | `tradectl ticket monitor --id ...` | 未実装 (M1.1+) | RUN-HITL-01 | - |

| BL-0295 | `tradectl ticket queue --summary` | 未実装 (M1.1+) | RUN-HITL-01 | - |

| BL-0296 | `tradectl ticket simulate --symbol USDJPY ...` | 未実装 (M1.1+) | RUN-HITL-01 | - |


## §92 証跡・Runbook統合

* 依頼元Runbook既定: RUN-OPS-02


### CLIコマンド

| バックログID | コマンド | 実装状況 | 依頼元Runbook | 証跡ファイル/備考 |

| --- | --- | --- | --- | --- |

| BL-0297 | `のpytestログと、将来的に追加されるCLIログ（` | 未実装 (M1.1+) | RUN-OPS-02 | - |
