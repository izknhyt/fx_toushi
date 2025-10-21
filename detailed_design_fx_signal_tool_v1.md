# FXヒューマン・インザループ投資ツール 詳細設計書 v2.4

## 0. 文書情報
- 作成日: 2025-03-01
- 作成者: Codex AI 支援
- 参照文書: 要件定義（テンプレ形式）v_1.md, basic_design_fx_signal_tool_v1.md
- 対象スコープ: マイルストーンM1（Backtest/Paper/Live 共通基盤）。M2以降で有効化される機能は拡張ポイントとして明示し、実装フックと制約を記載する。

### 0.1 改訂履歴
| 版 | 日付 | 改訂概要 |
| --- | --- | --- |
| v2.4 | 2025-03-02 | Acceptable Degradation演習を自動化するシナリオランナー設計とCLIテレメトリ統合の実装指針を追加。Codex向けワークパッケージのハンドオフ手順を拡張し、Runbook連携と証跡集約を強化。 |
| v2.3 | 2025-03-01 | Codexレビュー負荷を下げるQAスコアカードとRunbook連携シグナルを追加。ドメインデータモデル目録と運用シーケンス図を拡充し、トレーダー視点での整合チェックと将来改修時のIF安定性を強化。 |
| v2.2 | 2025-02-28 | Codex実装スプリント用のタクティカルロードマップとモジュール別契約テーブルを追加。M1 Core優先モジュールの拡張ポイントを再整理し、将来の仕様変更に耐えるインターフェース境界を強化。 |
| v2.1 | 2025-02-27 | Codex開発者向けワークパッケージ青写真とトレーダー運用シナリオを追加し、Acceptable Degradation時の判断材料とレビュー観点を具体化。プロンプト生成テンプレートにシナリオID/Runbook整合性チェックを義務化。 |
| v2.0 | 2025-02-26 | Codex向け実装アクセラレーションパックを追加し、エピック別の成果物・プロンプト指示・テストゲーティングを体系化。Acceptable Degradation運用と将来の拡張に耐える抽象化境界の指針を強化。 |
| v1.9 | 2025-02-25 | 要件v1.4/基本設計v1.4の差分（RateLimitGuard段階評価、Acceptable Degradation手動運用ログ、Validation Data Playbookリンク強化）を反映。Codex実装前提のプロンプト/テスト指示を更新し、SLA計測とRunbookトレーサビリティを拡充。 |
| v1.8 | 2025-02-20 | Codex実装前提の開発オペレーション/プロンプト設計/テストシナリオを体系化。ヒューマン・トレーダー視点の期待KPI/UXと整合させた。 |
| v1.7 | 2025-02-20 | KPI検証/性能モニタリング強化、戦略ガバナンス、データ品質上限対策、運用冗長化を追補し、勝率達成への実効性を高めた。 |
| v1.6 | 2025-02-20 | 運用責任分掌、BCP/DR指針、QAゲート、リスクログ、サポートツール等を追補し、プロジェクト/運用一体の整合を強化。 |
| v1.5 | 2025-02-20 | 運用体制・環境要件・プレフライト/リリース手順・ネットワーク回復設計・ログ分類を追補し、工程連携を強化。 |
| v1.4 | 2025-02-20 | 前提・制約、依存ライブラリ/バージョン管理、重大障害復旧シナリオ、検証環境・エラー通知マッピングを追補。 |
| v1.3 | 2025-02-20 | 状態遷移図・CLI仕様表・設定ガバナンス表・ログ/バックアップ方針・Feature Flag一覧を追補し、運用/拡張観点を強化。 |
| v1.2 | 2025-02-20 | すご腕SEレビュー反映。各レイヤの責務整理、公開API/状態遷移/エラーハンドリングの粒度向上、イベント・スナップショットスキーマ明文化、非機能/テスト/トレーサビリティの整備。 |
| v1.1 | 2025-02-20 | 要件v1.1・基本設計v1.1差分取り込み。Spread Monitor/Execution Model/Funding/Correlation Guard/Config Governance/Health Monitorの詳細を追加。 |
| v1.0 | 2025-02-15 | 初版（M1骨子）。 |

### 0.2 用語
| 用語 | 説明 |
| --- | --- |
| Signal | 戦略プラグインが出力する売買候補。`RawSignal → RankedSignal → RiskVettedSignal → SizedSignal` の順でフィルタされる。 |
| Ticket | ヒューマンに提示する注文チケット。サイズ/SL/TP/TTL/チェックリスト/バッジを含むJSON Linesレコード（FR-07, FR-38）。 |
| GateState | カレンダー、スプレッド、Kill Switch等のブロック条件を統合した状態構造体。 |
| SpreadCooldownState | Spread Monitorが算出する状態。`normal | watch | cooldown | halt`（M1は`normal`/`cooldown`を使用）。 |
| HealthState | リスク/データ/コンフィグ健全性を統合した状態。`ok | degraded | soft_stop | hard_stop`。 |
| BoardMode | Signal Boardの提案挙動。`normal | guarded | halted`。`guarded`はAcceptable Degradation時に主要4ペアのみ承認可、`halted`はKill Switch作動中。 |
| ModeContext | Backtest/Paper/Liveごとの副作用差分を吸収する実行コンテキスト。 |
| PipelineStep | ワークフロー各段階が実装する共通インターフェース。`execute(context) -> context`。 |
| Snapshot | 再起動用ステート（AccountState/OpenTickets/ConfigHash/HealthState/LastBar）。`snapshots/latest/`に保存。 |
| EventBus | DomainEventのpublish/subscribeを担う非同期バス。JSONL永続化を伴う。 |

### 0.3 表記・参照ルール
- FR/AC/NFR番号は要件定義書に準拠する。
- ファイル/クラス名は`src/`からのパスで記載する。
- M2以降の機能は明示的に`(M2+)`ラベルを付与し、M1では無効化フラグまたはダミー実装とする。

### 0.4 対象読者・レビュー体制
| 役割 | 主な責務 | レビュー観点 | サイクル |
| --- | --- | --- | --- |
| プロダクトオーナー | 仕様承認、KPI評価 | KPI整合、運用負荷、HITL UX | 月次（レポート共有後） |
| 開発（Codex + 開発者） | 実装/テスト/CI運用 | 実装可否、技術的負債、テスト網羅 | スプリント毎 |
| 運用担当 | 日次運用、Runbook更新 | アラート対応、プレフライト、ログ監査 | 週次（運用レビュー） |
| セキュリティ/監査（将来） | 監査ログ/アクセス制御 | ログ保持、権限分離、変更管理 | 半期 |

- レビュー結果は`docs/review_log.md`に記録し、重大指摘は`logs/ops/review.log`にも記載する。
- 要件差分は`basic_design_fx_signal_tool_v1.md`を起点にトレースし、受入前にPO＋運用担当のダブルチェックを実施。

### 0.5 文書メンテナンスと変更管理
- 変更要求は`docs/change_requests/`にMarkdownで起票し、PO→開発→運用の順に承認。
- 承認後に`vNext`ブランチへ反映し、リリースタグ作成時に本ドキュメントへ統合。
- 緊急改訂は`logs/ops/hotfix.log`で記録し、24時間以内に正式な更新として追補する。

### 0.6 Codex開発ハンドオフガイド

本プロジェクトでは、実装をAI開発パートナー（Codex）に委任することを前提に、プロンプト設計・成果物レビュー・テスト実行までの一連フローを定義する。HITLトレーダーとしての意思決定品質を担保するため、以下の運用を遵守する。

#### 0.6.1 実装リクエストの標準フォーマット
- **スレッド構成**: Issue/PRには「背景（KPIまたは運用課題）」「期待シナリオ」「受入条件」「関連テレメトリ/ログ」「参考スナップショット」を記載し、Codexへ渡す要約は300〜500字で完結させる。
- **ファイル指定**: 変更対象ファイルは本詳細設計のパス記法に従い列挙し、既存セクション番号を引用（例: `3.1.2 DataIngestionService.fetch_latest`）。
- **I/O契約**: 追加関数・クラスのシグネチャ、例外、戻り値を表形式で記載。可能な限り`typing`注釈と`pydantic`モデル定義を明示する。
- **テスト要件**: `pytest -k <keyword>`単位で実行指示を与え、成功/失敗判定基準と許容する浮動小数誤差を指定する。
- **運用制約**: Spread・ニュース・Kill Switchといったトレーダー観点の制約は必ず背景に紐づけ、レビュー観点（例: 「Acceptable Degradation時でもSpread Guardの閾値を緩めない」）を明記する。

#### 0.6.2 Codex向けプロンプトテンプレート
```
<概要>
  ・機能目的（FR/NFR/AC番号）
  ・想定するヒューマン判断ポイント

<既存設計参照>
  ・本書の該当セクション番号
  ・関連クラス/関数とファイルパス

<変更要求>
  ・追加/更新メソッド（署名 + docstring要件）
  ・入出力例（JSON/CLI例示）
  ・例外/フォールバック動作

<テスト>
  ・必須テストコマンド
  ・Fixturesまたはモック方針

<レビューメモ>
  ・リスク観点（スリッページ/レートリミット/ヒューマン手順）
  ・ログ/監査要件
```
- プロンプトはGit管理（`docs/prompt_packages/<YYYYMMDD>_<feature>.md`）し、再利用時は差分管理する。
- Codexへ渡すコード断片は**200行以内**に限定し、関連する`dataclass`/`Enum`の定義を先頭に含める。外部依存がある場合はスタブ/型定義を同梱する。
- 反復が必要な場合は「差分モード」を明示し、前回出力との差分レビュー観点を列挙する。

#### 0.6.3 実装優先度マトリクス（M1）
| トラック | 主担当モジュール | Codex作業エピック | 期待成果物 | 受入基準 |
| --- | --- | --- | --- | --- |
| データSLA | `src/data/service.py`, `src/data/quality.py`, `src/data/rate_limit.py` | `EP-01 DataLag Mitigation` | Fetch/Processing遅延計測・フォールバック導線強化＋RateLimitステージ運用 | `metrics/data_ingestion_sla.jsonl`のp95が閾値内、`metrics/rate_limit_window.jsonl`にStage記録が残る、`tests/integration/test_data_pipeline.py`と`tests/unit/test_rate_limit_guard.py`合格 |
| シグナル | `src/features/pipeline.py`, `src/strategies/registry.py` | `EP-02 Strategy Determinism` | 特徴量リプレイ一致、戦略プラグインの決定論テスト | Backtest/Liveで同一入力→同一出力、`pytest -k strategy_determinism`合格 |
| リスク/ヘルス | `src/core/health.py`, `src/risk/manager.py` | `EP-03 Guardrails` | Kill Switch/Board Mode遷移ロジック、リスクアラート配線 | 状態遷移テスト（`tests/unit/test_health_state.py`）合格、CLI `tradectl status`に理由表示 |
| チケットUX | `src/ticket/builder.py`, `src/interfaces/cli/board.py` | `EP-04 Ticket Clarity` | チケットJSON整形、チェックリスト/バッジ表示、監査ログ項目 | `pytest -k ticket_builder`合格、サンプルCLIスナップショット承認 |
| レポート/監査 | `src/reporter/generator.py`, `src/persistence/audit.py` | `EP-05 Weekly Review` | KPI算出テンプレ、監査トレーサビリティ | `tradectl report weekly --dry-run`でMarkdown生成、監査ログ整合 |

優先度はデータSLA > リスク/ヘルス > シグナル > チケットUX > レポート。Codexへは同時並行を避け、1エピックずつ完了させる。

#### 0.6.4 Codex出力レビューの観点
- **差分検証**: `git diff --stat`で対象ファイルが設計指定内に収まっているか確認する。想定外ファイル更新は即座に差戻し。`poetry lock`変更は明示的な承認を得る。
- **静的チェック**: `ruff`, `mypy`（M1 optional）を`pre-commit`で実行。Codex出力に余計な`print`/`TODO`が含まれていないかを確認する。
- **取引リスク**: Spread/Kill Switch関連の閾値が設計値から逸脱していないか、例外時にヒューマンへ十分な情報が届くかをレビューする。
- **ログ/監査**: `logger`メッセージはRunbook検索性の高いキーワード（例: `data_latency_fetch`, `kill_switch_manual_ack`）を含める。監査ログは`AuditRecord` schema準拠であること。
- **テスト**: Codex出力に対して指定テストが実行されたことをCIログまたはローカル証跡で確認。未実行の場合は必ず差戻し。

#### 0.6.5 ヒューマン・トレーダー観点のKPIリンク
- ヒット率、平均RR、週次ドローダウンなどのKPIは`reports/kpi/dashboard.md`に集約し、Codexが手を入れる際には関連KPIの期待変化を記述する。
- Acceptable Degradation状態での運用負荷を軽減するため、開発チケットには「オペレータが何分短縮されるか」「どのRunbookステップが省略/自動化されるか」を必ず盛り込み、実装後に`logs/ops/workload.log`で効果を定量化する。
- トレーダー視点でのUX課題（例: チケット承認時にSpread理由が不明瞭）は`docs/ux_feedback.md`で管理し、Codex改善タスクには該当行を参照させる。

#### 0.6.6 Codexフィードバックループ
1. Codex出力をレビュー後、`docs/prompt_packages/<date>_<feature>.md`に「良かった点」「改善要望」「想定外差分」を追記し、次回プロンプトの改善に反映する。
2. リリース後7日間は該当機能のメトリクスを重点監視し、異常時は`feedback_loop.md`に記録。Codexへの再依頼時はこのログを添付する。
3. KPIが改善した場合は`reports/weekly/<YYYYWW>.md`に成果を記載し、反対に悪化した場合はリスクレビュー（`docs/risk_review/<YYYYMMDD>.md`）で原因と暫定対応をまとめる。

### 0.7 Codex実装アクセラレーションパック（v2.0追加）

Codexへ実装を委任する際の成果物粒度・レビュー観点・トレーサビリティをさらに明確にするため、以下の運用ルールとテンプレートを追加する。これらは将来のM1.1/M2機能追加時にも再利用できるよう設計しており、エピックを跨いだ再帰的改善サイクルを可能にする。

#### 0.7.1 ブランチ/レビュー運用レーン
| レーン | ブランチ命名 | 主担当 | ゴール | 必須テスト | 監査ログ |
| --- | --- | --- | --- | --- | --- |
| Discovery | `feature/discovery/<epic>-<YYYYMMDD>` | PO＋開発 | 実験/仮実装。`docs/prompt_packages`に仮説とスナップショットを残す。 | `pytest -k smoke` | `logs/audit/discovery.log`（抜粋） |
| Build | `feature/<epic>-<story>` | Codex | 詳細設計に沿った本実装。Feature Flagは既定`off`。 | `pytest -k <story>`＋`ruff --select=E,F,I` | `logs/audit/build.log`（diff, cfg_hash） |
| Hardening | `hardening/<epic>-<fix>` | Codex＋開発 | Acceptable Degradation解除、回帰修正。 | `pytest`, `poetry run mypy`（対象モジュール） | `logs/audit/hardening.log`（SLA値） |
| Release | `release/<version>` | 開発 | リリースノート生成、タグ付け、bundle。 | `make ci-lite` | `reports/release/<version>.md` |

- `feature_flags/<epic>.yaml`はBuildフェーズでレビュー、Releaseフェーズで既定値を決定する。`docs/release_checklist.md`へ各レーン完了条件を追記済み。

#### 0.7.2 プロンプト/アーティファクト構成
- **Prompt Bundle**: `docs/prompt_packages/<YYYYMMDD>_<epic>_<story>.md`に以下を収録する。
  1. **差分概要**（300字以内）。
  2. **該当セクション引用**：本書のセクション番号＋抜粋（最大200行）。
  3. **I/O契約表**：関数シグネチャ、例外、戻り値、型ヒント必須。
  4. **テスト指示**：実行コマンド／期待結果（閾値含む）。
  5. **運用影響メモ**：Board/Kill Switch/Runbookのどの手順に影響するかを3 bulletで記載。
- **Diff Attachments**: Codexへ渡す既存コードは`docs/snippets/<epic>/<module>.py`として同期。200行超の場合は該当クラス単位に分割し、`# region`コメントで明示する。
- **Artifact検証**: Codex出力は`git apply --check`で検証後にブランチへ反映。未適用diffは`docs/prompt_packages/...`の`Rejected`節へ記録する。

#### 0.7.3 エピック別成果物マトリクス（v2.0更新）
| エピックID | 必須成果物 | 参照セクション | 最低限テスト | 監視・メトリクス | Acceptable Degradation時の判断材料 |
| --- | --- | --- | --- | --- | --- |
| EP-01 DataLag Mitigation | `src/data/*`, `metrics/data_ingestion_sla.jsonl`, `docs/runbooks/RUN-DATA-05/06`更新 | §3.1, §3.21, §5.1 | `pytest -k data_pipeline`, `pytest -k rate_limit_guard`, `scripts/qa/manual_csv_smoke.sh` | `metrics/data_ingestion_sla.jsonl`, `metrics/rate_limit_window.jsonl` | Stage退行条件、手動CSV投入ログ、`degraded_ack`記録有無 |
| EP-02 Strategy Determinism | `src/features/*`, `src/strategies/*`, `docs/validation/strategy_determinism.md` | §3.3〜§3.7, §4.3 | `pytest -k strategy_determinism`, `pytest -k feature_pipeline` | `metrics/strategy_replay.jsonl`, `reports/research/*` | `determinism_drift`イベント、`strategy_manifest`バージョン |
| EP-03 Guardrails | `src/core/health.py`, `src/risk/manager.py`, `src/interfaces/cli/status.py`, Runbook更新 | §2.5, §3.8〜§3.10, §5.3 | `pytest -k health_state`, `pytest -k risk_manager`, `pytest -k cli_status` | `health_state_transitions.jsonl`, `kill_switch_events.jsonl` | `HealthMonitor`推奨アクション履歴、`reports/validation_log/AC-45*` |
| EP-04 Ticket Clarity | `src/ticket/*`, `src/interfaces/cli/board.py`, `docs/ux_feedback.md`追記 | §3.16, §5.5, §6.2 | `pytest -k ticket_builder`, `pytest -k board_renderer`, `pytest --snapshot-update`（必要時） | `logs/audit/ticket.jsonl`, `metrics/cli_perf.jsonl` | `degraded`時のBoardモード切替手順、`RiskDisclosure`バナー状態 |
| EP-05 Weekly Review | `src/reporter/*`, テンプレ更新、`reports/templates/*` | §3.18, §5.11 | `tradectl report weekly --dry-run`, `pytest -k reporter` | `reports/weekly/*.md`, `metrics/reporter.jsonl` | KPI欠損時のFallbackコメント、`guarded`時のコメントテンプレ |

- 表の「必須成果物」は実装完了時に`docs/checklists/<epic>_done.md`へチェックし、Releaseフェーズでサインオフする。Codexへ渡す際は表の行を丸ごと貼り付け、達成条件を明文化する。

### 0.8 Codex実装ロードマップ（M1 Coreタクティクス）

Codexへ実装を委任する際のスプリント運用を以下に定義する。各スプリントは**1エピックずつ完遂**し、レビュー/Runbook訓練/メトリクス監視をセットで完了させることで、後続変更にも耐えられる堅牢な境界を維持する。

| Sprint Window | ワークパッケージ | 主担当モジュール/ファイル | 必須プロンプト添付物 | テストゲート | 進捗審査ポイント |
| --- | --- | --- | --- | --- | --- |
| Sprint 1 (週次) | EP-01 DataLag Mitigation | `src/data/service.py`, `src/data/rate_limit.py`, `src/data/cache.py`, `src/data/quality.py` | `docs/prompt_packages/<date>_ep01.md`, `docs/snippets/ep01/data_service.py`（200行以内）, `metrics/data_ingestion_sla.jsonl`抜粋 | `pytest -k data_pipeline`, `pytest -k rate_limit_guard`, `scripts/qa/manual_csv_smoke.sh`（429エッジケースを含む） | `metrics/data_ingestion_sla.jsonl`でfetch/processing両方のp95が記録され、`RUN-DATA-05/06`のチェックリストが更新されていること。 |
| Sprint 2 (週次) | EP-03 Guardrails | `src/core/health.py`, `src/risk/manager.py`, `src/risk/kill_switch.py`, `src/interfaces/cli/status.py` | `docs/prompt_packages/<date>_ep03.md`, `docs/snippets/ep03/risk_manager.py`, `reports/ops/incidents/*`の代表ログ | `pytest -k health_state`, `pytest -k risk_manager`, `pytest -k cli_status`, `make sla-report`（推奨） | `health_state_transitions.jsonl`に推奨アクションが残り、`tradectl status`でBoardモード/推奨Runbookが表示されること。 |
| Sprint 3 (週次) | EP-04 Ticket Clarity | `src/ticket/builder.py`, `src/ticket/checklist.py`, `src/interfaces/cli/board.py`, `src/ticket/validator.py` | `docs/prompt_packages/<date>_ep04.md`, `docs/snippets/ep04/ticket_builder.py`, CLIスクリーンショット（`tradectl board --sample`） | `pytest -k ticket_builder`, `pytest -k board_renderer`, `pytest --snapshot-update`（必要時） | `logs/audit/ticket.jsonl`に`ticket.edit.*`とチェックリストバッジが記録され、`docs/ux_feedback.md`の該当課題がクローズされていること。 |
| Sprint 4 (週次) | EP-05 Weekly Review | `src/reporter/generator.py`, `src/reporter/templates/weekly.py`, `src/interfaces/cli/report.py` | `docs/prompt_packages/<date>_ep05.md`, `reports/templates/m1_core.md`, `reports/kpi_snapshots/latest.json` | `pytest -k reporter`, `tradectl report weekly --dry-run`, `tradectl kpi rollup --window 90` | 週次レポートに`metric_state`が表示され、`reports/weekly/<YYYYWW>.md`へ自動生成＋POコメント欄が残っていること。 |

- **スプリントゼロ**: `src/core/session.py`, `src/core/workflow.py`, `src/interfaces/cli/main.py`の現状調査と`poetry run ruff --fix`適用。Codexに渡す前に既存ユニットテストをすべて再実行し、ベースラインを`docs/prompt_packages/<date>_baseline.md`へ記録する。
- **フォールバックルール**: Acceptable Degradation状態（`board_mode=guarded`）でスプリントが開始された場合、まずEP-01の`ManualCsvIngestionTask`と`RateLimitGuard`を再確認し、Runbookサインオフを更新する。ガード解除後に次エピックへ進む。
- **ブリッジング**: 各スプリント完了時に`docs/review_log.md`へレビュー結果を追記し、次スプリントのプロンプトには「前スプリントの改善要望」節を必須で含める。

- **将来拡張への備え**:
  - M1.1以降に備え、テーブルの`必須プロンプト添付物`列に「差分パッチ」「テレメトリ抜粋」「Runbookリンク」を最低3点添付するルールを明文化した。これにより後続のCodex依頼時に再利用可能な知識ベースを形成する。
  - `docs/snippets/`以下のコード断片は`# region`コメントで抽象化境界を示し、関数追加時に差分マージしやすい構造を保つ。

### 0.9 Codexワークパッケージ青写真（v2.1追加）

Codexへ実装タスクを委譲する際に、トレーダー運用目線での期待アウトカム・レビュー観点を即座に共有できるよう、下表のシナリオ別青写真を準備する。各シナリオはRunbook/Validation Data Playbook/メトリクスとリンクし、Acceptable Degradation下でも判断がブレないようトレーサビリティを確保する。

| シナリオID | 代表タスク/エピック | トレーダー視点の目的 | Codex向け着手前チェック | 成果物/証跡 | 受入テスト/CLI | Runbook整合ポイント |
| --- | --- | --- | --- | --- | --- | --- |
| `SCN-ING-01` | EP-01 DataLag Mitigation | SLA遅延を素早く観測しGuarded切替を判断できる状態にする | `metrics/data_ingestion_sla.jsonl`の最新30日サマリを確認し、欠損期間がRunbook `RUN-DATA-05`のステージ記録と一致するかレビューする | `src/data/service.py`差分、`metrics/data_ingestion_sla.jsonl`サンプル、`docs/runbooks/RUN-DATA-05.md`更新 diff | `pytest -k data_pipeline`, `tradectl data rate-limit stage inspect`, `make sla-report` | `RUN-DATA-05` 該当節のチェックボックスが全てTrue、`degraded_ack`ログのダブルサイン確認 |
| `SCN-RISK-02` | EP-03 Guardrails | 手動Kill Switch判断を迷わず下せるよう理由表示と履歴を整備 | `logs/audit/killswitch.jsonl`最新ファイルを開き、理由タグ/承認者がRunbook `RUN-RISK-01`と揃っているか確認 | `src/core/health.py`、`src/interfaces/cli/status.py`差分、`reports/validation_log/AC-45*`リンク集 | `pytest -k health_state`, `tradectl kill-switch status`, `tradectl health show --verbose` | `RUN-RISK-01`の承認手順にCLIスクリーンショット添付、`RUN-POST-03`への事後レビュー反映 |
| `SCN-TKT-03` | EP-04 Ticket Clarity | HITL承認時にSpread/ニュース/サイズ根拠が即読解できる | `docs/ux_feedback.md`の未解決コメントを確認し、対応範囲を明示 | `src/ticket/builder.py`, `src/interfaces/cli/board.py` diff、`tests/snapshots/board/*.snap`更新、`logs/audit/ticket.jsonl`サンプル | `pytest -k board_renderer`, `pytest --snapshot-update --maxfail=1`, `tradectl board --filter symbol=USDJPY` | `RUN-OPS-02`のBoardレビュー節に新バナー説明を追記、`RUN-HITL-01`のチェックリスト更新 |
| `SCN-REP-05` | EP-05 Weekly Review | 週次レビュー会議で即時にSharpe/最大DD/Runbook抜粋を共有 | `reports/weekly/templates/m1_core.md`のバージョンと`reports/kpi_snapshots/*.json`最新ファイルを突合 | `src/reporter/generator.py`, `docs/templates/reports/*` diff、`reports/weekly/<YYYYWW>.md`サンプル、`metrics/reporter.jsonl` | `tradectl report weekly --profile paper --dry-run`, `pytest -k reporter` | `RUN-OPS-04`（週次レビュー）にテンプレ更新を反映、`docs/review_log.md`へレビュー記録 |
| `SCN-BENCH-07` | Benchmark Monitor (EP-05派生) | ベンチマーク乖離検知を迅速化し改善タスクへ繋ぐ | `reports/benchmark/manual_log_signoff/`内の直近ファイルで手動CSVハッシュが一致しているか検証 | `src/reporter/benchmark.py`, `src/interfaces/cli/benchmark.py` diff、`benchmark_runs/normalized/*.parquet`サンプル | `tradectl benchmark ingest --dry-run`, `tradectl benchmark compare --window 90d`, `pytest -k benchmark_monitor` | `GOV-BENCHMARK-01`のエスカレーション節に新ログ添付、`RUN-DATA-06`の手動CSVダブルチェック欄更新 |

- **プロンプト生成ルール**: 上表のシナリオIDをプロンプト見出しに含め、`<シナリオID> :: <概要>`形式で記載する。`related_runbooks`キーで参照Runbook節番号を列挙し、Codexが差分を逃さないようにする。
- **レビュー観点**: 各シナリオには「トレーダーUX」「運用負荷」「データ整合」「Acceptable Degradation復帰条件」の4観点チェックリストを付与し、PRレビューで`LGTM`前に全観点へ○/×/要フォローを入力する。
- **ロールバック計画**: 受入テスト失敗時は`docs/prompt_packages/<date>_<scenario>_rollback.md`に差分と復旧手順を残し、`git revert`とRunbookロールバック箇所を明示する。Acceptable Degradation下ではロールバック判断までの時間目標（最大30分）を記録する。

#### 0.7.4 コーディング規約と自動チェック強化
- **Docstring**: すべての公開メソッドはGoogleスタイルDocstringで`Args`/`Returns`/`Raises`を記述し、`Example`にはCLIやJSONのサンプルを最低1件含める。
- **型注釈**: Optional/Unionでは`typing.Annotated`で意味を付与（例: `Annotated[Decimal, "pip"]`）。テストでは`typing.get_type_hints`で型逸脱を検証するユーティリティ（`tests/util/type_contract.py`）を活用する。
- **ログ規約**: ログレベルは`logger.log(LogLevel.DATA_LATENCY, {...})`のようにEnum経由で出力し、Runbook検索用タグ（例:`event="rate_limit_stage"`）をJSONに含める。
- **静的解析**: `make ci-lite`に`ruff --select=F,E,I`, `pyright --project pyproject.toml`（キャッシュ可）、`pytest --maxfail=1`を含め、Codex成果物レビュー時は`make ci-lite`の成功ログを添付させる。
- **フォーマッタ**: `ruff format`で統一。CodexがBlack整形を提案した場合は差分レビューで却下し、本設計書での`ruff`準拠を強調する。

#### 0.7.5 将来拡張に備えた抽象化境界
- **ProviderAdapter**: `src/data/providers/base.py`に抽象メソッド`fetch_raw`, `normalize`, `backfill_range`を定義し、M1で未使用でもスタブを配置しておく。M2でREST/WebSocket対応を追加する際の差分を局所化する。
- **StrategyPlugin**: `StrategyMetadata`へ`capabilities`（例:`{"supports_reduce_only": false}`）フィールドを追加し、M1では既定値を返すだけとする。M2でReduce-OnlyやShadowモードを導入しても`StrategyEngine`のシグネチャを維持できる。
- **HealthSignal**: `HealthMonitor`からCLI/Reporterへ送るメッセージは`HealthSignal` dataclassで統一し、`recommended_action`をEnum（`RUNBOOK`, `NOTIFY`, `DEFERRED_REVIEW`）にする。将来Slack/Webhook追加時にJSON Schemaが崩れないようにする。
- **ConfigDiff**: `ConfigRegistry.apply_patch`は`DiffResult`を返し、`dangerous`キー変更時に`NextBarChangeQueue`へ登録する現在の仕様を維持。M1では`DiffResult.rollback_instructions`を`None`にし、M2でロールバック自動生成を追加する余地を残す。
- **CLI Extensibility**: Typerコマンドは`@cli.command()`の代わりに`register_command(CommandSpec)`を利用するラッパーを導入し、GUI/Tauri移行時に再利用する。Codexは新コマンド実装時に`CommandSpec`を拡張すること。

### 0.10 Codex QAスコアカード（v2.3追加）

- **目的**: Codexが出力した成果物のレビュー時間を短縮しつつ、トレーダー運用で致命的な抜け漏れを防ぐ。スプリント毎に以下のスコアカードを埋め、`docs/review_log.md`に転記する。

| チェックID | タイミング | 担当 | 確認内容 | 必須証跡/ログ | 自動化ステータス |
| --- | --- | --- | --- | --- | --- |
| QA-01 Baseline | ブランチ作成時 | 開発（Codex前） | `make ci-lite`ベースラインが全てGREENであることを確認し、最新コミットハッシュと共に`docs/prompt_packages/<date>_baseline.md`へ貼り付ける。 | `ci/baseline_<commit>.log`、`metrics/version_pin.json` | ✅ `make ci-lite`（ローカル/CI両方） |
| QA-02 Diff Envelope | PRレビュー前 | PO/リード開発 | `git diff --stat`が設計指定ファイル内に収まっているか、`pyproject.toml`差分がないかを確認。許容外ファイルは`reject_reason`付きでCodexへ差戻す。 | `logs/audit/build.log`抜粋、`docs/prompt_packages/<date>_<epic>.md::Diff` | 🔁 半自動（`scripts/check_diff_scope.py`） |
| QA-03 Runbook Sync | テスト完了後 | 運用担当 | 実装変更に紐づくRunbook節が更新済みであるか、`degraded_ack`などの手動承認ログが存在するかを確認。 | `docs/runbooks/*`差分、`reports/validation_log/AC-*`リンク、`logs/ops/review.log` | 🔁 `make runbook-lint`で参照検知 |
| QA-04 Metrics Guard | マージ前 | 開発＋トレーダー | `metrics/*.jsonl`に新規メトリクスが追加された場合は命名規約と閾値が設定済みか、週次レポート集計に影響が出ないかを確認。 | `metrics/schema_index.json`, `reports/weekly/<YYYYWW>.md` | ✅ `scripts/qa/metrics_schema_check.py` |
| QA-05 Ops Drill Ready | Acceptable Degradation解除時 | Ops Manager | Guarded/Haltedからの復旧条件が満たされているか。`tradectl board --normal`実行前に`RUN-DATA-05`のチェックボックスが全て完了しているかを二重確認。 | `logs/ops/workload.log`, `docs/runbooks/RUN-DATA-05.md`サイン、`health_state_transitions.jsonl`抜粋 | ❌ 手動（M1 Core） |

- **レビューシグナル**:
  - `health.changed`イベントに`qa_scorecard`タグを付与し、各チェックIDの成否を`payload.qa`へ格納する。例:`{"qa":{"QA-01":"pass","QA-03":"pending"}}`。
  - `tradectl status --qa`で直近のQAスコアと不足証跡を表示。Codexへの差戻し時はこの出力をスクリーンショット化して添付する。
  - Acceptable Degradation期間中は`QA-05`を強制`pending`扱いとし、解除後24h以内に`pass`へ更新する。未更新の場合は`HealthMonitor.raise('warning','qa_scorecard_stale')`を送出し、Opsレビューを促す。

- **トレーダー向け指標**: QA完了後に`reports/weekly/<YYYYWW>.md`へ「QA所要時間」「Runbook更新数」「Guard解除判断」を追記し、運用負荷を可視化する。翌週のスプリント計画でQA時間が閾値（>6h/週）を超えた場合はタスク分割または自動化チケットを起票する。

## 1. アーキテクチャ概要

本システムはヒューマン・インザ・ループ（HITL）運用を前提としたPython 3.11アプリケーションであり、データ取得からシグナル生成・リスク制御・チケット発行・監査記録までをイベント駆動で統合する。Backtest/Paper/Liveの各モードは同一ドメインロジックを共有し、I/Oと副作用はインフラ層で抽象化することでトレーサビリティと再現性（AC-13, FR-08）を担保する。

### 1.1 システム構成
```
┌──────────────────────────────────────────────┐
│ CLI (tradectl) / 将来: GUI (React+Tauri)      │
└───────────────┬──────────────────────────────┘
                │Command/API (Typer/Rich)
┌───────────────┴──────────────────────────────┐
│ Application Service Layer                    │
│  SessionManager / ModeController             │
│  Workflow Orchestrator & Async Scheduler     │
│  EventBus / SnapshotManager / HealthMonitor  │
└───────────────┬──────────────────────────────┘
                │Domain Events (JSONL stream)
┌───────────────┴──────────────────────────────┐
│ Domain Core Layer                            │
│  DataIngestion → FeaturePipeline → Regime    │
│  → StrategyEngine → ExecutionModel → Scoring │
│  → RiskManager → CorrelationGuard → Sizer    │
│  → TicketBuilder → Reporter → Persistence    │
└───────────────┬──────────────────────────────┘
                │Repositories / External APIs
┌───────────────┴──────────────────────────────┐
│ Infrastructure Layer                         │
│  Providers (yfinance/dukascopy/CSV)          │
│  Storage (Parquet/SQLite/JSONL)              │
│  Config/Secrets (.yaml/.env/Keychain)        │
│  Notification (SMTP, Slack future)           │
└──────────────────────────────────────────────┘
```
- **M1 Coreスコープガード**: 上記ディレクトリのうち`scoreboard/`, `ideas/`, `ops_readiness/`, `governance/`, `reconciliation/`はM1 Coreでは最小スタブのみ配置し、必要なIFは`src/domain/governance/contracts.py`などの軽量スタブに限定する。Feature Flag `governance.alpha_scoreboard`等は`False`を既定とし、スタブは`pass`実装＋`logging.getLogger(__name__).info('noop')`に留める。将来有効化時は本設計書に追補する。


### 1.2 レイヤー責務
- **Application Service**: ランタイム管理（起動/停止/モード切替/Catch-up）、スケジューリング、イベント配信、CLI連携。副作用はEventBus/Alert/Snapshotへ委譲し、Fail-FastでKill Switchに連携する。
- **Domain Core**: ドメインデータ処理を担う純粋ロジック群。状態は明示的データ構造で受け渡し、モード差分は`ModeContext`で吸収する。
- **Infrastructure**: 外部システムとの境界。データプロバイダ、設定、永続化、通知、メトリクス。ユニットテストでは全てMock可能。

### 1.3 ディレクトリ構成（M1）
```
src/
  app/
    main.py              # CLIエントリ / Graceful shutdown
    telemetry.py         # 起動時メトリクス初期化
  interfaces/
    cli/
      __init__.py        # Typerアプリ登録
      board.py           # tradectl board
      tickets.py         # approve/reject/edit
      status.py          # health/snapshot表示
      events.py          # Event tail
      export.py          # CSV/JSON export
      resync.py          # Catch-up操作
      spread.py          # Spread監視補助
    renderers.py        # CLI共通フォーマッタ
  core/
    session.py           # SessionManager, ModeController
    workflow.py          # Pipeline orchestrator
    scheduler.py         # AsyncIntervalJob/OneShotJob
    event_bus.py         # publish/subscribe + JSONL sink
    health.py            # HealthMonitor/KillSwitch state
    snapshot.py          # SnapshotManager
  data/
    service.py           # DataIngestionService
    rate_limit.py        # RateLimitGuard & PollingStageEvaluator（M1 Core: 手動段階評価, M1.1+: 自動化再検討）
    cache.py             # Parquet/Arrowキャッシュ
    quality.py           # DataQualityGuard
    providers/
      yahoo.py
      dukascopy.py
      csv_loader.py
  features/
    pipeline.py          # FeaturePipeline + multi-TF join
    indicators.py        # インジケータ実装
    regime.py            # RegimeDetector
  strategies/
    base.py              # StrategyProtocol/Context
    registry.py          # Plugin登録/ロード
    ma_rsi.py
    donchian.py
  execution/
    model.py             # ExecutionModel（M1 Core: deterministic baseline実装, M1.1+: 分布拡張）
    spread.py            # SpreadMonitor + cooldown state（M1.1で本稼働、M1 Coreはスタブのみ）
    adjustments.py       # ExecutionAdjustments dataclass（M1 Coreでは参照のみ）
  scoring/
    hybrid.py            # HybridScore（M2+で有効化、M1 Coreではファイル未配置/追加不要）
    stability.py         # 摂動テスト（M2+）
    ranking.py           # ランキング/閾値
  scoreboard/
    service_stub.py      # StrategyScoreboardServiceStub (M1, no-op; M2+本実装は付録G)
    jobs_stub.py         # 週次ジョブスタブ（ログ出力のみ）
    repository_stub.py   # KPIキャッシュ参照スタブ（固定レスポンス）
  risk/
    policy.py            # RiskPolicy構造体
    manager.py           # Kill Switch/制約評価
    correlation_guard.py # 通貨・シンボル相関ガード（M1.1以降）
    sprt.py              # SPRT（M2+でのみ有効、M1 Coreはスタブ）
  account/
    service.py           # 残高/証拠金/ポジション集計
    fx_rates.py          # FX換算レート
    exposure.py          # 通貨バケット/相関用エクスポージャ
  sizing/
    fractional.py        # Fixed fractional sizing
    rounding.py          # ブローカー仕様準拠の丸め
  funding/
    service.py           # FundingCurve
    loaders.py           # swap_rates.csv / APIローダ
  ideas/
    manager_stub.py      # IdeaPipelineManagerStub (M1, ガバナンスAPIスタブ)
    schema_stub.py       # manifest/checklist検証スタブ
    checklist_stub.py    # ステージ別チェックリスト生成スタブ（常にTODO保留）
  calendar/
    service.py           # 経済指標/休日ゲート
    adapters.py          # CSV/外部API同期
  ops_readiness/
    evaluator_stub.py    # OpsReadinessEvaluatorStub (M1, スコア=Not Assessed)
    evidence_stub.py     # 証跡ハッシュ検証スタブ
  governance/
    model_risk_stub.py   # ModelRiskRegisterServiceStub (M1, ギャップ検出無効)
    registry_stub.py     # Register参照スタブ
  reconciliation/
    service_stub.py      # StatementReconciliationServiceStub (M1, 証跡未対応)
    normalizer_stub.py   # ブローカーステートメント正規化スタブ
    matcher_stub.py      # 取引/残高突合スタブ
  ticket/
    builder.py           # TradeTicket構築
    validator.py         # Broker検証/TTL/Drift
    checklist.py         # ヒューマンエラーチェック
  persistence/
    events.py            # DomainイベントJSONL
    audit.py             # HITL監査ログ
    snapshot.py          # Snapshot永続化
  backtest/
    engine.py            # Pipeline replay
    walkforward.py       # Walk-Forward
    optimizer.py         # Grid/Random探索
  reporter/
    generator.py         # 週次/成績レポート
    templates/           # Markdownテンプレート
  infra/
    config.py            # ConfigRegistry + schema検証
    registry.py          # モード別依存性組立
    alert.py             # AlertDispatcher (SMTP)
    metrics.py           # メトリクス集計/Exporterフック

tests/
  conftest.py
  fixtures/
  unit/
  integration/
```

ランタイムディレクトリとして `config/`, `data/`, `logs/`, `snapshots/`, `reports/`, `metrics/` を使用する。

### 1.4 ドメインデータモデル目録（v2.3追加）

| モデル | 主フィールド（型） | 生成元 | 主な利用先 | 備考 |
| --- | --- | --- | --- | --- |
| `MarketFrame` | `ts: datetime64[ns]`, `open/high/low/close: Decimal`, `volume: float`, `provider_id: str`, `quality_flag: int`, `timeframe: Timeframe` | DataIngestionService | FeaturePipeline, Reporter, SnapshotManager | `quality_flag`は`0=clean/1=patched/2=quarantined`。`provider_id`で後続の評価ログと突合する。 |
| `ManualCsvPayload` | `path_op: Path`, `path_review: Path`, `symbol: str`, `timeframe: Timeframe`, `submitted_by: str` | CLI `tradectl data jobs enqueue --task manual_csv` | ManualCsvIngestionTask, Audit Service | 2系統CSVのSHA256ハッシュを`manual_csv.log`へ出力し、Runbook `RUN-DATA-06`の証跡リンクと紐付ける。 |
| `BackfillReport` | `bars_loaded: int`, `fallback_used: bool`, `segments: list[BackfillSegment]`, `started_at/completed_at: datetime`, `warnings: list[str]` | DataIngestionService.backfill | CLI `tradectl data backfill`, HealthMonitor | 欠損区間のスパンを`segments`に保持し、再実行対象を明示。`warnings`はRunbookレビューで確認する。 |
| `FeatureFrame` | `symbol: str`, `timeframe: Timeframe`, `features: dict[str, NDArray]`, `lagged_context: FeatureLagContext` | FeaturePipeline | StrategyEngine, Backtest | `lagged_context`で最新Nバーの特徴量を保持し、決定論テストで利用。 |
| `StrategyContext` | `mode: ModeContext`, `feature_frame: FeatureFrame`, `regime_state: RegimeState`, `gate_state: GateState`, `account_state: AccountState`, `config: ConfigSlice` | Workflow Orchestrator | StrategyEngine | `config`は読み取り専用スナップショット。Codexは副作用を与えないこと。 |
| `RawSignal` | `id: str`, `strategy_id: str`, `symbol: str`, `side: Literal['LONG','SHORT']`, `score: float`, `ttl_sec: int`, `tags: list[str]`, `notes: dict[str, Any]` | Strategy Plugins | ScoringService | `tags`は`ALIGN/VOL/NEWS`等のバッジ候補、`notes`は根拠テキストや指標値を格納。 |
| `RankedSignal` | `raw: RawSignal`, `rank: int`, `base_score: float`, `components: dict[str, float]`, `ui_hints: UiHint` | ScoringService | RiskManager, Reporter | `components`でSharpe/Drawdown等の要素を保持し、`ui_hints`でBoard表示用コメントを提供。 |
| `RiskVettedSignal` | `ranked: RankedSignal`, `risk_flags: list[RiskFlag]`, `effective_r: Decimal`, `margin_required: Decimal`, `approved: bool`, `notes: dict[str, Any]` | RiskManager | PositionSizer, TicketBuilder | `risk_flags`に`r_eff`, `bucket_limit`, `kill_switch`等を格納し、Reject時は理由を`notes`へ付与。 |
| `ExecutionAdjustments` | `expected_entry: Decimal`, `expected_slippage: Decimal`, `ttl_seconds: int`, `fill_style: ExecutionFillStyle`, `drift_guard_r: Decimal` | ExecutionModel | TicketBuilder, Reporter | `fill_style`は`MARKETABLE_LIMIT`などを想定。`drift_guard_r`はReduce-Only推奨ライン。 |
| `GateState` | `board_mode: BoardMode`, `kill_switch: KillSwitchState`, `calendar_blocked: bool`, `spread_cooldown: SpreadCooldownState`, `news_alerts: list[NewsEvent]` | HealthMonitor, CalendarService, SpreadMonitor | Workflow, TicketBuilder | `board_mode`変更はRunbook承認必須。`news_alerts`は重大ニュースのタイトルと影響度を保持。 |
| `HealthSignal` | `status: Literal['ok','degraded','soft_stop','hard_stop']`, `reasons: list[HealthReason]`, `recommended_action: RecommendedAction`, `qa: dict[str, str]` | HealthMonitor | CLI `tradectl status`, Reporter, AlertDispatcher | `qa`にQAスコアカード（§0.10）の結果を格納。`recommended_action`はRunbook IDと根拠メトリクスを含む。 |
| `RiskEvaluationResult` | `approved: list[RiskVettedSignal]`, `rejected: list[RejectedSignal]`, `alerts: list[RiskAlert]`, `snapshot: RiskMetricsSnapshot` | RiskManager | TicketBuilder, Audit Service | `snapshot`はCorrelation行列ハッシュとバケット露出を保持。`alerts`はRunbook `RUN-RISK-01`レビューの材料。 |
| `TicketPayload` | `ticket_id: str`, `symbol: str`, `size: Decimal`, `sl: Decimal`, `tp: Decimal`, `ttl_sec: int`, `badges: list[str]`, `checklist: list[ChecklistItem]`, `audit_ref: AuditPointer` | TicketBuilder | CLI Board, Audit Service, Trade Journal | `checklist`はヒューマン入力必須。`audit_ref`で監査ログとの往復を保証。 |

- **データモデル運用ルール**:
  - すべてのモデルは`pydantic` v2ベースまたは`@dataclass(frozen=True, slots=True)`で定義し、イミュータブル性を担保する。
  - 型変更は`docs/change_requests/`で承認後に実施し、`tests/contracts/test_datamodel_hash.py`でスキーマハッシュが更新されたことを確認する。
  - Enum類（`UiHint`, `RiskFlag`, `HealthReason`など）は`docs/schema/enums.md`で集中管理し、Codex依頼時は対象Enumと許容値を明示する。

### 1.5 主要運用シーケンス（トレーダー視点）

1. **通常稼働（Board = normal）**
   1. DataIngestionServiceが`MarketFrame`を`bar_ready_queue`へ投入。
   2. FeaturePipeline→StrategyEngine→ScoringService→RiskManager→PositionSizerが順に実行し、`RiskVettedSignal`を生成。
   3. TicketBuilderが`TicketPayload`を整形し、`tradectl board`がバッジ/チェックリスト付きで提示。承認/却下イベントはAudit Serviceと`logs/events/`に記録される。
   4. Reporterが`metrics/scoring_base.jsonl`や`tickets/*.jsonl`から週次レポートを生成し、POレビューに供する。

2. **Acceptable Degradation（Board = guarded）**
   1. `HealthMonitor.raise('degraded', 'data_latency_fetch')`が発火し、SessionManagerが`board_mode=guarded`へ遷移。
   2. WorkflowはReduce-Only候補に限定し、TicketBuilderが`badges`へ`REDUCE_ONLY`を追加。`RiskVettedSignal.notes['guarded_reason']`で根拠を共有。
   3. Ops担当はRunbook `RUN-DATA-05`に従いフォールバック経路を検証。`QA-05`（§0.10）は`pending`へ変更され、解除条件が満たされるまで保持。
   4. 復旧後、`tradectl board --normal`と`HealthMonitor.ack`を実行し、`degraded_ack`イベントとRunbookサインを残す。`QA-05`は`pass`へ更新し、週次レポートへ所要時間を追記。

3. **Manual CSV補填フロー**
   1. OpsがRunbook `RUN-DATA-06`に従いCSVを二重入力し、`ManualCsvPayload`をCLIで登録。
   2. `ManualCsvIngestionTask`がハッシュ一致を検証し、成功時に`MarketFrame`へ統合。失敗時は`ManualCsvMismatch`例外と`health.changed(reason='manual_csv_mismatch')`を発火。
   3. `metrics/data_ingestion_sla.jsonl`へ`manual_source=true`のレコードを残し、Reporterが週次レポートに補填ログリンクを追記。
   4. Ops Managerは`QA-05`とRunbookサインを確認後、`tradectl board --normal`で解除。Audit Serviceは`manual_csv_ingested`イベントを保管し、将来検証に備える。

- **図面管理**: `docs/diagrams/sequence/normal_flow.mmd`と`docs/diagrams/sequence/degradation_flow.mmd`でシーケンス図を管理し、更新時は`make diagrams`でPNGに変換する。

### 1.6 主要コンポーネントサマリ
| コンポーネント | 主責務 | 対応FR | 実装位置 |
| --- | --- | --- | --- |
| SessionManager | 起動/停止、Catch-up制御、モード切替 | FR-08, FR-16 | `core/session.py` |
| Workflow Orchestrator | バー処理パイプラインの実行 | FR-03, FR-04, FR-05 | `core/workflow.py` |
| EventBus & SnapshotManager | イベント配信と再起動整合 | FR-11, FR-18 | `core/event_bus.py`, `core/snapshot.py` |
| DataIngestionService | データ取得・キャッシュ・フォールバック | FR-01, FR-02 | `data/service.py` |
| StrategyEngine | プラグイン戦略実行 | FR-04 | `strategies/registry.py` |
| ExecutionModel & SpreadMonitor | 滑り補正・ヒューマン遅延・Spread制御 | FR-27, FR-39, FR-41 | `execution/` |
| RiskManager & HealthMonitor | リスク制限・Kill Switch | FR-05, FR-36, FR-22 | `risk/manager.py`, `core/health.py` |
| RiskDisclosureService | リスク開示バナー/同意証跡 | FR-53, FR-54 (M1.1) | `compliance/risk_disclosure.py` |
| TicketBuilder | HITLチケット構築・監査 | FR-07, FR-38 | `ticket/builder.py` |
| Reporter | 週次/日次レポートと可視化 | FR-10 | `reporter/generator.py` |
| ConfigRegistry | 設定ガバナンス・ホットリロード | FR-14, FR-33 | `infra/config.py` |

### 1.7 クロスカッティング懸念
- **同期待ち合わせ**: 非同期ジョブは`AsyncIntervalJob`/`AsyncOneShotJob`で管理し、`max_lag_secs`を超えると`EventLagWarning`→`HealthMonitor`へ通知。
- **安全な更新**: 危険パラメータ変更は`NextBarChangeQueue`で遅延適用し、`cfg_hash`を監査ログに刻印。Kill Switch解除には手動確認フローを強制。
- **可観測性**: `metrics/pipeline.jsonl`/`metrics/cli_perf.jsonl`と`logs/events/*.jsonl`でトレーサビリティを確保し、`tradectl metrics report`でRunbook添付用レポートを生成する。Prometheus互換Exporterはインターフェースのみ実装し、HTTP公開はM2で有効化する。
- **再現性**: Backtest/Paper/Liveで共通のExecutionModel/Spread/Fundingロジックを使い、`mode_context.deterministic_seed`で乱数初期化を固定。
- **拡張ポイント**: SPRT、Reduce-Only Advisor、Slack通知などM2+機能はFeature Flagと依存注入で無効化可能にする。

### 1.8 主な前提と制約
| 分類 | 内容 | リスク・備考 |
| --- | --- | --- |
| 運用前提 | PCは平日日中のみ稼働。夜間/週末停止時は次回起動時にResync必須。 | 無通電期間が48h超の場合は手動でバックフィル期間を短く分割。 |
| 市場データ | Dukascopy/yfinance双方の可用性に依存。API仕様変更時は48h以内にパッチ適用。 | API変更監視をRunbookに追加。 |
| 人的リソース | HITL承認は1人運用。緊急停止時は電話/メールで自己通知。 | 代替要員不在のため長期離席時はKill Switch STOPのまま。 |
| セキュリティ | macOSローカル環境でFileVault/画面ロック、ネットは自宅有線/信頼Wi-Fiのみ使用。 | 公共ネットワーク禁止。VPN利用ポリシーはM2検討。 |
| データ保持 | 生データはParquetで1年分を保持。古いティックは再取得可能という前提。 | Dukascopy停止時はバックアップCSVへの切替を手順化。 |
| バージョン管理 | main/devブランチ運用。Poetryで依存固定。 | ランタイム差異回避のため`poetry lock`更新時はCIで再検証。 |
| SLA | FR KPI達成が主目的。Alert応答はMAJOR:10分、CRITICAL:5分以内。 | 応答遅延時は自己レビューをRunbookに記録。 |
| 将来拡張 | M2でAPI発注/Slack通知/Tauri GUIを追加予定。M1でフック実装済み。 | M2機能を有効化する際はFeature Flagと回帰テストが必須。 |

### 1.9 システム環境・リソース要件
| 項目 | 要件 | 備考 |
| --- | --- | --- |
| ハードウェア | Apple Silicon (M1/M2) or Intel i7 同等、RAM 16GB、SSD空き 20GB以上 | バックテスト並列時は4コア以上推奨。 |
| OS | macOS 13 Ventura 以降 | Python 3.11動作検証済み。将来Linux移植予定。 |
| Python | 3.11.x (pyenv or system) | `python --version`で起動時チェック。 |
| タイムゾーン/NTP | システムTZ=JST。時計誤差±2秒以内を維持（目視確認推奨） | 日次起動前にRunbook `RUN-TIME-01`で`systemsetup`等を確認、`tradectl preflight`はWARNログで支援。 |
| ネットワーク | 下り20Mbps以上、HTTPS(80/443) outbound許可 | Dukascopy/yfinance両方のエンドポイントへ疎通確認。 |
| SMTP | StartTLS対応サーバ（Gmail等） | `.env`で資格情報管理し、試験送信を週次実施。 |
| ストレージ配置 | `~/development/codex_invest/{data,logs,snapshots,metrics}` | バックアップ先は外部SSD/NAS。 |
| 依存ツール | `poetry`, `git`, `make`(任意), `gnu-sed`, `rg` | セットアップは`poetry install`で完結。 |
| 監査バックアップ | 週次フルバックアップ(外部デバイス) + 日次増分 | 復元テストを月次実施。 |

- 起動スクリプトはプレフライトでPython/Poetryバージョン、ディスク残量、SMTP疎通を必須検査とし、NG項目があれば`HealthState=degraded(preflight)`を設定する。NTP同期は推奨検査として実施し、失敗時はWARNログとRunbook参照を案内する。
- `TimeSyncGuard`は`tradectl preflight`内で`systemsetup -getnetworktimeserver`設定をチェックし、未設定の場合は`config.time.ntp_server`を案内する。NTP疎通は`/usr/sbin/sntp -sS <server>`のdry-runで確認し、`clock_drift_ms`が500ms超の場合はWARNログと`health.suggest_guarded(clock_out_of_sync)`イベントを発行する。結果は`metrics/time_sync.jsonl`に追記し、偏差が1500ms/3000msでWARN→MAJORへレベルを引き上げるが、自動ガードは行わない。
- ランタイムでは`AsyncIntervalJob`（10分間隔）が同じ検査を実施し、偏差が閾値内に戻った場合は`health.suggest_resume(clock_out_of_sync)`イベントを出す。復帰条件は`clock_drift_ms<200ms`かつ直近30分のNTP応答率100%を満たしたことをWARNログで示し、最終判断はオペレータが行う。
- Manual CSV取込では`utc_iso`列のタイムゾーンを`pandas.to_datetime(..., utc=True)`で強制し、`ManualCsvReconciler`が`timezone != UTC`を検出した場合は`ManualCsvError(code='clock_mismatch')`で拒否する。拒否ログは`reports/validation_log/AC-45_sla_<date>.md`と`metrics/time_sync.jsonl`へ記録し、再入力要求にはRunbook `RUN-TIME-01`を参照させる。
- VPN/テザリング使用時はSpread遅延が見込まれるため、`config.provider.timeout_sec`や`retry`値を引き上げ、`AlertDispatcher`でWARNを送信する。

### 1.10 運用体制・RACI
| 活動 | R (実行) | A (責任) | C (協議) | I (報告) |
| --- | --- | --- | --- | --- |
| 日次プレフライト/運用 | 運用担当 | プロダクトオーナー | 開発 | セキュリティ |
| 設定変更レビュー | 開発 | プロダクトオーナー | 運用 | セキュリティ |
| アラート対応 (MAJOR) | 運用 | プロダクトオーナー | 開発 | セキュリティ |
| アラート対応 (CRITICAL) | 運用+開発 | プロダクトオーナー | セキュリティ | 全員 |
| リリース判定 | プロダクトオーナー | プロダクトオーナー | 開発・運用 | セキュリティ |
| バックアップ/復旧ドリル | 運用 | プロダクトオーナー | 開発 | セキュリティ |
| Runbook改訂 | 運用 | プロダクトオーナー | 開発 | セキュリティ |
| KPIレビュー | プロダクトオーナー | プロダクトオーナー | 運用・開発 | セキュリティ |

- 代替要員が不在の場合、`runbook/contingency.md`に従って計画休暇・不在時のKill Switch手順を事前申請する。
- 重大障害時は運用→開発→PO→セキュリティの順で通知し、`logs/ops/incident.log`へ時系列を記録する。

## 2. アプリケーションサービス層

### 2.1 SessionManager & ModeController (`src/core/session.py`)
- **主要クラス**: `SessionManager`, `ModeController`, `SessionHandle`。
- **公開API**: `start(profile, mode)`, `catch_up(from_ts=None)`, `shutdown(graceful=True)`, `status()`, `reset_kill_switch()`。
- **状態管理**: `SessionState`に`mode`, `health`, `active_jobs`, `cfg_hash`, `last_bar_ts`を保持。`ModeController`は`ModeContext`（バックテスト: in-memory fill, Paper: 仮想 fills, Live: ユーザー入力CSV）を提供。
- **Catch-up**: `resync_queue`へ`BackfillJob`を投入し、欠損ウィンドウの長さと影響ティッカー数から`priority ∈ {critical, high, normal}`を決定して登録。主要4ペアで30分超欠損が発生した場合は自動的に`critical`を付与し、`provider_priority`を`{cache > dukascopy > yfinance}`へ強制切替する。処理中は`metrics/data_ingestion_sla.jsonl`へ`catch_up_lag_minutes`を追記し、30分超で`HealthMonitor.raise(level='critical', reason='data_latency_catch_up')`を発火。`BackfillJob`が連続3回失敗した場合は24時間ウィンドウを最大4時間単位に分割し直し、再投入前に`ManualCsvIngestionTask`へ手動CSV要求フラグを設定する。完了時は`ResyncCompleted(catch_up_elapsed_sec, recovered_symbols, failover_used)`イベントを発行し、Runbookチェックリストに承認者IDと代替ソース解除時刻を記録する（FR-16, AC-04）。
- **エラーハンドリング**: 重大例外は`HealthMonitor.raise("hard_stop", reason)`を経由しKill Switchを`STOP`に遷移。`graceful=False`でshutdownした場合、再起動時に`soft_stop(manual_review)`から開始。
- **設定依存**: `config.profile_<name>.yaml`と`cfg.schema.json`。Profile切替時は`cfg_hash`を再計算し監査ログへ出力。

### 2.2 Workflow Orchestrator (`src/core/workflow.py`)
- **役割**: トリガー時間足（M1:5分）に同期したバー処理ループの進行。`PipelineStep`の連鎖を構築し、各ステップの処理時間をメトリクスに記録。
- **実装**: `asyncio`ベースで`AsyncIntervalJob`としてスケジュール。Catch-up時は`fast_forward`モードで順次処理し、途中で`HealthMonitor`ステータスをチェック。
- **例外処理**: 各`PipelineStep`は`PipelineError`を投げ、オーケストレータが`HealthMonitor`へ通知。`retry_policy`を設定可能（既定は1回リトライ後soft_stop）。
- **Backpressure**: `max_concurrent_steps`で同時実行数を制御し、過負荷時は`WorkflowLag`イベントを発生させKill Switchの判断材料とする。

### 2.3 Scheduler (`src/core/scheduler.py`)
- **コンポーネント**: `AsyncIntervalJob`, `AsyncOneShotJob`, `JobRegistry`。
- **責務**: Intervalジョブ（バー処理、Spread監視、Funding更新）とOneShotジョブ（Resync、レポート生成、バックテスト）を統合管理。ジョブのキャンセル/再スケジュールをサポート。
- **監視**: `metrics/scheduler.jsonl`へ`enqueue_ts`, `start_ts`, `end_ts`, `status`を記録。遅延が`config.scheduler.lag_warn_sec`を超えると`SchedulerLagWarning`イベントを発火。

### 2.4 EventBus & SnapshotManager (`src/core/event_bus.py`, `src/core/snapshot.py`)
- **EventBus**
  - `publish(event)`でdataclass → `orjson` → `logs/events/YYYYMMDD.jsonl`へ追記。同時に`asyncio.Queue`にpushしCLI/Reporterがsubscribe。
  - `subscribe(event_type, filter_fn=None)`は非同期ジェネレータ。購読解除は`async with`文で保証。
  - 書き込み遅延>500msで`EventLagWarning`。ファイルハンドラは日跨ぎでローテーション。
- **SnapshotManager**
  - `persist(snapshot)`は`tmp`ファイル経由でアトミックに保存。`cfg_hash`と`data_hash`を付与。
  - `restore()`は最終スナップショットを読み込み、`health.status in {soft_stop, hard_stop}`の場合は`Paused`状態で起動しCLIに復旧手順を提示。
  - `compare_hash(data_hash)`でResync後のデータ整合性を検証し、差異があれば`DataMismatch`イベントを発行（FR-32）。

### 2.5 HealthMonitor / Kill Switch (`src/core/health.py`)
- **状態遷移**: `ok → degraded → soft_stop → hard_stop`。戻り条件はRunbookで管理し、Kill Switchは`RUNNING | STOP`を保持する。M1 Coreでは遷移判定をログ出力に留め、Opsが手動で状態を確定する。
- **BoardMode遷移**: `normal`（既定）→`guarded`→`halted`のシーケンスをサポートするが、M1 Coreは`HealthMonitor`が`HealthState`とNTP逸脱を監視して`health.suggest_guarded`/`health.suggest_resume`イベントを発行し、オペレータが`tradectl board --guarded`/`--normal`で反映する。自動復帰はM1.1で有効化予定。`guarded`状態の証跡として承認ログに`degraded_ack`が必須。
- **入力イベント**: `RiskAlert`, `DataQualityAlert`, `SpreadCooldown`, `ConfigRejected`, `SnapshotCorrupted`, `HeartbeatTimeout`。
- **出力**: `HealthStateChanged`（手動反映結果）、`KillSwitchChanged`（手動操作）、`AlertEvent`。
- **SPRT (M2+)**: `SPRTAlert`受信時に`soft_stop`へ移行しReduce-Onlyを発動。
- **運用対応**: CLI `tradectl status`で理由/解除条件を表示。`--ack <id>`で承認ログを取った後Kill Switch解除可能。`tradectl board --guarded`/`tradectl kill-switch set --mode <state>`で手動操作し、`audit`に承認者を記録する。
- **Acceptable Degradation管理**: `health.status=degraded`発生時に`health.suggest_guarded`イベントを出力し、OpsチームがRunbook `RUN-DATA-05`/`RUN-DATA-06`に従って`BoardMode=guarded`へ手動切替・代替ソース選択・`degraded_ack`登録を行う。`health.status=degraded`が**連続3営業日**または**ローリング30日で2回**発生した場合は`health.escalate`イベントでレビューを通知し、**5営業日**超継続または週次KPIレビュー2回未解消の場合はKill Switch `hard_stop`昇格を手動判断する。復帰時は`catch_up_lag_minutes<30`、`metrics/data_ingestion_sla.jsonl`で`fetch_p95`/`processing_p95`が目標以内、`tradectl benchmark validate-manual`結果一致、PO/Opsダブルサインを`reports/validation_log/AC-45_sla_<date>.md`へ記録する。Kill Switch自動昇格はM1.1で再評価する。

### 2.6 CLI (`src/interfaces/cli/*.py`)
- `tradectl board`: EventBus購読でTicket表示。`--filter`, `--view`, `--format json`（将来）を提供。TTL/ドリフトをリアルタイム更新し、Spreadクールダウンやニュースブロック理由をバッジ表示。`RiskMetricsSnapshot`を購読し、`R_eff`超過時はヘッダに赤バナー（`R_eff=2.8 (>2.5)`等）と通貨バケット別エクスポージャ表を表示する。Acceptable Degradation中は`BoardMode=guarded`を手動選択できるよう橙色バナーと代替ソース（dukascopy/yfinance/manual_fallback）バッジ、ダブルチェック入力を提示し、承認操作時に`degraded_ack`イベント記録とRunbookリンクを表示する（自動切替は行わない）。将来のCorrelation Guard本体と整合させるため`correlation_snapshot`ペイロードをそのまま`board`へ受け渡すIFを先行実装し、M1.1ではReduce-Only提案リンクを追加するだけで済む構造とする。
  - **リスク開示分岐**: `RiskDisclosureService.fetch_state()`で承諾状況を取得。M1 Coreでは`state.status in {'pending','expired'}`の際にヘッダへ警告バナーと承諾誘導リンクを表示し、`board_mode='read_only'`で承認/却下コマンドに`warn_only`フラグを付与する。M1.1以降は同条件でCLIを一時停止し、`RiskDisclosureService.prompt()`が同意ダイアログを起動。承諾完了まで`BoardRenderer`は`render_locked()`で「同意待ち」画面を表示し、高リスク操作（Approve/Kill Switch/Emergency）は`ConsentRequiredError`でブロックする。
- `tradectl data ...`（`src/interfaces/cli/data.py`）: 手動フォールバックオペレーションの専用CLI。`ManualCsvIngestionTask`/`ManualCsvReconciler`と直結し、Acceptable Degradation時のRunbook `RUN-DATA-05`/`RUN-DATA-06`の各手順をCLI内で誘導する。サブコマンドは以下の通り。
  - `manual-template --provider <name> --symbol <pair> --date <YYYY-MM-DD> --timeframe {m5,h1}`: 双子CSV雛形（`fallback_<provider>_<symbol>_<tf>_<YYYYMMDD>_{op,review}.csv`）を`data/manual_fallback/<provider>/<symbol>/<YYYYMMDD>/`へ生成し、UTC/JSTヘッダを自動記入。5分足の場合は`HH:MM`が5分刻みで昇順となるスケルトンを出力する。生成時に`RunbookStepCompleted(task="RUN-DATA-05.step2")`イベントを記録し、`metrics/rate_limit_window.jsonl`へ手動切替タイムスタンプを追記する。
  - `validate-csv --path <dir> [--provider <name>] [--symbol <pair>] [--date <YYYY-MM-DD>]`: `ManualCsvReconciler`を呼び出し、(a) UTC/JST相互変換の整合、(b) 5分足/1時間足境界チェック（先頭バーが`00/05/10...`、タイムゾーン境界で欠損なし）、(c) `low ≤ open,close ≤ high`、(d) 双子CSV（`op`/`review`）のSHA256ハッシュ一致を検証。`ManualCsvIngestionTask`が`bar_ready_queue`へ投入する前提条件としてExit code 0を要求し、不一致はExit code 120で`RUN-DATA-06.step4`を未完に設定する。結果サマリは`reports/validation_log/manual_csv_<provider>_<symbol>_<YYYYMMDD>.md`にMarkdownで追記し、ハッシュ値は`logs/ops/manual_csv.log`と`metrics/rate_limit_window.jsonl`へ同期書込する。
  - `jobs --pending/--all`: `ManualCsvIngestionTask`キューの状態を表示し、`ManualCsvReconciler`が未完了のシグナル（`status=pending_review`）を強調。Runbook `RUN-DATA-05.step3`で要求される「手動補填中の通貨ペア一覧」をCLI出力から転記できるよう、`--export-json`で`reports/validation_log/manual_jobs_<date>.json`を生成する。
  - `manual-report --date <YYYY-MM-DD> [--provider <name>] [--symbol <pair>] [--attach <path>]`: `ManualCsvReconciler.generate_report()`を呼び出し、`ManualCsvIngestionTask`のレビュー履歴と検証結果を集約したMarkdownを`reports/validation_log/manual_summary_<YYYYMMDD>.md`へ作成。Runbook `RUN-DATA-06.step6`のチェックボックスと、Opsワークロードログ（`ops_worklog.jsonl`）へ`{"task":"manual_fallback_review","duration_min":<入力値>}`を追記する。`--attach`で外部根拠ファイルを`reports/validation_log/attachments/`にコピーし、パスをレポート末尾に挿入する。
  - `hash --path <dir>`: 双子CSVのSHA256ダイジェストと、時刻/価格列の差分サマリを表示。`ManualCsvReconciler.compute_hash_pair()`を直接実行し、`ManualCsvIngestionTask`が参照する`manual_hash.json`を更新。`RUN-DATA-06.step3`完了時にCLIが`reports/validation_log/hash_audit_<provider>_<symbol>_<YYYYMMDD>.json`を保存し、Runbookチェックリストへ添付すべきファイルパスを標準出力へ明示する。
  - `rate-limit stage inspect [--provider <name>] [--window <hours>]`: `RateLimitGuard.snapshot()`を読み込み、現在のStage/429発生率/連続カウント/推奨ステージを表形式で表示。`--window`指定でローリング評価期間（既定24h）を変更する。Acceptable Degradation宣言中は警告バナーと`RUN-DATA-05#rate_limit_guard`リンクを表示する。
  - `rate-limit stage set <stage> --provider <name> --reason <text> [--dry-run]`: Stage変更提案の適用。`--dry-run`時は`RateLimitSuggestion`との乖離を表示し、Exit code 3で差異有りを通知。実際の変更時はRunbookチェックリストIDと操作者イニシャルを入力させ、`logs/audit/rate_limit.jsonl`と`metrics/rate_limit_window.jsonl`へ記録する。Stage変更後に`ProviderFetchWorker`へ再設定イベントをブロードキャストし、手動CSVキューが存在する場合は警告する。
- `tradectl ticket approve|reject|edit`: `TicketAction`イベントと監査ログ追記。`edit`は複数フィールド同時更新を許可し、バリデーションエラー時は差分と原因を表示。
- `tradectl status`: HealthState, Kill Switch, Snapshot Hash, SpreadCooldown, 未処理リスクフlagを表示。
- `tradectl events tail`: event_type絞り込みと`--since`指定。
- `tradectl export`, `tradectl resync`, `tradectl spread inspect`: 運用補助。`resync`は進行状況をProgress Bar表示。

### 2.7 プレフライト & ランタイムモニタ (`src/app/telemetry.py`, `src/core/health.py`)
- **プレフライトチェック** (`tradectl preflight`, 起動時自動実行)
  1. Python/Poetryバージョン整合 (`python3 --version`, `poetry --version`)
  2. ディスク残容量 (`threshold=5GB`) と書込権限確認
  3. NTP同期状態（推奨チェック: `systemsetup -getnetworktimeserver`, `/usr/sbin/sntp -sS <server>`のdry-run）
  4. SMTP疎通テスト（メール送信ドライラン）
  5. `config/profile`と`cfg.schema.json`の整合検査
  6. 直近バックアップ日付 (`logs/ops/backup.log`) の検証
  -> 必須項目（1,2,4,5,6）が失敗した場合は`HealthState=degraded(preflight)`とし、CLI/メールで通知。NTP推奨チェック（3）は失敗時にWARNログとRunbook `RUN-TIME-01`参照を提示する。
- **ランタイムモニタ**
  - `telemetry.HeartbeatTask`: 30秒ごとに処理遅延/CPU/メモリを`metrics/pipeline.jsonl`へ記録。
  - `PreflightReminder`: プレフライト未実施状態で`tradectl start`した場合、初回バー処理前に警告。
  - `BackupReminder`: `logs/ops/backup.log`の最終更新から7日超過でWARNを発行。
- **手動実行**: `tradectl preflight --silent`で結果をJSON, `tradectl preflight --export path`で報告書を出力。

## 3. ドメインサービス詳細

以下、主要サービスごとに公開API・入力/出力・主アルゴリズム・エラーハンドリング・設定項目を記載する。

### 3.1 DataIngestionService (`src/data/service.py`)
- **公開API**: `fetch_latest(symbols, timeframe)`, `backfill(symbols, timeframe, start, end)`, `warm_cache()`に加え、起動/停止時に`spawn_provider_workers()`/`drain_buffers()`を呼び出す。
- **入力**: `MarketRequest`（symbol, timeframe, start, end, provider_priority）、`config.provider.*`、`config.ingestion.buffer_maxsize`、`config.ingestion.buffer_timeout_sec`。
- **出力**: `MarketFrame`（5分/1時間）。1時間足は5分足を集約して生成し、**整合済みバーのみ**が`Workflow Orchestrator`の`bar_ready_queue`へ投入される。
- **アルゴリズム**: symbol×provider単位で`asyncio.Queue(maxsize>1)`を保持し、`ProviderFetchWorker`がAPI取得→生データをキューへ投入。`ProviderParseWorker`が内部`AsyncBuffer`で整形・UTC整列し、`DataQualityGuard`チェック合格までバッファに保持する。`BufferCoordinator`が`Queue.get()`にタイムアウトを付与し、取得/パースが滞留した場合は`fetch_delay`と`processing_delay`を分離記録する。フォールバックは`ProviderFallbackPolicy`が**再試行間隔と手動CSV移行をそれぞれ`FallbackRetryTask`/`ManualCsvIngestionTask`へ委譲**し、メインパイプラインから分離する。
- **RateLimit制御**: すべての取得リクエストは`RateLimitGuard.acquire(provider, symbol)`を経由し、段階別トークンバケット（§3.1.1）で発行する。`acquire`は`PollStage`に応じたジッター付きディレイ（Stage0: `Uniform[12,15]`sec, Stage1: `Uniform[11,14]`sec, Stage2: `Uniform[10,12]`sec）を算出し、取得ジョブへawaitさせる。429/403検知時は`RateLimitGuard.observe(rate_limit_event)`を呼び、ローリング1hの発生率/連続回数を更新する。
- **ManualCsvIngestionTask**: `data/manual_fallback/<provider>/<symbol>/<YYYYMMDD>/fallback_<provider>_<symbol>_<tf>_<YYYYMMDD>_{op,review}.csv`の双子入力を必須とし、`ManualCsvReconciler`が差分チェック・SHA256ハッシュ生成・承認者イニシャル検証を実施。ハッシュ一致とRunbook `RUN-DATA-06`の承認チェックが完了するまで`bar_ready_queue`への投入をブロックし、`reports/benchmark/manual_log_signoff/<YYYYMMDD>.md`と`logs/ops/manual_csv.log`へ証跡を残す。CLI `tradectl benchmark validate-manual --path data/manual_fallback/<provider>/<symbol>/<YYYYMMDD>/`が検証コマンドとして実装され、非一致時はExit code 120でKPI更新を抑止する。
- **内部バッファ**: `AsyncBufferSlot`は最新バーと`quality_flag`を保持し、Quality Guardで`status=reconciled`となったものだけが`bar_ready_queue`へコミットされる。未整合バーは`AsyncBuffer`内で再検証するため、シグナル側での欠損判定は不要。
- **エラーハンドリング**: Provider失敗で`ProviderError`→`FallbackRetryTask`が指数バックオフで再取得をスケジュール。全失敗で`DataSourceDown`→`HealthMonitor.degraded(fetch_delay)`。パース失敗やQuality Guard不合格は`processing_delay`として記録され、`processing_timeout`超過時にのみKill Switchへ伝搬する。
- **設定**: `config.cache.ttl_hours`, `config.provider.retry`, `config.provider.timeout_sec`, `config.ingestion.buffer_maxsize`, `config.ingestion.fetch_timeout_sec`, `config.ingestion.processing_timeout_sec`。
- **遅延メトリクス**: `fetch_delay_sec = (queue_enqueue_ts - request_ts)`、`processing_delay_sec = (bar_ready_ts - queue_enqueue_ts)`を算出し、`metrics/data_ingestion_sla.jsonl`に`phase=fetch|processing`ラベルで記録。閾値（既定: fetch≤18秒、processing≤12秒）は`config.ingestion.sla.fetch_p95_sec`/`config.ingestion.sla.processing_p95_sec`で制御し、超過時は`HealthMonitor.raise('degraded','data_latency_fetch|process')`を行う。Prometheus Exporterでは`data_ingestion_delay_seconds{phase,symbol,provider}`として公開。
- **Runbook連携**: 遅延アラート発生時はEventBusで`ingestion.latency_exceeded`を発火し、Runbook手順`RUN-DATA-05`（フォールバック調整）/`RUN-DATA-06`（手動補填）を通知。`FallbackRetryTask`/`ManualCsvIngestionTask`の完了を`tradectl data jobs --pending`で確認し、二重入力CSVは`tradectl benchmark validate-manual`の結果（ハッシュ一致・承認サイン）をRunbookチェックリストへ添付する。`make sla-report`出力（`reports/validation_log/AC-45_sla_<date>.md`）と合わせて`RUN-POST-03`に従い事後レビュー（原因/再発防止）を`logs/ops/review.log`へ追記する。

#### 3.1.A Codex実装契約と拡張境界

| 関数/メソッド | シグネチャ（型ヒント必須） | 主な例外/戻り値 | 必須テスト/フィクスチャ | 拡張ポイント・備考 |
| --- | --- | --- | --- | --- |
| `fetch_latest` | `async def fetch_latest(self, symbols: list[str], timeframe: Timeframe) -> dict[str, MarketFrame]` | `ProviderError`, `DataSourceDown`; 正常時はシンボルごとの`MarketFrame` | `pytest -k data_pipeline::test_fetch_latest_success`, `pytest -k data_pipeline::test_fetch_handles_rate_limit` | `ModeContext`でBacktest/Paper/Liveのキャッシュ経路を切替。M1.1でWebSocket追加予定のため戻り値はdict固定。 |
| `backfill` | `async def backfill(self, symbols: list[str], timeframe: Timeframe, start: datetime, end: datetime) -> BackfillReport` | `BackfillTimeout`, `ManualCsvRequired`; レポートは`bars_loaded`, `fallback_used`等を含む | `pytest -k data_pipeline::test_backfill_gap_detection`, `scripts/qa/manual_csv_smoke.sh` | `BackfillReport`に`segments: list[BackfillSegment]`を含め将来の部分再実行を許容。 |
| `warm_cache` | `async def warm_cache(self, symbols: list[str]) -> None` | `CacheWarmupError` | `pytest -k data_pipeline::test_warm_cache_populates` | キャッシュを`data/cache/<provider>/<symbol>.parquet`に保存。M2でRedis化する際もAPI変更なし。 |
| `spawn_provider_workers` / `drain_buffers` | `async def spawn_provider_workers(self) -> None` / `async def drain_buffers(self) -> None` | `WorkerSpawnError`, `BufferDrainTimeout` | `pytest -k data_pipeline::test_worker_spawn_guardrails` | `spawn_*`は`asyncio.TaskGroup`で実装し将来WebSocketへ移行可能にする。`drain_buffers`は終了時のGraceful shutdown手順。 |
| `ingest_manual_csv` | `async def ingest_manual_csv(self, payload: ManualCsvPayload) -> ManualCsvResult` | `ManualCsvMismatch`, `ManualCsvMissingTwin` | `pytest -k data_pipeline::test_manual_csv_double_entry`, `scripts/qa/manual_csv_smoke.sh` | `ManualCsvPayload`は`path_op`, `path_review`, `symbol`, `timeframe`を保持。M1.1でGUI導線を追加予定。 |
| `snapshot_state` | `def snapshot_state(self) -> IngestionSnapshot` | 例外なし（不変データを返却） | `pytest -k data_pipeline::test_snapshot_roundtrip` | Snapshotは`AsyncBuffer`のヘッド・Stage情報を含む。`SessionManager`のスナップショット復元APIで利用する。 |

- **実装ガイド**:
  1. Codexに渡す際は`ManualCsvPayload`/`BackfillReport`等の`@dataclass`定義を先頭に提示する。
  2. `RateLimitGuard`との結合は`acquire/observe`のみに限定し、`TokenBucket`内部構造へアクセスしない。将来`rate_limit`モジュールを差し替えても変更を局所化できるようにする。
  3. エラーメッセージはRunbook検索キーワード（例: `data_latency_fetch`, `manual_csv_mismatch`）を含める。

#### 3.1.1 RateLimitGuard & Polling Stage Evaluator (`src/data/rate_limit.py`)
- **目的**: 無償フィード(yfinance)の帯域制限を管理し、429/403レートリミット発生率を監視したうえで段階的ポーリング間隔（Stage0/1/2）を手動で運用する。自動遷移はM1.1以降の検討事項とし、M1 Coreでは測定・提案・Runbookログ連携に徹する。
- **公開API**: `acquire(provider, symbol) -> Awaitable[None]`, `observe(event: RateLimitEvent)`, `snapshot() -> RateLimitSnapshot`, `set_stage(provider, stage, actor)`, `suggest_stage(provider) -> RateLimitSuggestion`, `record_manual_action(provider, stage, actor, reason)`。
- **内部構造**: `RateLimitState`（`stage`, `tokens_per_minute`, `burst_tokens`, `jitter_range`, `rolling_1h_429_rate`, `consecutive_429`, `last_stage_change_ts`, `manual_actor`, `manual_reason`）をprovider単位で保持。`TokenBucket`は`tokens_per_minute`と`burst_tokens`から初期化し、`acquire`時に即時消費できない場合はStageごとのジッターを適用してawaitする。
- **ステージ定義**:
  | Stage | ポーリング間隔分布 | `tokens_per_minute` | `burst_tokens` | 昇格基準（手動適用条件） | 退行基準 | 備考 |
  | --- | --- | --- | --- | --- | --- | --- |
  | 0 | `Uniform[12,15]` 秒 | 20 | 5 | 初期状態。7日間連続稼働し、ローリング1hの429発生率≤1.0%、連続429<3回を確認。 | 429率>1.5% または連続429≥3回 | Acceptable Degradation判定時はこのStageに戻す。 |
  | 1 | `Uniform[11,14]` 秒 | 24 | 6 | Stage0条件を満たしOpsレビューで承認後。レビューではRunbook `RUN-DATA-05`の`rate_limit_stage_eval`チェックを完了し、`metrics/rate_limit_window.jsonl`の統計を添付。 | 同上（閾値越えで即座にStage0へ戻す） | Stage1は最長14秒を維持し429率が低い場合のみ暫定許可。 |
  | 2 | `Uniform[10,12]` 秒 | 30 | 8 | Stage1で7日間連続基準内、かつOps/POダブルサイン済み。 | 429率>1.2% または連続429≥2回 | Stage2はPoC用途。Acceptable Degradationでは必ずStage0へロールバック。 |
- **評価ロジック**: `RateLimitGuard.observe`は429/403イベントを`RateLimitWindow`へ累積し、1分バケットで`rolling_1h_429_rate`と`consecutive_429`を更新。`RateLimitStageEvaluator`（Scheduler 15分間隔ジョブ）が`snapshot()`を読み取り、昇格/退行条件を判定して`RateLimitSuggestion`（`suggested_stage`, `reason`, `metrics_summary`）を生成する。提案はEventBus `rate_limit.suggest_stage`にpublishし、CLI/メールで通知する。
- **メトリクス/監査**: `metrics/rate_limit_window.jsonl`に`{ts, provider, stage, tokens_remaining, rolling_1h_429_rate, consecutive_429, suggested_stage, manual_override, runbook_step}`を追記。Runbook `RUN-DATA-05`/`RUN-DATA-06`の手動操作では`record_manual_action`を必ず呼び、`reports/validation_log/AC-45_sla_<date>.md`へステージ判定理由とハッシュをリンクする。
- **CLI連携**: `tradectl data rate-limit stage inspect`が現在の`stage`と直近24hの429統計を表示。`tradectl data rate-limit stage set <stage> --provider yfinance --reason <text>`はRunbook承認後のみ使用でき、実行時に`RateLimitGuard.set_stage`を呼び出し監査ログ（`logs/audit/rate_limit.jsonl`）へ記録する。`--dry-run`で提案との差分を確認可能。Stage変更後は`ManualCsvIngestionTask`の待機中ジョブを再計画し、`RateLimitGuard`が`max_concurrent = ⌊tokens_per_minute / (60 / mean_interval)⌋`を再計算して`ProviderFetchWorker`へ伝搬する。
- **HealthMonitor連携**: 429退行基準を超えた場合は`HealthMonitor.raise('degraded','rate_limit_stage')`を呼び、`recommended_action='runbook:RUN-DATA-05#rate_limit_guard'`を付与する。Acceptable Degradation期間中はStageを0へ戻したうえで`ManualCsvIngestionTask`の準備手順を案内する。
- **将来拡張**: M1.1では`auto_transition_enabled` Feature Flagで`RateLimitStageEvaluator`に自動適用を委譲する余地を残し、テストケースとRunbook承認フローを整備する。M2ではプロバイダ別のポーリングプロファイル（Dukascopy高速取得）を同一機構に統合する計画。

### 3.2 DataQualityGuard (`src/data/quality.py`)
- **公開API**: `validate(frame)`, `report()`, `compare(reference_series)`。
- **ルール**: 連続欠損>1バーまたは欠損率>0.5%で`DataQualityAlert`。Z-score>5、スプライン乖離>3σで`quality_flag`=1し除外。外れ値は`anomaly_log`へ出力。
- **補正/隔離**: 軽微欠損はforward-fill後`quality_flag`=2。重大欠損は`KillSwitch`を`soft_stop(data_quality)`へ遷移し、当該区間を`quarantine`ラベルで隔離。
- **ドリフト検知**: 5分/1時間足でヒストリカル平均からの乖離が`config.data_quality.drift_ppm`超過した場合に`DataDriftAlert`を発火。連続3回で`HealthMonitor`が`soft_stop(data_quality)`に遷移しニュース/Spreadガードを強化。
- **イベントアノテーション**: 介入・災害など特異イベントは`data/annotations/<date>_<event>.yaml`に記録し、バックテスト時に該当期間を除外または重み調整。
- **レポート**: `reports/data_quality/<date>.md`に欠損率/外れ値/ドリフト統計を出力し、週次QAレビューで確認。

### 3.3 FeaturePipeline (`src/features/pipeline.py`)
- **公開API**: `update(market_frame)`, `rebuild_range(symbols, start, end)`, `get_feature_frame(symbol)`。
- **処理**: `resample`でマルチTF生成→`IndicatorSet`計算（MA/EMA/RSI/MACD/ATR/BB/Donchian）。差分更新で最新バーのみ再計算し、バックフィル時は指定範囲を再生成。
- **最適化**: pandas rolling共有、Numba optional。GPUサポートはM3候補。
- **エラーハンドリング**: 指標計算失敗で`IndicatorError`発生→リトライ後も失敗なら`HealthMonitor.hard_stop(indicator)`。

### 3.4 RegimeDetector (`src/features/regime.py`)
- **公開API**: `update(feature_frame)`, `current_state()`。
- **アルゴリズム**: ADX, TrueRange, 標準偏差, 自己相関, 平均リターンを0-1正規化→重み付き合算→Softmax。ヒステリシスにより急峻な切替を抑制。
- **出力**: `RegimeState`（mode, volatility, score, history）。変化時は`RegimeChanged`イベントを出す。

### 3.5 StrategyEngine (`src/strategies/registry.py`)
- **公開API**: `run_all(strategy_context)`, `register_plugin`（デコレータ）
- **入出力**: `StrategyContext`（FeatureContext, RegimeState, GateState, AccountState, Config）→`Iterable[RawSignal]`。
- **プラグイン**: M1で`ma_rsi`, `donchian_breakout`。`metadata.required_features`でFeature不足を検知。`cooldown_bars`で連続エントリーを抑止。
- **安全性**: 戦略から返却されたシグナルは`SignalSchema`で検証。レジーム不一致やGateStateブロック時は自動Reject。

### 3.6 ExecutionModel & SpreadMonitor (`src/execution/model.py`, `src/execution/spread.py`)
- **公開API**: `ExecutionModel.apply(raw_signal, market_snapshot, spread_state)`, `SpreadMonitor.update(spread_frame)`。
- **入力**: `execution_model.yaml`, `SpreadMetrics`, `RegimeState`, `config.execution.*`。
- **アルゴリズム**:
  - **M1 Core**ではヒューマン遅延Δtと滑り補正を`execution_model.yaml`および`config.execution.*`に保持した平均値（例: `execution.human_delay_secs`, `execution.slippage_mean_pips`）で決定し、`MarketFrame`終値を基準に`expected_entry`と`expected_slippage`を算出する。Marketable Limit保護は`protection_pips`定数で指値/TTLを決定し、`ttl_seconds`は`execution.human_delay_secs + execution.ttl_buffer_sec`として決定論的に返す。
  - **M1.1以降**はヒューマン遅延を`distribution.human_delay`から抽出し、滑り補正をシンボル×レジーム毎のp10/p50/p90から補間する拡張に差し替える。
  - SpreadMonitorはローリング分位で`SpreadCooldownState`を算出し、`gate_state.spread_cooldown`を更新。
- **出力**: `ExecutionAdjustments`（expected_entry, expected_slippage, fill_style, ttl_seconds, drift_guard_R）、`SpreadState`。
- **M1 Core整合性**: `ExecutionAdjustments`の全フィールドを決定論的に供給し、Risk Manager/PositionSizer/Scoringが`expected_entry`/`ttl_seconds`を必須前提として参照できるようにする。M1.1で確率分布化する際も同じAPIシグネチャを維持する。
- **エラーハンドリング**: Spreadデータ欠損で`SpreadDataDegraded`→`HealthMonitor.degraded`。Market snapshot不足は該当シグナルを拒否。

### 3.7 ScoringService (`src/scoring/basic.py`, `src/scoring/hybrid.py`, `src/scoring/stability.py`, `src/scoring/ranking.py`)
- **公開API**: `rank(raw_signals, performance_stats, penalties)`。
- **アルゴリズム（M1）**: `base_score = α·expected_R + β·PF_all − δ·drawdown_penalty − ε·spread_penalty`。既定係数は`α=0.6, β=0.4, δ=0.1, ε=0.05`。`drawdown_penalty`はバックテスト統計の最大DDから算出し、`spread_penalty`はSpread Monitorから供給。
- **アルゴリズム（M2+）**: `hybrid_score = w_recency·PF_recent + w_global·PF_all − λ·DD_all − γ·(1-Stability) − δ·swap_penalty − ε·spread_penalty`。`Stability`は±10%パラメータ摂動で再計算し、`stability_cache.parquet`に保持。Feature Flag `scoring.hybrid_enabled`が真の時のみ適用。
- **制約**: `config.scoring.max_signals_per_symbol`で上限管理。スコア閾値未満は`RejectedSignal(low_score)`として破棄。ハイブリッド有効時は`RankedSignal.hybrid_components`を監査ログへ出力し、M1では`base_components`のみ出力。
- **モニタリング**: M1は`metrics/scoring_base.jsonl`にランキング結果と係数を記録。M2+では`metrics/scoring_hybrid.jsonl`へ構成要素を出力し、AC-07〜AC-09/AC-16用の統計値（PF_recent, PF_all, Stability Score, ランク反転率）をダッシュボードへ提供。

### 3.8 RiskManager (`src/risk/manager.py`)
- **公開API**: `evaluate(ranked_signals, context)`, `kill_switch_state()`, `capture_snapshot()`。
- **内部状態**: `CurrencyBucketExposure`（`{bucket, gross_R, net_R, position_count}`）、`CorrelationMatrix`（30日ローリング）、`RiskMetrics`（`r_eff`, `max_bucket`, `drawdown`, `margin_buffer`）。`capture_snapshot()`は`data/correlation/<YYYYMMDD>/risk_snapshot.parquet`へ書き出し、最新行を`data/correlation/latest.parquet`へハードリンクする。
- **チェック順序**:
  1. `GateState`（ニュース/祝日/Spread/ReduceOnly）。
  2. Kill Switchが`STOP`ならReject。
  3. `AccountState.running_pnl_daily/weeky`で閾値判定（日次-2.5%, 週次-5%）。
  4. `AccountExposureCache.rebuild()`で通貨バケット別エクスポージャを算出し、`config.correlation.bucket_limits`と比較。
  5. `CorrelationMatrixBuilder.compute(exposures, history_window=30d)`でシンボル相関行列を更新し、`EffectiveRiskCalculator.calculate(ranked_signals, exposures, correlation_matrix)`から`R_eff`を取得。閾値（既定2.5）を超えたら`RiskAlert(type='r_eff')`と`RiskMetricsSnapshot`イベントを発火し、Signal Boardへ通知する。M1 Coreでも`CorrelationGuard`未導入時はRisk Managerが簡易的にR抑止（`signal.blocked_reason='r_eff'`）を付与する。
  6. `SpreadMetrics`と`RiskPolicy.spread_max_pips`比較。
  7. `margin_estimate` vs `available_margin`。
  8. SPRT（M2+）。
- **出力**: `RiskVettedSignal`、`RiskAlert`（`drawdown`, `bucket_limit`, `r_eff`, `margin`）、`RiskMetricsSnapshot`（`bucket_exposures`, `correlation_matrix_hash`, `r_eff`, `ts`）。Reject理由は`risk_flags`に列挙し、Signal Boardがインラインで表示できるよう`ui_hints`（`severity`, `bucket`, `r_eff_delta`）を添付する。
- **Kill Switch**: 連続ドローダウンで`soft_stop(drawdown)`→Spread/CorrelationによるReduce-Only提案（M2+）を指示。`r_eff`逸脱が継続する場合はKill Switchへ`reason='r_eff_guard'`を伝搬し、解除時は`RiskMetricsSnapshot`の`r_eff<=threshold`が2バー連続で確認できたことを条件とする。
- **資本整合性チェック**: `RiskPolicy`に`base_capital_jpy`と`trade_frequency_estimate`を保持し、月次ジョブ`RiskSimulationJob`（CLI: `tradectl risk simulate --trials 10000 --horizon 252d`）が最新Paper実績（勝率/平均R/相関）をサンプルしてモンテカルロ試算を実行する。`Prob(max_drawdown>15%)`と`Prob(equity<0.8·base_capital)`を計算し、閾値（0.25/0.05）を超えた場合は`health.raise('degraded','risk_capital_gap')`→Kill Switchレビューをトリガーする。結果は`reports/risk/capital_adequacy/<YYYYMM>.md`へMarkdown出力し、PO＋Ops ManagerがRunbook `RUN-RISK-01`の月次レビュー節でサインする。

#### 3.8.A Codex実装契約とレビュー観点

| 関数/メソッド | シグネチャ | 主な例外/戻り値 | テスト観点 | 拡張ポイント |
| --- | --- | --- | --- | --- |
| `evaluate` | `def evaluate(self, ranked: Iterable[RankedSignal], context: RiskContext) -> RiskEvaluationResult` | `KillSwitchEngaged`, `RiskPolicyBreach`; 結果は`approved`, `rejected`, `alerts`を含む | `pytest -k risk_manager::test_r_eff_guard`, `pytest -k risk_manager::test_bucket_limits`, `pytest -k risk_manager::test_reduce_only_recommendation` | `RiskEvaluationResult`に`ui_hints`と`audit_payload`を含め、M1.1でSPRTやReduce-Only自動化を追加しても互換。 |
| `kill_switch_state` | `def kill_switch_state(self) -> KillSwitchState` | 例外なし、`status`, `reason`, `since`を返す | `pytest -k risk_manager::test_kill_switch_state_snapshot` | `KillSwitchState`は`FeatureFlag`で将来`suggested_action`を追加する余地。 |
| `capture_snapshot` | `def capture_snapshot(self) -> RiskSnapshot` | `SnapshotWriteError` | `pytest -k risk_manager::test_snapshot_roundtrip`, `pytest -k risk_manager::test_snapshot_file_integrity` | `RiskSnapshot`は`correlation_matrix_hash`を保持し、M2で外部モニタリングに送信可能。 |
| `acknowledge_alert` | `def acknowledge_alert(self, alert_id: str, actor: str) -> None` | `AlertNotFound`, `AlreadyAcknowledged` | `pytest -k risk_manager::test_acknowledge_alert_audit` | 監査ログ`logs/audit/risk.jsonl`へ`ack_actor`, `ack_ts`を書き出す。M1.1でUI承認やSlack連携に転用。 |
| `register_policy_override` (M1.1+) | `def register_policy_override(self, *, key: str, value: Any, expiry: datetime) -> PolicyOverride` | `PolicyOverrideRejected` | `pytest -k risk_manager::test_policy_override_requires_signature` | M1 CoreではFeature Flag `risk.policy_override_enabled`がfalse。Codex実装時もAPIシグネチャは確定済みのため準備のみ。 |

- **レビュー観点**:
  1. 監査ログ (`audit_payload`) には`strategy_ids`, `r_eff`, `bucket_exposure`, `kill_switch_status` を含め、HumanレビューがそのままRunbookへ転記できるようにする。
  2. `evaluate`内部で`context.mode`に応じた緩和ロジックを集中管理し、将来Live特有の閾値調整を追加する際に分岐を一箇所で済ませる。
  3. Codex出力に`Decimal`と`float`が混在しないかをレビュー。金融計算は`Decimal`を優先し、`FractionalSizer`との整合性を保つ。

### 3.9 HealthMonitor (`src/core/health.py`)
- **公開API**: `raise(level, reason)`, `snapshot()`, `ack(alert_id)`。
- **入力**: Risk/Data/Config/Spread/Funding/Heartbeat/Manual。`alert_id`を生成しCLIで承認。
- **出力**: `HealthStateChanged`, `AlertEvent`（メール/Slack送信対象）。`AlertEvent`には`severity`, `recommended_action`, `runbook_ref`, `ack_required`, `metric_snapshot`（`metric`, `observed`, `threshold`, `lookback`）を含め、CLIの`tradectl health ack --alert <id>`で承認者IDとRunbook記録先を入力する。
- **運用ポリシー**: `data_latency_fetch`, `data_latency_processing`, `catch_up_lag_minutes`, `fetch_gap_sec`などのメトリクスを独立評価し、**HealthMonitorは計測と推奨アクション提示に限定する**。`board_mode`変更やKill Switch操作はRunbook承認後に人間がCLIで実行し、Health Monitorはその判断を補助する証跡（推奨アクション・メトリクス・Runbook参照）を提供するのみとする。
  - `fetch_delay_p95>config.ingestion.sla.fetch_p95_sec`を検出した際は`HealthState.reasons`へ`code='data_latency_fetch'`と`recommended_action='runbook:RUN-DATA-05#enter_guarded'`を追加し、`AlertEvent`でOpsチャンネルへ通知する。オペレータはRunbook `RUN-DATA-05`のチェックリストで`tradectl board --guarded`実行可否を判断し、承認後に手動実行し、チケットID/承認者/計測値/根拠RunbookステップIDを`reports/validation_log/AC-45_sla_<date>.md`へ追記する。
  - `processing_delay_p95`や`processing_timeout_sec`の逸脱は`code='data_latency_processing'`で記録し、推奨アクションとして`runbook:RUN-DATA-05#processing_fallback`と`notify:ops`を付与する。`ManualCsvIngestionTask`や再処理はRunbook承認後に実行し、解除も`tradectl board --normal`を人手で行う。
  - データ取得が停止し`fetch_gap_sec>config.ingestion.fetch_timeout_sec`の場合は`severity='critical'`, `recommended_action='runbook:RUN-DATA-05#kill_switch_review'`で`AlertEvent`を生成し、Ops/POがRunbook `RUN-RISK-01`の審査手順で`tradectl kill-switch engage --reason data_feed_unavailable`実行可否を判断する。自動でKill Switchへ伝搬しない。
  - `catch_up_lag_minutes>config.ingestion.catch_up_warn_minutes`で`warn`レベルの`AlertEvent`を発行し、20分超過では`recommended_action`に`notify:ops`を、30分超過では追加で`pager:ingestion`, `runbook:RUN-DATA-06#guarded_checklist`を設定する。オペレータはRunbook記録に測定値、代替ソース実施状況、承認者サイン、手動実行した`tradectl board --guarded`/`tradectl board --normal`コマンドのログを必須項目として追記する。`catch_up_lag_minutes<30`が連続3回確認できた場合にのみ`degraded_recovered`イベントへ測定スナップショットとRunbook参照を添付して手動解除する。
  - `health.status=degraded`が`business_days_since(last_ok)≥3`または`rolling_30d_degraded_count≥2`を満たした際は`health.escalate`イベントを`runbook:RUN-DATA-05#escalation_review`付きで出力し、Ops Manager主導のレビュー会議を要求する。`business_days_since(last_ok)≥5`または週次KPIレビュー2回連続で`degraded`が解消されない場合でもKill Switch/Board Guard遷移は自動化せず、レビュー結果を踏まえて人間がコマンドを実行する。
- **メトリクス**: `health_state_transitions.jsonl`に`reason`, `phase`, `prev_state`, `next_state`, `trigger_metric`, `recommended_action`, `ack_user`, `ack_ts`, `runbook_ref`, `manual_command_log`を記録し、`make sla-report`がData Ingestion遅延メトリクスとRunbookログを突合して手動対応が証跡化されているか検証する。Kill Switch操作は`kill_switch_events.jsonl`と監査イベント（`audit.kill_switch_engaged`）をセットで出力し、人手レビューと承認サインの必須記録フィールド（承認者、実行コマンド、計測値、判断根拠）をRunbookで照合できるようにする。

### 3.10 CorrelationGuard (`src/risk/correlation_guard.py`, `src/account/exposure.py`)
- **公開API**: `filter(signals, account_state, correlation_snapshot)`。
- **入力**: Risk Managerが生成した`CorrelationSnapshot`（`bucket_exposures`, `correlation_matrix`, `r_eff`, `ts`）。M1 Coreでは`correlation_guard`が無効なため、Risk ManagerがR抑止を担当するが、Signal Boardへ渡すインターフェースは同一構造を使用しM1.1で差し替え可能にする。
- **アルゴリズム**: 通貨バケット別にRを集計し、`config.correlation.bucket_limits`を超える場合は信号を抑制。シンボル相関>閾値（既定0.7）で同方向ポジションを抑制し、`CorrelationSnapshot.ui_hints`をSignal Boardへ引き渡す。
- **出力**: `CorrelationFilteredSignals`, `CorrelationAlert`（M2+でReduce-Only候補に利用）。

### 3.11 PositionSizer (`src/sizing/fractional.py`, `src/sizing/rounding.py`)
- **公開API**: `size(signal, account_state, broker_specs, execution_adjustments)`。
- **アルゴリズム**: `lot = per_trade * equity / (ATR_pips * pip_value)`でサイズ算出→`lot_step`丸め→`stop_level_pips`超過を検証。必要に応じてSL/TPを補正。
- **出力**: `SizedSignal`（size, risk_R, margin_estimate, ttl_factor）。丸め誤差は`checklist.lot_round_ok`に反映。

### 3.12 FundingService (`src/funding/service.py`)
> **マイルストーン注記**: FundingServiceはPaper損益の正確性を確保するためM1 Coreへ「コア例外」として含め、`swap_rates.csv`手動更新＋Calendar連携までを必須化する。ブローカーAPI自動同期はM2で拡張する。
- **公開API**: `update_forecast(account_positions)`, `apply_daily_swap(now)`, `status()`。
- **依存モジュール**: `ConfigRegistry`（`config/swap_rates.csv`, `funding.triple_day_shift`）、`CalendarService`（祝日・三倍日補正）、`AccountService`（`AccountState.swap_realized`反映）、`ScoringService`（`swap_penalty`入力）。
- **データ源**: `config/swap_rates.csv`（ユーザー管理）、`CalendarService`。M2以降で`broker_api`アダプタを追加。
- **アルゴリズム**: 保持期間推定×スワップで`swap_penalty`を算出しScoringへ提供。ロールオーバー時刻に`swap_realized`をAccountStateへ反映。祝日シフトは`triple_day`とカレンダーで補正。
- **運用要件**: `tradectl funding sync`でCSVを読み込み、更新結果を`funding_state.json`へ記録。M1ではCSVのハッシュと更新者を`reports/validation_log/AC-09_funding_<date>.md`に残し、IT-FUND-01統合テストで祝日前後の三倍日処理を検証する。
- **エラーハンドリング**: データ欠損で`FundingDegraded`イベント→`HealthMonitor.degraded`。Fallbackで前回値保持。3営業日連続で更新が無い場合は`health.raise('degraded','funding_data_gap')`を発火し、Acceptable Degradation手順で手動CSV確認を要求。

### 3.13 CalendarService (`src/calendar/service.py`)
- **公開API**: `update(now)`, `is_blocked(symbol)`, `reload()`。
- **入力**: `calendar/high_impact_events.csv`, `calendar/holidays.csv`, `config.trading_timezone`。
- **処理**: UTC→ローカル変換→重要度別に±15/30分ブロック。祝日/週末ロールオーバーで`GateState.holiday_block`を設定。解除時は`CalendarWindowCleared`。
- **拡張**: M2で外部API同期（adapters）がイベント強度を自動更新。

### 3.14 AccountService & FxRateCache (`src/account/service.py`, `src/account/fx_rates.py`)
- **公開API**: `refresh_state(mode_context)`, `apply_ticket_action(action)`, `sync_from_csv(path)`。
- **データソース**: Backtest=仮想 fills、Paper=Paper Logs、Live=ユーザーCSV（`data/account/live_account.csv`）。`fx_rates.parquet`で口座通貨換算（FR-31）。
- **出力**: `AccountState`（balance, equity, margin, running_pnl, swap_realized, open_positions[]）。
- **Live取込要件**: CSVヘッダに`ticket_id, signal_id, fill_ts, fill_price, quantity, pnl, comment`を最低限含める。`sync_from_csv`は必須列を検証し、不足時は`AccountSyncError`をraise。
- **突合処理**: `TicketRepository`（監査ログ由来の承認済チケット）と`ticket_id`/`signal_id`でJoinし、（1）未承認チケットの実績→`WARN account.unmatched_ticket`、（2）承認済だがCSV未掲載→`WARN account.missing_fill`としてアラート。整合済レコードには`proposed_entry`と比較したスリッページ、実際の`fill_ts`と承認時刻差分を算出。
- **監査イベント**: 正常に取り込んだレコードごとに`actual_fill_imported`イベントを生成し`logs/audit/live.jsonl`へ追記。メタデータとして`slippage_pips`, `fill_delay_sec`, `reconciled=true/false`, `csv_hash`を記録する。
- **相関用エクスポージャ**: `ExposureByCurrency`で通貨別Rを保持し`CorrelationGuard`へ提供。
- **エラーハンドリング**: CSV整合性NGで`AccountSyncError`→`HealthMonitor.soft_stop(account)`。監査書き込み失敗時は`AuditWriterError`を再throwしKill Switch=hard_stop。

#### 3.14.1 Trade Journal（Live実績CSV）
1. CLIまたはスケジュールジョブから`AccountService.sync_from_csv('data/account/live_account.csv')`を起動。
2. CSV読込→ヘッダ検証→`ticket_id`/`signal_id`/`fill_ts`/`fill_price`の欠損チェック。NG時は即座に`AccountSyncError`をraiseし、監査ログへ`actual_fill_import_failed`を書き込む。
3. `TicketRepository.fetch_approved(range=csv.fill_ts_span)`で承認済チケットを取得し、`ticket_id`/`signal_id`キーで突合。未一致レコードは`unmatched_rows`リストに保持し`WARN account.unmatched_ticket`を発行。
4. 突合成功レコードに対し、`slippage = fill_price - proposed_entry`（買いは正方向、売りは逆符号）と`fill_delay = fill_ts - approved_ts`を算出。スリッページ統計を`TradeJournalStats`に集計（p50/p90, 平均R換算）。
5. `AccountState`を更新し、`actual_fill_imported`イベントをレコード単位でAuditWriterへ送信。イベントには`ticket_id`, `signal_id`, `fill_ts`, `fill_price`, `quantity`, `pnl`, `slippage_pips`, `fill_delay_sec`, `reconciled`フラグを含める。
6. 集計結果を`logs/audit/live.jsonl`にサマリイベント（`actual_fill_import_summary`）として追記し、Reporterが週次レポートへ差し替える（FR-10）。

### 3.15 SnapshotManager & Resync (`src/core/snapshot.py`)
- **公開API**: `persist(context)`, `restore()`, `maybe_persist(last_bar_ts)`。
- **SnapshotModel**: `{account_state, open_tickets, gate_state, health_state, cfg_hash, last_bar_ts}`。
- **Resync手順**: `last_bar_ts`から現時刻までのバーを`fast_forward`処理し、チケットTTL/ドリフト再計算。期限切れは`TicketExpired`としてイベント化。
- **遅延補正メトリクス**: Resync完了後に`resync_latency_sec = (resync_completed_ts - last_bar_ts)`を記録し、`resync_latency_ratio = resync_latency_sec / timeframe_sec`で評価。`ratio>24`の場合は`HealthMonitor.raise('degraded','resync_lag')`を行い、Runbookフォローアップを要求する。
- **Runbook連携**: Resync開始時に`RUN-DATA-05`（手動再取得）ステップIDをEventBusへ通知し、完了後は`RUN-POST-03`に沿って事後レビュー（遅延原因、再発防止策、Kill Switch解除判断）を`logs/ops/review.log`へ追記。レビュー承認が完了するまで`HealthMonitor.ack`を保留する。M2+ではEmergency Orchestratorが`data_latency`シナリオを監視し、必要に応じてRunbookチェックリストを自動実行する。

### 3.16 TicketBuilder (`src/ticket/builder.py`, `src/ticket/validator.py`, `src/ticket/checklist.py`)
- **公開API**: `build(sized_signal, execution_adjustments, gate_state)`。
- **処理**: 価格丸め→距離検証→TTL計算→Checklist生成（lot_round_ok, price_decimals_ok, spread_ok, news_ok, oco_set）。
- **監査**: `TicketIssued`イベントと`logs/audit/*.jsonl`へ書き込み。`cfg_hash`, `data_hash`, `hybrid_components`を添付。
- **エラーハンドリング**: バリデーションNGで`TicketValidationError`→SignalをReject。ユーザー編集時も同じバリデーションを実施。

#### 3.16.A Codex実装契約とUI整合性

| 関数/メソッド | シグネチャ | 主な例外/戻り値 | テスト観点 | UI/UX拡張ポイント |
| --- | --- | --- | --- | --- |
| `build` | `def build(self, sized_signal: SizedSignal, *, execution: ExecutionAdjustments, gate: GateState, disclosure: RiskDisclosureState) -> Ticket` | `TicketValidationError`, `InstrumentMetaMissing` | `pytest -k ticket_builder::test_build_rounding`, `pytest -k ticket_builder::test_guarded_reduce_only`, `pytest -k ticket_builder::test_disclosure_badge` | `Ticket`の`ttl`と`expected_entry`は`ExecutionModel`と整合。GUI導入時もJSON Schemaを固定し、表示層のみ差し替える。 |
| `apply_manual_adjustments` | `def apply_manual_adjustments(self, ticket: Ticket, adjustments: TicketAdjustments) -> Ticket` | `AdjustmentOutOfRange`, `MinLotViolation` | `pytest -k ticket_builder::test_manual_adjustment_limits` | 調整差分は`ticket.changes`に保持し、CLIが`+2.0 pips`等の表示を生成可能。 |
| `validate_ticket` | `def validate_ticket(self, ticket: Ticket) -> ValidationResult` | `ValidationError`（`code`, `field`, `delta`を含む） | `pytest -k ticket_validator::test_min_stop_distance`, `pytest -k ticket_validator::test_risk_disclosure_gate` | `ValidationResult`は`is_valid`, `warnings`, `errors`を保持。M1.1でGUI入力検証に再利用。 |
| `render_checklist` | `def render_checklist(self, ticket: Ticket, *, format: ChecklistFormat = ChecklistFormat.CLI) -> str` | 例外なし | `pytest -k ticket_builder::test_checklist_render_cli` | `ChecklistFormat`に`cli`/`markdown`を用意し、M1 CoreはCLIのみ。GUI導入時にMarkdownを転用。 |
| `badge_summary` | `def badge_summary(self, ticket: Ticket) -> list[BadgeSummary]` | 例外なし | `pytest -k ticket_builder::test_badge_summary_levels` | Badgeは`level∈{info, warn, critical}`を持ち、Signal Boardが色分け表示できる。

- **実装ノート**:
  1. `Ticket`は`pydantic`モデルで定義し、`json(by_alias=True)`出力がCLI/監査共通となるようAliasを整備する。
  2. `ChecklistEngine`に新項目を追加する際は`ChecklistRegistry`へ登録し、Feature Flagで制御。Codex実装時は新規`Enum`を増やしても既存ロジックが崩れないよう`default`ケースを定義する。
  3. `badge_summary`に表示するラベルはRunbook検索語（例: `oco_missing`, `risk_disclosure_pending`）を含め、運用トレーダーがCLIログから直接Runbook参照できるようにする。

### 3.17 Backtest & Optimizer (`src/backtest/engine.py`, `src/backtest/walkforward.py`, `src/backtest/optimizer.py`)
- **Backtest**: Workflowと同じパイプラインを同期実行し、ExecutionModel統計値でFill判定。`PerformanceStats`にPF/Sharpe/DD/Stabilityを集計。
- **Walk-Forward**: `(train_start, train_end, test_end)`スケジューラを処理。`config.optimizer.walkforward`でウィンドウ指定。
- **Optimizer**: グリッド/ランダム探索。目的関数は`HybridScore`、制約として`MaxDD <= threshold`。結果は`reports/optimizer/<timestamp>.json`。

### 3.18 Reporter (`src/reporter/generator.py`)
- **公開API**: `generate_weekly(profile)`, `generate_daily(date)`, `emit_summary()`。
- **M1 Core出力範囲**: `PerformanceStats`からSharpe/最大DD/WinRate/累積Rを抽出し、`primary_comment`（主要イベント1件の短文）と共にMarkdownを生成する。テンプレートは`docs/templates/reports/weekly_m1_core.md`（週次）と`docs/templates/reports/daily_m1_core.md`を使用し、欠損メトリクスは`status=pending`で表示する。`emit_summary()`は同じ4指標をJSONで返し、Signal Boardヘッダに埋め込む（FR-10）。
- **拡張要素の段階的有効化**: Spread統計、Correlationガード履歴、Resync/StressTest/Journal要約、Kill Switchログ、Config差分はFeature Flag `feature_flags.reporter.enable_extended_blocks`配下で管理し、既定`False`（M1 Core）とする。M1.1以降で同FlagをON、または派生Flag（例:`reporter.enable_spread_block`, `reporter.enable_kill_switch_block`）を用意して順次解放する。Flagが無効の場合は対応ブロックをスキップし、テンプレートには`<!-- deferred:M1.1 -->`コメントを残すのみとする。
- **依存**: M1 Coreでは`PerformanceStats`、`reports/performance/paper|live/*.parquet`、`logs/events`（主要コメント抽出のみ）に限定する。Feature Flag有効時にのみ`metrics/pipeline.jsonl`、`kill_switch_events.jsonl`、`config/diff/`を追加読み込みする。
- **リスク概要/キルスイッチ連携**: `RiskSummaryBuilder`はM1.1で有効化し、Flag無効時は`RiskSummaryStub`が`None`を返す。M1.1では`risk_policy.yaml`の閾値と`kill_switch_events.jsonl`を集計し、逸脱時に`[ALERT]`バッジを付与、閾値変更は`reports/risk/threshold_change_<date>.md`へのリンクを付ける。
- **同期メタデータ**: `kpi_snapshot_version`のみをM1 Coreで記録し、Feature Flagが有効化された際に`threshold_version`や`extended_block_version`を追加する。`tradectl risk status`はメタデータ齟齬を監視し、Flag無効時は拡張フィールドを`not_applicable`表示とする。

#### 3.18.A Codex実装契約とテンプレート運用

| 関数/メソッド | シグネチャ | 主な例外/戻り値 | テスト観点 | 拡張ポイント |
| --- | --- | --- | --- | --- |
| `generate_weekly` | `def generate_weekly(self, profile: ReportProfile) -> ReportArtifact` | `ReportTemplateMissing`, `MetricNotAvailable`; `ReportArtifact`は`markdown`, `summary`, `attachments` | `pytest -k reporter::test_generate_weekly_core`, `pytest -k reporter::test_weekly_missing_metric_annotations` | `ReportProfile`に`feature_flags`を保持し、M1.1でブロック追加時にテンプレ差分のみで対応可能。 |
| `generate_daily` | `def generate_daily(self, date: datetime) -> ReportArtifact` | `ReportDataGap`; `ReportArtifact` | `pytest -k reporter::test_generate_daily_catchup` | Daily版はM1 Core optional。M1.1でベンチマーク比較等を追加する際に再利用。 |
| `emit_summary` | `def emit_summary(self) -> dict[str, Any]` | 例外なし（欠損時は`metric_state='pending'`） | `pytest -k reporter::test_emit_summary_structure` | Signal Boardヘッダで使用。M1.1で`extended_blocks`を含める場合でもキー互換を維持。 |
| `render_block` | `def render_block(self, block: ReportBlock, data: ReportData) -> str` | `ReportBlockDeferred`（Flag無効時） | `pytest -k reporter::test_render_block_deferred_comment` | `ReportBlock`はEnumで定義し、`deferred_reason`を保持。将来GUIレポートでも再利用。 |
| `validate_inputs` | `def validate_inputs(self, stats: PerformanceStats) -> None` | `ReportValidationError` | `pytest -k reporter::test_validate_inputs_thresholds` | `PerformanceStats`の閾値変更があっても例外文言をRunbook検索語（例: `report_missing_winrate`）で統一。

- **テンプレート管理**:
  1. `docs/templates/reports/*.md`は`jinja2`テンプレートとして実装し、Codexが修正する際は`{{ metric.value }}`/`{{ metric.state }}`などの変数名を変更しない。
  2. テンプレートに新ブロックを追加する場合は`<!-- block:<name> -->`コメントで囲み、Feature Flagが無効なときに`render_block`が`ReportBlockDeferred`を返しても差し支えないよう記述する。
  3. `ReportArtifact.attachments`には`reports/kpi_snapshots/<date>.json`や`metrics/...`のパスを格納し、Runbook `RUN-OPS-04`が参照できるようにする。

#### 3.18.1 Benchmark Monitor & Feed Loader (`src/reporter/benchmark.py`, `src/interfaces/cli/benchmark.py`)
- **目的**: 市販シグナルツールとの比較KPIを算出し、`reports/benchmark/<YYYYWW>.md`および`reports/governance/benchmark_review/<YYYYQ>.md`へ自動反映する。
- **データ取り込み**: `BenchmarkFeedLoader`がTradingView ICS/CSV（`--provider tradingview`）とMyfxbook CSV（`--provider myfxbook`）を受け取り、時刻→UTC、価格→口座通貨換算を行った上で`benchmark_runs/raw/<provider>/<YYYYMMDD>.parquet`へ保存する。CLI `tradectl benchmark ingest --provider <name> --file <path>`がエントリーポイントで、ヘッダ検証・重複除去・欠損補完を実施。取得不可区間は`data/manual_fallback/<provider>/<symbol>/<YYYYMMDD>/fallback_<provider>_<symbol>_<tf>_<YYYYMMDD>_{op,review}.csv`としてOps ManagerとPOが双子入力し、`tradectl benchmark validate-manual --path data/manual_fallback/<provider>/<symbol>/<YYYYMMDD>/`を実行する。検証が一致した場合のみ週次ジョブが手入力値を正規化してParquetへマージし、ハッシュと承認サインを`reports/benchmark/manual_log_signoff/<YYYYMMDD>.md`へ保存する。不一致時はExit code 120でKPI更新と比較処理を停止する。
- **比較処理**: `BenchmarkComparator.compare(window='90d', mode='paper')`がPaper/Liveのエクイティとベンチマーク信号を同一期間に揃え、Sharpe/最大DD/HitRate/提案レイテンシ差分を算出。結果は`benchmark_runs/normalized/<YYYYMMDD>.parquet`にキャッシュし、ReporterはFeature Flag有効時（M1.1以降想定）に週次レポートへ組み込む。四半期レビュー用にはローリング252営業日分を別途算出し、`reports/benchmark/rolling_252d.md`へ出力する。
- **CLI**: `tradectl benchmark compare --window 90d --mode paper --provider tradingview,myfxbook`で最新データに対する差分を表示。`--export`オプションでMarkdownを生成し、`--fail-on-gap`で欠損率>10%時に非ゼロ終了コードを返す。`tradectl benchmark ingest --email <mbox>`は将来拡張（M2+）としてメール添付パースを想定し、M1では未実装の警告を返す。
- **監査/Runbook**: 取り込みログは`logs/benchmark/ingest.jsonl`、比較結果は`logs/benchmark/compare.jsonl`へ出力し、Runbook `GOV-BENCHMARK-01`のチェックリストにリンク。欠損率や差分閾値超過時は`benchmark_gap`イベントを発行し、Health Monitorへ`reason='benchmark_gap'`を追加する。

### 3.19 Configuration Governance & Alert Dispatcher (`src/infra/config.py`, `src/infra/alert.py`)
- **ConfigRegistry**: `load(profile)`, `apply_patch(diff)`, `validate(config)`。`safe_keys`はホットリロード、`dangerous_keys`は`NextBarChangeQueue`経由で遅延適用。
- **監査**: Config差分は`ConfigChanged`イベントと`logs/audit`に記録。`cfg_hash`をSnapshotに反映。
- **AlertDispatcher**: SMTP設定を`.env`から読み込み、`AlertEvent`をメール送信。将来Slack/Webhookに備え`Dispatcher`インターフェースを用意。

#### 3.19.1 設定パラメータ分類
| 設定キー例 | 既定値 (profile\_live) | 区分 | 反映方式 | 備考 |
| --- | --- | --- | --- | --- |
| `risk.per_trade` | `0.0075` | dangerous | 次バー適用 (`NextBarChangeQueue`) | M1上限0.75%。変更時は監査ノート必須。 |
| `risk.daily_loss`, `risk.weekly_loss` | `-0.025`, `-0.05` | dangerous | 次バー適用 | Kill Switch閾値。解除には手動承認が必要。 |
| `gates.spread_max_pips` | `1.5` | dangerous | 次バー適用 | Spread guardの即時停止を防ぐため遅延適用。 |
| `strategies[].weight` | `0.6/0.4` | safe | 即時反映 | 変更は`StrategyRegistry`へbroadcast。 |
| `strategies[].params` | 戦略依存 | safe | 即時反映 | 変更履歴は`ConfigChanged`に記録。 |
| `execution.human_delay_secs` | `45` | safe | 即時反映 | ExecutionModelが次バーで自動適用。 |
| `execution.slippage_mean_pips` | `0.4` | safe | 即時反映 | M1 Coreの滑り平均。シンボル別は`execution_model.yaml`で上書き。 |
| `execution.ttl_buffer_sec` | `30` | safe | 即時反映 | `ttl_seconds = human_delay + buffer`算出に利用。 |
| `spread.cooldown_percentile` | `0.9` | dangerous | 次バー適用 | Spread guardの安定性確保。 |
| `funding.triple_day_shift` | `Wed` | safe | 即時反映 | FundingServiceが次ロールで利用。 |
| `correlation.bucket_limits.JPY` | `2.5R` | dangerous | 次バー適用 | 相関制約緩和には運用承認が必要。 |
| `notifications.email.enabled` | `true` | safe | 即時反映 | メール停止時は監査コメント必須。 |
| `feature_flags.*` | 各Feature | safe/dangerous (後述) | Flag定義に従う | 付録B参照。 |

- `dangerous`キーは`tradectl cfg diff`(将来)で強調表示し、CLIが確認プロンプトを要求する。
- ロールバックは`SnapshotManager`の`cfg_hash`と`logs/audit`を参照し、`ConfigRegistry.rollback(hash)`（M2計画）で対応予定。M1では手動復元。

### 3.20 Persistence & Audit (`src/persistence/*.py`)
- **EventsWriter**: DomainEvent→`logs/events/YYYYMMDD.jsonl`。書込失敗で`EventWriteError`をリトライ3回。その後`hard_stop(audit)`。
- **AuditWriter**: HITL操作を`logs/audit/YYYYMMDD.jsonl`へ。`ticket_id`, `action`, `user`, `delta`, `note`, `cfg_hash`。Live実績取込時は`actual_fill_imported`/`actual_fill_import_summary`イベントを受け取り、`slippage_pips`や`reconciled`フラグを含めて永続化する。
- **SQLite (拡張)**: `logs/audit.db`にテーブルを保持（M1 optional, M2+で強化）。

### 3.21 Metrics & Telemetry (`src/infra/metrics.py`)
- **収集対象**: パイプライン処理時間、SpreadCooldown滞留時間、Kill Switch遷移、CLIレスポンス、**Data Ingestionのfetch/processing遅延**、**RateLimitステージ統計（429発生率/トークン残量/手動操作ログ）**。
- **フォーマット**: JSON Lines (`metrics/pipeline.jsonl`, `metrics/cli_perf.jsonl`, `metrics/data_ingestion_sla.jsonl`, `metrics/rate_limit_window.jsonl`)でローリング1日ごとにローテーション。レコードは`ts, metric, value, labels`を共通スキーマとし、Data Ingestionは`metric=data_ingestion_delay_sec`、`labels={phase,provider,symbol}`を付与する。RateLimit系は`metric=rate_limit_429_rate|rate_limit_tokens`を利用し、`labels={provider,stage,window}`を必須とする。
- **M1出力経路**: `JSONLMetricsWriter`がバックグラウンドワーカーで書き込み、`tradectl metrics report --window 24h`がJSONLから集計してMarkdown/JSONサマリーを`reports/metrics/<timestamp>/summary.{md,json}`へ出力（Runbook添付用）。`rate_limit`グループは`tradectl metrics report --window 24h --filter rate_limit`で個別抽出可能とし、Runbook `RUN-DATA-05`のステージレビューにリンクする。
- **Exporterインターフェース**: `PrometheusExporter`クラスを定義し`register_histogram/register_gauge`でメトリクスを登録できるようにするが、M1では`start_http()`はFeature Flag無効時にNo-OpとなりHTTPサーバを起動しない。M2で`127.0.0.1:9108/metrics`を公開する実装を追加予定。
- **アラート**: 閾値（pipeline p95>250ms, spread mismatch>5%, fetch_delay_p95>fetch目標, processing_delay_p95>processing目標, rate_limit_429_rate>Stage基準）超過で`AlertDispatcher`へ通知し、CLIにもWARNを表示する。RateLimit逸脱時は`code='rate_limit_stage'`でHealthMonitorへ伝搬し、`recommended_action`にRunbook節を添付する。

### 3.22 依存ライブラリとバージョン管理
- **パッケージ管理**: Poetry (Python 3.11)。`pyproject.toml`に厳格バージョンとハッシュ (`poetry.lock`) を保持し、`poetry install --no-root`を標準化。
- **主要依存**:
  - `pandas`, `numpy`, `pyarrow`, `pandas-ta` (データ/指標)
  - `typer`, `rich` (CLI)
  - `pydantic`, `jsonschema` (設定検証)
  - `orjson`, `python-json-logger` (高速シリアライズ/ログ)
  - `pytest`, `pytest-mock`, `pytest-approvaltests`, `hypothesis` (テスト)
- **アップグレード方針**: セマンティックバージョンに従い、パッチ更新は月次、マイナー更新は四半期、メジャー更新は専用スプリントで実施。`poetry update <package>`後に`pytest -m "m1 or m2plus"`とバックテスト回帰を必須化。
- **互換性検証**: pandas/pyarrowなどABI影響のある依存は`tests/integration/test_data_pipeline.py`で再計算差異を確認。CLIは`pytest-approvaltests`で出力差分をチェック。
- **CI/CD**: GitHub Actions（想定）で`poetry export --with dev`→`pip install --require-hashes`を実行。M1はローカルCI、M2でクラウドCI導入予定。
- **OS依存**: macOS 13+で動作確認。Linux移植はM2+課題としてDockerfile整備を予定。

### 3.23 ネットワーク/レートリミット耐性
- **リトライポリシー**: `ProviderAdapter`は指数バックオフ(初期1s, 最大30s, 試行3回)を使用。連続失敗時は`DataSourceDown`イベントを発行し、フォールバックプロバイダへ切替。
- **レートリミット**:
  - yfinance: `RateLimitGuard`（§3.1.1）がStage0/1/2ごとのジッター付きポーリングを提供し、429閾値に応じて手動昇格/退行を行う。Stage変更時は`max_concurrent = ⌊tokens_per_minute / (60 / mean_interval)⌋`を再計算し、`metrics/rate_limit_window.jsonl`に証跡を残す。
  - Dukascopy: 1リクエスト/0.5秒、日次ダウンロードは時間帯分散。403/429検出時は60秒クールダウン。Stage制御の対象外だが`RateLimitGuard`は`stage='fixed'`で統計のみ記録する。
- **Stage監視ジョブ**: `RateLimitStageEvaluatorJob`（15分間隔）が429率・連続回数を集計し、昇格/退行提案をEventBusへ配信。Acceptable Degradation中は自動的にStage0推奨を発行し、Runbook `RUN-DATA-05#rate_limit_guard`のチェックリスト更新を促す。
- **プロキシ/VPN検出**: プロキシ利用時は`config.provider.proxy`を設定。未設定で疎通不可ならWARNを出力。
- **ネットワーク障害時の保護**: 連続失敗閾値到達で`HealthMonitor`が`soft_stop(network)`へ遷移し、新規シグナルを停止。再接続後に自動`Resync`を実施。
- **監視**: `metrics/network.jsonl`に遅延、エラー率、フォールバック発生回数を記録。閾値(エラー率>10%/5分)でメールWARN。
- **テスト**: `tests/integration/test_network_resilience.py`でHTTP 429/500/timeoutシナリオをモックし、フォールバック動作を確認。

### 3.24 サポートツール/スクリプト
| ツール | パス | 用途 | 備考 |
| --- | --- | --- | --- |
| `tools/gen_fixture.py` | テストデータ生成 | 30日分OHLCV疑似データを生成し`tests/fixtures/market/`へ配置 | PR時に再生成推奨 |
| `tools/replay_signals.py` | シグナルリプレイ | 監査ログを読み込みCLIボード動作を再現 | 運用教育用 |
| `tools/redact_logs.py` | ログマスキング | 個人情報をマスクした監査ログを出力 | 外部共有時に使用 |
| `scripts/backup.sh` | バックアップ | `data/`と`logs/events/`を外部ストレージへ同期 | LaunchAgent化予定 |
| `scripts/restore_snapshot.sh` | 復旧 | 指定スナップショットを復元し`tradectl resync`を実行 | ドリルトレーニングで利用 |
| `scripts/preflight.sh` | プレフライト | 起動前にチェック項目を実行し結果をJSONで出力 | `tradectl preflight`から呼び出し |
| `docs/templates/incident_report.md` | 事故レポート | 障害対応後の振り返り | Runbook付録参照 |
| `docs/templates/config_change.md` | 設定変更計画 | 危険設定変更時の計画書 | Configレビューで必須 |

- 各スクリプトには`--dry-run`オプションを持たせ、運用前に影響を確認できるようにする。
- ドキュメントテンプレートはリポジトリに保存し、Pull Requestテンプレート(`.github/PULL_REQUEST_TEMPLATE.md`)から参照する。

#### ガバナンス系サービスのM1スコープガード
- `src/scoreboard/`, `src/ideas/`, `src/ops_readiness/`, `src/governance/`, `src/reconciliation/`配下のサービスはM1ではスタブとしてのみ配置する。
- 共通ポリシー: ①公開APIは存在するが戻り値は`None`や`NotAssessed`等の安全な定数、②EventBus publish/subscribeは無効化、③設定ファイルは`config/*.yaml`の存在チェックのみ行い内容参照はしない、④ログに`logger.info("<service> noop (M1)")`を残す。
- 依存箇所（Workflow OrchestratorやCLIコマンド）はFeature Flag `governance.enable_<service>`が`True`の場合のみ本実装をDIし、M1では既定`False`で`*Stub`が注入される。
- テストベースライン: M1ではスタブが副作用を発生させないこと、呼び出し側が安全なデフォルトハンドリングを行うことを確認するユニットテストのみを実施する。FR-61/62/63/64およびAC-49/51/53はM2+承認後に有効化。

### 3.25 Strategy Scoreboard Service Stub (M2+)
- **M1実装**: `StrategyScoreboardServiceStub`（`src/scoreboard/service_stub.py`）。
  - `generate_weekly_snapshot(week_ending)`は`None`を返し、`logger.info("scoreboard.generate noop (M1)")`のみ出力。
  - `get_latest()`は`StrategyScoreboardSnapshot(status="not_available", generated_at=None, metrics=[])`等の固定値を返す。
  - `trigger_watchlist(strategy_id)`はEventBusを呼ばず`False`を返却。
- **イベント/連携**: すべて無効化。`EventBus.publish`は呼び出さないことをユニットテストで保証する。
- **依存関係**: `core/workflow.py`からの呼び出しはFeature Flag `governance.enable_scoreboard`にラップし、M1ではスタブのみ解決される。Reporter/Model Risk連携も未配線。
- **M2+実装**: KPI算出・watchlist連携などの完全ロジックは付録G.1を参照。M2+承認後に`service.py`へ実装し、スタブは残置して再現性を担保する。

### 3.26 Idea Pipeline Manager Stub (M2+)
- **M1実装**: `IdeaPipelineManagerStub`（`src/ideas/manager_stub.py`）。
  - `load_manifest(idea_id)`は`IdeaManifestStub(status="not_applicable")`を返却し、ファイルアクセスは行わない。
  - `transition_stage(...)`は`IdeaStageResult(accepted=False, reason="governance_disabled")`を返す。
  - `validate_evidence(idea_id)`は`IdeaEvidenceStatus(not_assessed=True)`を返し、欠損イベントを発火しない。
- **イベント/連携**: `stage.changed`等のEventBus発火は実施しない。Reporter/Scoreboard/ModelRiskとの連携呼び出しもログ出力のみに留める。
- **依存関係**: CLI `tradectl research stage`はFeature Flag `governance.enable_ideas`が有効な場合のみ有効化し、M1ではヘルプ表示に`(M2+)`を追加して案内する。
- **M2+実装**: ステージ遷移や証跡検証の詳細は付録G.2に移設。M2+承認までは本節のスタブ仕様に従う。

### 3.27 Ops Readiness Evaluator Stub (M2+)
- **M1実装**: `OpsReadinessEvaluatorStub`（`src/ops_readiness/evaluator_stub.py`）。
  - `evaluate(period)`は`OpsReadinessScore(status="not_assessed", score=None)`を返す。
  - `explain(period)`は空の`OpsReadinessBreakdown(entries=[])`を返す。
  - `record_override(...)`は`False`を返しEventBusへ通知しない。
- **イベント/連携**: 健全性変更やScoreboard連携は行わない。Kill SwitchやReporterとの連携もスタブ。
- **依存関係**: Scheduler登録は`jobs_stub.py`で`logger.info("ops_readiness job skipped (M1)")`を出力するのみ。HealthMonitorはこのスコアを参照しない。
- **M2+実装**: 証跡評価やKill Switch連携のロジックは付録G.3を参照。

### 3.28 Model Risk Register Service Stub (M2+)
- **M1実装**: `ModelRiskRegisterServiceStub`（`src/governance/model_risk_stub.py`）。
  - `scan_register()`は空リストを返す。
  - `open_gap(...)`/`resolve_gap(...)`はどちらも`False`を返し、副作用なし。
- **イベント/連携**: `model_risk.*`イベントは発火しない。Kill Switch条件やScoreboard watchlist同期も行わない。
- **依存関係**: Ops Readinessとの連携、CLI `tradectl model risk ...`はFeature Flag `governance.enable_model_risk`を前提にM2+まで無効化。
- **M2+実装**: Register解析・ギャップ管理の詳細は付録G.4へ移設。

### 3.29 Statement Reconciliation Service Stub (M2+)
- **M1実装**: `StatementReconciliationServiceStub`（`src/reconciliation/service_stub.py`）。
  - `reconcile(...)`は`StatementReconciliationResult(status="not_available")`を返し、ファイル読み込みを行わない。
  - `load_statement(path)`は`None`を返し、IO例外を握りつぶさない。
  - `export_summary(result)`は`logger.info("reconciliation summary noop (M1)")`を出力するのみ。
- **イベント/連携**: `reconciliation.completed`/`discrepancy`等のイベントは発火しない。Ops ReadinessやHealthMonitorとの接続は未配線。
- **依存関係**: CLI `tradectl reconcile statements`はM1では`Feature disabled (M2+)`メッセージを返し、Schedulerにも登録しない。
- **M2+実装**: ステートメント突合やKill Switch連携の詳細は付録G.5を参照。
## 4. データモデル

### 4.1 時系列フレーム
| フレーム | 主フィールド | 説明 |
| --- | --- | --- |
| `MarketFrame` | `ts (DatetimeIndex[UTC])`, `symbol`, `open/high/low/close`, `volume`, `provider`, `quality_flag` | 取得した生データ。 |
| `FeatureFrame` | `ts`, `symbol`, `feature_*`, `mask` | インジケータとマルチTF特徴量。欠損は`mask`列で管理。 |
| `SpreadMetrics` | `ts`, `symbol`, `bid`, `ask`, `spread_pips`, `percentile`, `source_tag` | Spread Monitorの入力。 |
| `FxRateFrame` | `ts`, `pair`, `mid`, `source_priority` | 口座通貨換算用。 |

### 4.2 ステートオブジェクト
```python
@dataclass
class AccountState:
    balance: float
    equity: float
    available_margin: float
    used_margin: float
    running_pnl_daily: float
    running_pnl_weekly: float
    swap_realized: float
    swap_forecast: float
    open_positions: list[OpenPosition]
    exposure: ExposureByCurrency
    last_updated: datetime
```
`OpenPosition`には`symbol`, `side`, `size`, `avg_entry`, `sl`, `tp`, `unrealized_R`, `age_bars`, `correlation_bucket`, `regime_at_entry`を含む。

```python
@dataclass
class GateState:
    news_block: bool
    news_reason: Optional[str]
    news_release_ts: Optional[datetime]
    holiday_block: bool
    spread_cooldown: SpreadCooldownState
    spread_reason: Optional[str]
    reduce_only: bool
    reduce_only_reason: Optional[str]
```

`HealthState`は`status`, `reasons: dict[str, str]`, `alerts: list[AlertSummary]`, `last_update`を持つ。

### 4.3 シグナル/チケットパイプライン
| 構造体 | フィールド |
| --- | --- |
| `RawSignal` | `strategy_id`, `symbol`, `side`, `entry_mode`, `entry_price`, `sl_price`, `tp_price`, `rationale`, `badges` |
| `RankedSignal` | `raw`, `score`, `stability`, `swap_penalty`, `spread_penalty`, `rank`, `hybrid_components` |
| `RiskVettedSignal` | `ranked`, `kill_switch_state`, `risk_flags`, `gate_snapshot` |
| `SizedSignal` | `risk_vetted`, `size`, `risk_R`, `margin_estimate`, `ttl_factor`, `expected_fill` |
| `TradeTicket` | `ticket_id`, `symbol`, `side`, `entry`, `size`, `sl`, `tp`, `score`, `ttl_sec`, `drift_guard_R`, `badges`, `checklist`, `cfg_hash`, `expires_at`, `created_ts` |

### 4.4 設定ファイル
- `config/profile_<name>.yaml`主要キー: `provider`, `timeframes.trigger`, `timeframes.regime_ref`, `risk.*`, `gates.*`, `strategies[]`, `execution.*`, `spread.*`, `funding.*`, `correlation.*`, `scheduler.*`。
- `cfg.schema.json`で型/範囲検証。`apply_patch`時は`jsonschema`+独自検査（丸め、閾値相互制約）。

### 4.5 イベントスキーマ
| event_type | 主フィールド |
| --- | --- |
| `market_update` | `ts`, `symbols`, `last_bar_ts`, `provider` |
| `signal_generated` | `ts`, `strategy_id`, `symbol`, `score`, `components`, `cfg_hash` |
| `ticket_issued` | `ts`, `ticket_id`, `symbol`, `entry`, `size`, `ttl_sec`, `badges`, `cfg_hash`, `data_hash` |
| `ticket_action` | `ts`, `ticket_id`, `action`, `user`, `delta`, `note` |
| `risk_alert` | `ts`, `type`, `reason`, `severity`, `r_eff`, `bucket`, `signal_ref`, `ui_hints` |
| `risk_metrics_snapshot` | `ts`, `mode`, `r_eff`, `threshold`, `bucket_exposures`, `correlation_matrix_hash`, `ui_hints` |
| `health_state_changed` | `ts`, `from`, `to`, `reason`, `alert_id` |
| `config_changed` | `ts`, `profile`, `diff_summary`, `cfg_hash` |
| `spread_state_changed` | `ts`, `symbol`, `from`, `to`, `threshold`, `cooldown_eta` |
| `resync_completed` | `ts`, `bars_processed`, `data_hash`, `snapshot_hash` |
| `actual_fill_imported` | `ts`, `ticket_id`, `signal_id`, `fill_ts`, `fill_price`, `quantity`, `slippage_pips`, `fill_delay_sec`, `reconciled`, `csv_hash` |
| `actual_fill_import_summary` | `ts`, `imported_count`, `unmatched_count`, `slippage_stats`, `csv_path`, `csv_hash` |
| `actual_fill_import_failed` | `ts`, `csv_path`, `missing_columns`, `error`, `csv_hash` |

### 4.6 リスクスナップショット (`RiskMetricsSnapshot`)
- **スキーマ**: `ts`, `mode`, `r_eff`, `threshold`, `bucket_exposures`（JSON: `{bucket: {gross_R, net_R, position_count}}`）, `correlation_matrix_path`, `correlation_matrix_hash`, `top_pairs`（相関上位3組）, `ui_hints`（Signal Board表示用）。
- **保存先**: `data/correlation/<YYYYMMDD>/risk_snapshot.parquet`（日次追記）と`data/correlation/<YYYYWW>_correlation.parquet`（週次サマリ）。ヒートマップPNGは`data/correlation/<YYYYWW>_heatmap.png`に出力する。
- **初期データセット**: Validation Data Playbook（要件定義§8.2, AC-09行）で指定した対象期間（直近30営業日）と責任者（Risk Manager/Ops Manager）を基に`data/correlation/initial/bootstrap.parquet`を生成し、Paper移行前のレビューでサインオフする。週次更新はRunbook `docs/runbooks/RUN-RISK-01.md`の「通貨バケット・相関データセット更新」節を参照し、更新ログを`reports/validation_log/AC-09_<date>.md`へ追記する。

### 4.7 スナップショットファイル
- `account_state.json`: `AccountState`シリアライズ。
- `open_tickets.json`: 未失効チケット一覧（`ticket_id`, `expires_at`, `drift_guard`, `status`）。
- `gate_state.json`: 最新`GateState`。
- `health.json`: `HealthState`。
- `cfg_hash.txt`, `data_hash.txt`, `last_bar_ts.txt`。
- 整合性チェック: 再起動後に`cfg_hash`差異で`ConfigMismatch`、`data_hash`差異で`DataMismatch`。

## 5. シーケンス / ワークフロー

### 5.1 起動〜Resyncフロー
1. `tradectl start --profile <name>` → `SessionManager.start`。
2. `SnapshotManager.restore`で前回状態読込。`cfg_hash`差異があればResync必須フラグ。
3. `DataIngestionService.backfill`で`last_bar_ts`以降を取得。
4. `FeaturePipeline.rebuild_range`で特徴量再生成。
5. `ExecutionModel`と`RiskManager`がチケットTTL/ドリフトを再評価。期限切れは`TicketExpired`イベント。
6. `ResyncCompleted`イベント発行→`HealthState`を`ok`へ戻す。

### 5.2 バー処理パイプライン（Backtest/Paper/Live共通）
1. `DataIngestionService.fetch_latest`。
2. `DataQualityGuard.validate`。
3. `FeaturePipeline.update`。
4. `RegimeDetector.update`。
5. `SpreadMonitor.update`。
6. `CalendarService.update_gate_state`。
7. `FundingService.update_forecast`。
8. `AccountService.refresh_state`。
9. `StrategyEngine.run_all`。
10. `ExecutionModel.apply_adjustments`。
11. `ScoringService.rank`。
12. `RiskManager.evaluate`（通貨バケットエクスポージャ更新→相関行列算出→`R_eff`評価→`RiskMetricsSnapshot`発行）。
13. `CorrelationGuard.filter`（M1.1で有効化、M1 CoreはRisk ManagerがR抑止を兼務）。
14. `PositionSizer.size`。
15. `TicketBuilder.build`。
16. `EventBus.publish(TicketIssued)`。
17. `Reporter`/`Metrics`が処理時間を記録。
18. `HealthMonitor`が閾値を評価。必要に応じKill Switch遷移。
19. `SnapshotManager.maybe_persist`（`config.snapshot.interval_bars`ごと）。

### 5.3 Kill Switch / Health State遷移
- `ok → degraded`: Spread/Funding欠損、軽微なデータ欠損、NTPドリフト検知。`BoardMode=guarded`で主要4ペアのみ承認継続。
- `degraded → soft_stop`: 日次損失, 連続エラー, Heartbeat断、Manual stopなどリスクイベント。データ遅延のみでは遷移せず、Kill Switchを`STOP`にして新規シグナル停止・Reduce-Only準備。
- `soft_stop → hard_stop`: 監査ログ書込失敗、データ破損など重大障害。全処理停止。
- `解除条件`: 原因解消後にCLIで`ack`しKill Switch `STOP → RUNNING`。`hard_stop`解除は再起動必須。
| from | to | トリガー | 自動アクション | 解除条件 |
| --- | --- | --- | --- | --- |
| ok | degraded | Spreadデータ欠損、軽微なDataQualityAlert、NTPドリフト、SchedulerLagWarning | `HealthState=degraded`, `BoardMode=guarded`, メールWARN, 主要4ペアのみ承認継続 | 自動（回復検知）またはオペレータ確認 |
| degraded | soft_stop | 日次/週次ドローダウン閾値超、SpreadCooldown長期化、HeartbeatTimeout、手動`tradectl killswitch stop` | 新規シグナル停止、Reduce-Only準備、Kill Switch=STOP (`BoardMode=halted`) | CLIで`ack`し原因解消を記録 |
| soft_stop | hard_stop | AuditWriter失敗、Snapshot破損、Config不整合、重大例外 | 全イベント停止、Alert CRITICAL送信、再起動待ち | 原因除去後にプロセス再起動しResync完了 |
| any | ok | 手動`ack` + 状態確認 | 新規シグナル再開、Alert履歴更新 | `HealthMonitor.ack`でアラートクローズ |

ModeController遷移: `BACKTEST ↔ PAPER ↔ LIVE`は`active_jobs=0`かつ未処理チケット無しを前提に実行し、前提未満では`TransitionRejected`イベントで理由（open tickets, pending resync等）を通知する。

### 5.4 Spreadクールダウン判定
1. `spread_pips > spread_max_pips`または分位超過で`SpreadCooldownState=cooldown`。
2. `GateState.spread_cooldown=True`、解除時刻を`cooldown_eta`に保持。
3. Risk/Ticketは理由をバッジ表示し新規提案を抑止。
4. 正常化バー数が`cooldown_release_bars`連続で満たされると解除。

### 5.5 Ticketライフサイクル
1. `TicketIssued` → CLI表示。
2. ユーザー操作（approve/reject/edit）→ `TicketAction` → 監査ログ。
3. `approve`後: `TicketApproved`イベント、`AccountService`がポジション同期を待つ。
4. Liveモード: `tradectl account import --csv data/account/live_account.csv`等で実績CSVを取り込み、`actual_fill_imported`/`actual_fill_import_summary`イベントを生成。承認済チケットと突合し、スリッページ統計と監査ログを更新。
5. TTL経過/Drift超過: `TicketExpired`→CLIで失効表示。
6. Kill Switch `STOP`: 未承認チケットを`TicketForceCancelled`として整理。

### 5.6 Config変更フロー
1. `config/profile_<name>.yaml`更新→`ConfigRegistry.apply_patch`。
2. `jsonschema`+独自チェックで検証。NGなら`ConfigRejected`。
3. `safe_keys`: 即時反映。`dangerous_keys`: `NextBarChangeQueue`に登録し次バー確定時に適用。
4. `ConfigChanged`イベントで差分サマリを記録。

### 5.7 Backtest / 最適化実行
1. `tradectl backtest run --profile paper --range 2024-01-01:2024-06-30`（将来コマンド）
2. BacktestEngineがパイプラインを同期実行し`PerformanceStats`出力。
3. WalkForwardRunner/Optimizerが結果を`reports/optimizer`へ。

### 5.8 シャットダウン/復旧
1. `tradectl stop` → `SessionManager.shutdown(graceful=True)`→`SnapshotManager.persist`。
2. 異常停止検出時は次回起動で`hard_stop(unexpected_shutdown)`から開始。`EventBus`が未書込イベントを再書き込み。
3. 復旧完了後`HealthMonitor`に`ack`してKill Switch解除。

### 5.9 重大障害復旧シナリオ
- **AuditWriter失敗 (CRITICAL)**
  1. Alert受信後、CLIで`tradectl status --verbose`を確認。
  2. `logs/audit/retry.log`を点検し、ディスク空き/権限を修復。
  3. `tradectl resync --since <last_success_ts>`で再投入し、問題が再発しないことを確認。
  4. `HealthMonitor.ack`でアラートをクローズ。再発時はM2でSQLite移行を検討。
- **Snapshot破損**
  1. `snapshots/archive/`から直前世代をコピーし、`tradectl resync --force`で再同期。
  2. 差分データを`reports/diff`に吐き出し確認。
  3. 原因（例: ディスク容量不足）をRunbookに記録。
- **Spreadデータ全損**
  1. `tradectl spread inspect`で欠損を確認し、`spread_metrics.parquet`をバックアップから復元。
  2. 復元不可の場合は一時的に`SpreadMonitor`を回避し、`config.gates.spread_max_pips`を厳しめに再設定。
  3. 手動スプレッド取得スクリプトを実行し、再度Spread guardを有効化。
- **Config破損**
  1. `git status`で差分確認→直近コミット/バックアップから`config/profile_*.yaml`を復旧。
  2. `jsonschema`が通るか`tradectl cfg validate`（将来コマンド）で確認。
  3. `ConfigChanged`イベントが整合するか`logs/events`を確認。

各シナリオはRunbook付録Gに詳細手順を記載し、月次でドリルを実施する。

### 5.10 起動前チェックリスト
| 手順 | チェック内容 | コマンド/場所 | 期待結果 |
| --- | --- | --- | --- |
| 1 | プレフライト実行 | `tradectl preflight` | `status: ok`。NG項目は一覧表示。 |
| 2 | バックアップ確認 | `logs/ops/backup.log` | 前日または週次バックアップ記録あり。 |
| 3 | Config差分確認 | `git status config/` | 未コミット差分なし、`cfg_hash`一致。 |
| 4 | Spread/Funding更新 | `data/spread_metrics.parquet`/`config/swap_rates.csv` | 最終更新が24h以内。 |
| 5 | Kill Switch状態 | `tradectl status` | `KillSwitch: RUNNING`。異常時は原因調査。 |
| 6 | SMTPテスト (任意) | `tradectl notify test`(将来) | テストメール受信。 |
| 7 | Runbookサイン | `logs/ops/preflight.log` | チェック者/日時を記録。 |

- チェックが完了したら`logs/ops/preflight.log`にJSON形式で記録し、`EventBus`へ`preflight_completed`イベントを送信。
- 自動起動時はcron/LaunchAgentでプレフライト→アプリ起動の順に実行する。

### 5.11 週次スコアボード更新フロー（AC-49, FR-61）
> **M2+想定**: Appendix G.1に従う本実装フロー。M1では`StrategyScoreboardServiceStub`が即時`noop`で復帰し、本シーケンスは実行されない。
```
Scheduler(job=scoreboard_weekly)
    │ trigger (週次, 月曜 06:00 JST)
    ▼
StrategyScoreboardService.generate_weekly_snapshot()
    │ 1. `returns_24w.parquet`/`kpi_cache.parquet`読み込み
    │ 2. PF/Sharpe/Stability正規化 + `decay_score`回帰
    │ 3. `scoreboard/alpha/<YYYYWW>.json`へ書込
    │ 4. `reports/research/alpha_score/<YYYYWW>.md`レンダリング
    ▼
EventBus.publish(`scoreboard.generated`)
    │ → Reporter/CLIが結果可視化
    │ → ModelRiskRegisterServiceが`watchlist`フラグを監視
    ▼
EventBus.publish(`strategy.watchlist` when score<閾値)
    │ → TicketBuilderが警告バッジ追加
    │ → IdeaPipelineManagerが昇格ゲートを保留
    ▼
HealthMonitor
    │ score<閾値継続時に`soft_stop(strategy_watchlist)`提案（手動確認）
    ▼
Kill Switch条件更新（解除要件に「戦略レビュー完了」追加）
```

### 5.12 Opsレディネス評価→HealthState制御（AC-51, FR-63）
> **M2+想定**: Appendix G.3参照。M1では`OpsReadinessEvaluatorStub`が`status="not_assessed"`を返し、以下のフローはスキップされる。
```
Scheduler(job=ops_readiness_weekly)
    │ trigger (週次, 金曜 19:00 JST)
    ▼
OpsReadinessEvaluator.evaluate(period=週次)
    │ 1. 証跡ファイル存在/ハッシュ検証
    │ 2. バックアップ整合度/演習ログ/Runbook更新率を集計
    │ 3. `ops_readiness_score`算出し`reports/governance/ops_readiness_<YYYYWW>.md`更新
    ▼
EventBus.publish(`ops_readiness.evaluated`)
    │ → ScoreboardServiceがOpsスコアを参照
    │ → Reporterがガバナンスレポートを生成
    ▼
HealthMonitor
    │ score<`min_score` → `health.changed`(reason=`ops_readiness_low`)
    │ `HealthState=degraded` → Kill Switch=STOP, 新規戦略昇格/リリース停止
    ▼
Opsチーム
    │ `tradectl ops readiness --explain`で不足証跡確認
    │ Runbook `OPS-READINESS-01`に沿って証跡補完
    ▼
OpsReadinessEvaluator.re-evaluate()
    │ score回復後 → `health.changed`(reason=`ops_readiness_recovered`)
    ▼
Kill Switch解除 & Scoreboard閾値通常運用へ復帰
```

### 5.13 ステートメント照合→Kill Switch条件（AC-53, FR-64）
### 5.14 パフォーマンス計測とSLA検証（NFR-01/AC-05）
1. **パイプライン計測**: `core/workflow.py`で`perf_counter_ns`を用いて`on_bar_in`→`features_ready`→`signal_ranked`→`ticket_emitted`→`board_render`の区間ごとにメトリクスを取得。`metrics/pipeline.jsonl`へ`{"phase":"bar_to_board","elapsed_ms":...,"board_mode":...}`を追記し、`BoardMode=guarded`時も計測を継続する。
2. **CLI応答計測**: `interfaces/cli/board.py`と`tickets.py`に`@measure_cli_latency`デコレータを実装し、`metrics/cli_perf.jsonl`へ`render_ms`/`fetch_ms`/`persist_ms`を記録。`p95(render_ms)<100ms`, `p99<180ms`、`board_mode=guarded`中は`p95<140ms`を閾値とする。`tools/measure_cli_perf.py`で自動測定し、CIジョブ`perf-check`で週次実行。
3. **テスト**: `tests/perf/test_pipeline_latency.py`がメトリクスJSONLを解析し、直近500サンプルのp95/p99が閾値未満か検証。失敗時は`pytest`失敗とし、`docs/runbooks/RUN-PERF-01.md`に貼り付けるスパークラインを`tools/render_perf_chart.py`で再生成。
4. **レポート生成**: `tradectl metrics report --kind latency --window 7d`が`metrics/pipeline.jsonl`/`metrics/cli_perf.jsonl`を集計し、`reports/performance/pipeline_latency/<YYYYMMDD>.md`へ`board_mode`別統計とSLA逸脱ログを出力。Acceptable Degradation解除時は同コマンドの出力を`degraded_recovered`イベントに添付する。

### 5.15 Codex実装スプリントレビューシーケンス（v2.0追加）
1. **キックオフ**: PO/開発がIssueに`0.7.3`表の対象行、受入基準、想定リスクを貼り付け、`docs/prompt_packages`へプロンプトドラフトを保存。`tradectl spec lint`（将来追加予定、現状はMarkdownチェックリスト）で必須項目を確認。
2. **Codex実装**: CodexがPrompt Bundleに従って実装。完了後に`make ci-lite`を実行し、成功ログと`pytest`抜粋、主要メトリクスの差分（`git diff --stat`）をIssueへ添付。Acceptable Degradationを伴う変更の場合は`reports/validation_log/AC-45*`へ暫定ログを追記しておく。
3. **レビューフィードバック**: 開発者が`git show`で差分確認→`tradectl review checklist --epic <id>`（YAMLベースのチェックリスト）を実行し、`logs/audit/build.log`との整合性を確認。差分が仕様外の場合はPrompt Bundleを更新し再依頼。SLA影響が疑われる場合は`tradectl metrics report --window 1d`で事前検証する。
4. **ハードニング**: 運用シナリオで`docs/runbooks`を辿り、`tradectl scenario run --id <scenario>`でAcceptable Degradation手順をリハーサル。逸脱があれば`hardening/`ブランチで追補し、SLAログ（`metrics/data_ingestion_sla.jsonl`等）を`reports/validation_log`に貼り付ける。
5. **リリース判定**: Releaseブランチへマージする前に`make release-dry-run`（bundle生成＋`poetry export`）を実行し、`reports/release/<version>.md`にまとめてPO承認を得る。承認後にタグ打ち、`tradectl bundle create --version <version>`で配布物を生成する。

| ステップ | トリガー | 実行者 | コマンド/成果物 | フェイルセーフ |
| --- | --- | --- | --- | --- |
| Kickoff | Issue作成 | PO/開発 | `docs/prompt_packages/<date>_<epic>.md`、`docs/checklists/<epic>_todo.md` | 必須項目欠落時はIssueを`status=blocked`に戻す |
| Build | Codex成果物提出 | Codex | `make ci-lite`, `pytest -k <story>`, `git diff --stat` | テスト失敗時はPrompt Bundleへ原因と再試走条件を追記 |
| Review | 差分受領 | 開発 | `tradectl review checklist --epic <id>` | チェックリストNGで`feedback_loop.md`へ記録し、再学習素材とする |
| Hardening | Acceptable Degradationログ確認 | 開発＋運用 | `tradectl scenario run --id AC-45`, `tradectl metrics report --window 7d` | Runbook逸脱があれば`logs/ops/incident.log`に暫定処置を記録 |
| Release | PO承認 | 開発 | `make release-dry-run`, `tradectl bundle create` | バンドル検証失敗時は`release/<version>`を閉じ、`hardening`フェーズへロールバック |

- このシーケンスを1スプリント単位で繰り返し、`feedback_loop.md`に結果を追記する。特にAcceptable Degradationに関わる変更は、Release前に必ず手動CSV投入とBoard Guard切替手順を演習し、`degraded_ack`証跡が欠落していないかを確認する。

> **M2+想定**: Appendix G.5参照。M1では`StatementReconciliationServiceStub`が`status="not_available"`を返し、下記フローは監査用ログのみ残す。
```
Operator or Scheduler(job=reconciliation_daily)
    │ `tradectl reconcile statements --from <date>` / 日次トリガ
    ▼
StatementReconciliationService.reconcile()
    │ 1. ステートメントCSV/PDF→CSVを`normalizer`で整形
    │ 2. `trade_log.parquet`/`account_balances.parquet`と突合
    │ 3. 残高差分/取引突合率を評価しMarkdownサマリ出力
    ▼
EventBus.publish(`reconciliation.completed` or `reconciliation.discrepancy`)
    │ → Ops Readiness Evaluatorが証跡に取り込み
    │ → Reporterが`reports/audit/reconciliation/<date>.md`をリンク
    ▼
HealthMonitor
    │ 差分>閾値 → `HealthState=degraded(statement_gap)`
    │ Kill Switch=STOP, Ticket承認とIdea昇格をブロック
    ▼
Ops/Finance review (Runbook `AUD-REC-02`)
    │ 差分原因調査→`reconciliation_resolution.md`更新
    ▼
StatementReconciliationService.reconcile(retry)
    │ 差分解消で`reconciliation.completed`
    ▼
HealthMonitor.ack()
    │ Kill Switch解除条件: サマリと証跡添付を確認
```

## 6. 外部インターフェース

### 6.1 データプロバイダ
| プロバイダ | プロトコル | 備考 |
| --- | --- | --- |
| YahooFinanceProvider | HTTPS (pandas-datareader) | Intraday保持期間短。`provider_priority`でフォールバック。 |
| DukascopyProvider | HTTPS (`.bi5`バイナリ) | 1分バー→5分へ集約。認証不要。 |
| CsvProvider | ローカルCSV | `timestamp, open, high, low, close, volume?`。
| SpreadFeed | Parquet (`data/spread_metrics.parquet`) | Dukascopyティックから生成。M2でBroker API追加。 |
| SwapRates | `config/swap_rates.csv` | 手動更新。`AlertDispatcher`が古い場合警告。 |

### 6.2 CLI I/O
- CLI出力はRichテーブル/JSON/CSV。`tradectl board`と`tradectl status`は人間可読。`tradectl export`は`reports/export/<date>/`に保存。
- CLIは非同期EventBusを購読し、タイムアウト時は再購読する。

### 6.3 通知
- SMTP設定（`.env`: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `ALERT_RECIPIENTS`）。
- `AlertEvent`受信でメール送信。件名`[tradectl] <severity> <reason>`。
- Slack/Webhookは`Dispatcher`差し替えでM2+対応。

### 6.4 セキュリティ境界
- 対外通信はHTTPSのみ。タイムアウト5秒、リトライ3回。
- `config/`と`.env`は権限600。APIキーはmacOS Keychainから取得可能（M2課題）。
- 監査ログはSHA256ハッシュを`logs/checksums/`に保存し改ざん検知。

### 6.5 CLIコマンド仕様
| コマンド | 主用途 | 主要引数/フラグ | 正常時挙動 | 代表的エラーと対応 |
| --- | --- | --- | --- | --- |
| `tradectl board` | Ticketストリームの監視/操作 | `--filter key=value`, `--view open_tickets`, `--format table|json`(将来) | EventBus購読→Rich Table更新、TTL/ドリフト残を強調表示 | EventBus断: 自動再購読→失敗時`WARN board.stream`。Resync中は`INFO board.catchup`表示。 |
| `tradectl ticket approve|reject|edit` | HITL承認/却下/編集 | `--id`, `--field`(edit), `--note` | `TicketAction`イベントを記録し監査ログ追記。CLIは反映結果を表示 | バリデーションNG: `ERROR ticket.validation`＋失敗理由。監査書込失敗時は自動リトライ→`hard_stop(audit)`。 |
| `tradectl status` | Health/Kill Switch/Snapshot確認 | `--verbose` | `HealthState`, `KillSwitch`, Spread/News gate、Snapshot hashを表示 | Health取得失敗で`WARN status.fetch`。`--verbose`時に内部例外を表示。 |
| `tradectl events tail` | Domain/Auditイベントのリアルタイム追跡 | `--type`, `--since`, `--follow` | JSONL tailをストリーム表示 | ファイル存在なし: `ERROR events.tail`。`--follow`時にファイルローテーションで自動再open。 |
| `tradectl export` | チケット/シグナル/アカウントのエクスポート | `--what`, `--format csv|json`, `--out` | `reports/export/<date>/`に出力しパスを表示 | 出力先書込不可: `ERROR export.write`。リトライ指示を表示。 |
| `tradectl account import` | Live実績CSVの取り込み・突合 | `--csv <path>`, `--dry-run`, `--since` | `AccountService.sync_from_csv`を呼び出し、突合結果とスリッページ統計を表示。成功時は`actual_fill_imported`イベント数と`unmatched`件数をサマリ表示 | 必須列欠落: `ERROR account.csv_missing_columns`。監査書込失敗: `CRITICAL account.audit_failed`でKill Switch=hard_stop。 |
| `tradectl resync` | Catch-up/バックフィル操作 | `--since <ts>`, `--force` | Resyncジョブ投入→進捗バー表示→完了時`ResyncCompleted`イベント確認 | 他ジョブ競合: `WARN resync.busy`。Resync失敗で`ERROR resync.failed`＋再試行提案。 |
| `tradectl spread inspect` | Spreadメトリクス確認/解除条件確認 | `--window`, `--symbol` | `data/spread_metrics.parquet`統計を表示、クールダウン解除条件を提示 | ファイル欠損: `WARN spread.data_missing`→再計測を促す。 |
| `tradectl reduce-only status|release`(M2+) | Reduce-Only提案の管理 | `--id`, `--all` | 対象ポジションと理由を表示/解除 | Reduce-Only未対応時は`INFO reduce_only.disabled`。 |
| `tradectl research stage` (M2+) | Idea Pipeline | `--id`, `--stage`, `--note` | M1: Feature Flag既定`False`→`Feature disabled (M2+)`メッセージのみ。M2+: Appendix G.2記載の`manager.transition_stage`を呼び出し監査ログに記録 | M1: INFOログ`research.disabled`。M2+: バリデーションNGで`IdeaPromotionDenied`、Ops低下時は`IdeaPromotionDenied(ops_readiness_low)` |
| `tradectl ops readiness --explain` (M2+) | Opsヘルス可視化 | `--period`, `--output` | M1: `OpsReadinessEvaluatorStub`が`status=not_assessed`を返し、CLIは`(M2+)`案内のみ表示。M2+: Appendix G.3記載の証跡内訳を表示 | M1: `ops_readiness.disabled`ログ。M2+: 証跡欠損時は`OpsEvidenceMissing`を列挙 |
| `tradectl model risk resolve` (M2+) | モデルリスクギャップ対応 | `--id`, `--evidence` | M1: Feature Flag既定`False`で`Feature disabled (M2+)`のみ出力。M2+: Appendix G.4のギャップ解消フローを実行 | M1: `model_risk.disabled`ログ。M2+: 必須エビデンス欠落で`ModelRiskEvidenceMissing` |
| `tradectl reconcile statements --from <date>` (M2+) | ステートメント突合 | `--to`, `--mode`, `--dry-run` | M1: `StatementReconciliationServiceStub`が`status=not_available`を返し、CLIは`Feature disabled (M2+)`とログのみ。M2+: Appendix G.5の照合処理を実行 | M1: `reconciliation.disabled`情報ログ。M2+: CSV欠損で`StatementImportError`、差分特定不可で`reconciliation.escalated` |

### 6.6 ネットワーク・セキュリティ制約
| 項目 | 要件/制限 | 対応策 |
| --- | --- | --- |
| FW/Proxy | HTTP(S) outboundのみ許可。社内Proxy利用時は`config/provider.proxy`設定 | Preflightで疎通検査、Proxyエラー時はFail-Safe停止。 |
| レートリミット | yfinance: 60 req/min、Dukascopy: 120 req/min想定 | Token bucket制御、超過時はクールダウンとWARN送信。 |
| TLS証明書 | システムCAストア依存。失効/更新時は自動反映 | `requests`が失敗した場合は`ProviderError`で通知。 |
| データ暗号化 | 通信はHTTPS、ローカルデータはFileVault上で保護 | 追加暗号化が必要な場合はM2で`cryptography`導入を検討。 |
| APIキー | SMTP等の資格情報は`.env`/Keychain | Preflightで環境変数の存在を検査。 |
| 時刻同期 | NTP失敗時はSpread/Resync精度に影響 | プレフライトでドリフト検知し、補正完了まで新規シグナル停止。 |

- ネットワーク変更（ISP/ルーター交換等）の際は事前に接続テストを実施し、`logs/ops/network.log`に結果を記録する。
- VPN利用中はIP変動によりAPIブロックの可能性があるため、`ProviderAdapter`が403/429を検出した場合はVPN解除を案内する。

### 6.7 戦略ガバナンスと縮退手順
| 状態 | トリガー | 自動アクション | レビュー/復帰条件 |
| --- | --- | --- | --- |
| 正常運用 | KPI達成、SPRT安定 | 通常提案、Performanceログ更新 | KPI週次レビュー継続 |
| 注意 (Warning) | KPI乖離が閾値前後、SPRT警告域 | 提案頻度50%に縮小（`sprt_guard`）、警告をダッシュボード表示 | KPIが2週連続で回復または改善計画実施 |
| 縮退 (Degraded) | KPI未達 (Sharpe<0.5/MaxDD>15%)、SPRT fail | 戦略Feature Flag OFF、サイズ0、アラートCRITICAL | Backtest/Paperで基準回復＋PO承認 |
| 停止 (Halt) | Kill Switch発動、重大例外 | Kill Switch STOP、全提案停止 | 根本原因解消＋PO/運用/開発の合意 |

- 戦略ごとのPerformance記録を`strategies/<id>/performance.json`で管理し、ON/OFF履歴と理由を監査ログへ出力する。
- Feature Flag切替時は`reports/strategy_review_<id>.md`で評価結果をまとめ、POレビュー後に適用する。
- 新規戦略追加はBacktest→WalkForward→Paper→Liveのゲートを順次通過し、QA/PO/運用の承認を必要とする。

※詳細手順とCLIスクリーンショットはRunbook付録Gと相互参照。

### 6.8 CLIテレメトリおよびコマンドログ設計（v2.4追加）

CodexがCLI改善やUX回収タスクを効率的に実装できるよう、Typerベースの各コマンドに共通テレメトリフックを追加する。ヒューマン・トレーダーの操作痕跡をQA/Runbookと突合しやすくし、将来的なGUI/Tauri移行時にも同一スキーマを再利用できるようにする。

- **対象モジュール**: `src/interfaces/cli/__init__.py`, `src/interfaces/cli/renderers.py`, 各コマンドモジュール（`board.py`, `status.py`, `tickets.py`, `events.py`, `export.py`, `resync.py`, `spread.py`, `data/rate_limit.py`, `report.py`, `benchmark.py`, `account.py`, `calendar.py`）。
- **Feature Flag**: `telemetry.cli.enabled`（既定`True`）。M1で常時記録、プライバシー要件が変化した場合は`False`で完全停止できるようにする。

#### 6.8.1 テレメトリデータモデル

| モデル | フィールド | 説明 |
| --- | --- | --- |
| `CommandTelemetryRecord` | `ts: datetime`, `command: str`, `subcommand: str | None`, `args_hash: str`, `duration_ms: int`, `status: Literal['success','error','cancelled']`, `error_code: str | None`, `health_state: HealthStateSummary`, `board_mode: BoardMode`, `actor: str`, `session_id: UUID`, `context: Literal['backtest','paper','live']`, `qa_tags: list[str]` | 1コマンド実行ごとの記録。`args_hash`は非機微引数をソートしたJSONのSHA1。`actor`は`.env`の`CLI_ACTOR`またはmacOSユーザ名。 |
| `HealthStateSummary` | `status: Literal['ok','degraded','soft_stop','hard_stop']`, `reason_codes: list[str]`, `kill_switch: Literal['RUNNING','STOP']` | コマンド開始時点の状態快照。`CommandTelemetryRecord`からインライン参照。 |
| `TelemetryAggregation` | `command: str`, `period: date`, `count_success: int`, `count_error: int`, `p95_duration_ms: float`, `p99_duration_ms: float`, `median_duration_ms: float`, `error_codes: dict[str,int]`, `board_mode_distribution: dict[str,int]` | 日次バッチで生成する統計行。`reports/telemetry/cli/<YYYYMMDD>.json`に保存し週次レポートへ引用。 |

- **格納先**: `metrics/cli_commands.jsonl`に逐次追記。日次ジョブ`TelemetryAggregatorJob`が`TelemetryAggregation`を生成し、`reports/telemetry/cli/<YYYYMMDD>.json`と`reports/telemetry/cli/<YYYYWW>.md`へ出力する。Runbook `RUN-OPS-02`のレビュー手順で参照する。
- **匿名化ポリシー**: `args_hash`に含めるのは非個人情報のみに限定する。手動ノートやコメントを含む引数（例: `--note`）は`redacted_args`リストに登録し、`args_hash`から除外する。`actor`は`CLI_ACTOR`環境変数で明示したイニシャルに制限し、個人名をログへ出力しない。

#### 6.8.2 実装ガイド

1. `Typer`アプリ登録時に`@instrument_command`デコレータを挟み、`CommandContext`を生成する。
   ```python
   @instrument_command(command="board")
   def board(...):
       ...
   ```
2. デコレータは`async`/同期双方に対応し、`time.perf_counter_ns()`で実行時間を計測、例外捕捉で`status`/`error_code`を設定する。`error_code`は`ERROR-*`（§7）または`CLI-*`（新設）を使用する。
3. `CommandTelemetryRecord`は`pydantic` v2モデルで定義し、`.model_dump(mode="json")`したものを`metrics/cli_commands.jsonl`へ追記。ファイルローテーションは1日単位で行い、`SessionManager`起動時に昨日のファイルを`gzip`圧縮する。
4. CLIコマンド内で`HealthMonitor.snapshot()`と`BoardStateResolver.current_mode()`を呼び、`HealthStateSummary`と`board_mode`を記録する。`board_mode`取得で例外が発生した場合は`board_mode='unknown'`で記録し、`status='error'`扱いにする。
5. Acceptable Degradation時に実行されたコマンドは`qa_tags`へ`['degraded','runbook:<id>']`を付与し、Runbook証跡検索を容易にする。`qa_tags`は`set[str]`として重複を許さず、将来GUIからも流用できるよう `List[str]`で保存する。

#### 6.8.3 テストと可観測性

- **ユニットテスト**: `tests/unit/test_cli_telemetry.py`
  - `test_instrument_success_records_metrics`: 正常完了で`status='success'`, `duration_ms>0`が記録される。
  - `test_instrument_error_records_error_code`: 例外発生で`status='error'`, `error_code`が捕捉される。
  - `test_redacted_args_not_in_hash`: `--note`など機微引数がハッシュから除外される。
- **統合テスト**: `tests/integration/test_cli_command_logging.py`
  - `tradectl board --filter symbol=USDJPY`実行後に直近ログ行を解析し、`command='board'`, `board_mode`が期待値であることを確認。
  - Acceptable Degradationシナリオ（`tradectl board --guarded`）で`qa_tags`に`degraded`が付与されることを検証。
- **メトリクス監視**: `TelemetryAggregatorJob`は`metrics/cli_commands.jsonl`の最新24h分を読み込み、`reports/telemetry/cli/<YYYYWW>.md`に以下を出力する。
  1. コマンド別実行回数/成功率。
  2. `board`/`ticket`系のp95実行時間とAcceptable Degradation時の増分。
  3. 重大エラーコード（`CRITICAL`）の一覧とRunbookリンク。
- **アラート閾値**: `TelemetryAggregatorJob`は`command='board'`で`p95_duration_ms>4000`または`error_rate>0.1`を検出した場合に`AlertDispatcher`へ`telemetry.cli.performance` WARNを送信し、Runbook `RUN-OPS-02`のUX改善タスクを提示する。
- **将来拡張**: GUI移行時は同一スキーマでWebSocket経由の操作を記録し、`context='gui'`を追加予定。Codexは`CommandTelemetryRecord`のバージョンを`__schema_version__=1`とし、互換性変更時に`tests/contracts/test_cli_telemetry_schema.py`で検知できるようにする。

#### 6.8.4 Codexプロンプト指針

- CLI改善の実装依頼時は、対象コマンドの直近テレメトリ抜粋（`metrics/cli_commands.jsonl`の10行）と`reports/telemetry/cli/<YYYYWW>.md`のサマリをPrompt Bundleへ添付する。
- `instrument_command`デコレータの既存挙動を変更する場合は、`CommandTelemetryRecord`の互換性チェックリスト（`fields`, `types`, `qa_tags`）をIssue本文に明記し、`tests/contracts/test_cli_telemetry_schema.py`の更新手順を添付する。
- Acceptable Degradation関連タスクでは`qa_tags`がRunbook整合性チェックに使用されることを明記し、PRに`tradectl telemetry report --command <cmd>`（将来実装予定、当面は`make telemetry-report`）の結果を添付する。

## 7. エラーハンドリング / フェイルセーフ

| ID | シナリオ | 検知 | アクション | 再開条件 |
| --- | --- | --- | --- | --- |
| ERROR-C01 | データ欠損閾値超過 | DataQualityGuard | 欠損区間除外・`soft_stop(data_quality)`・アラート | 再取得成功 or 手動承認 |
| ERROR-C02 | 指標計算失敗 | FeaturePipeline | 直近nバー再計算→失敗で`hard_stop(indicator)` | 計算成功 + ack |
| ERROR-C03 | コンフィグ検証NG | ConfigRegistry | ロールバック・`ConfigRejected`・メール通知 | 修正後再適用 |
| ERROR-C04 | 監査ログ書込失敗 | AuditWriter | リトライ3回→`hard_stop(audit)` | 書込再成功 + ack |
| ERROR-C05 | Spreadデータ欠損 | SpreadMonitor | `HealthState=degraded`, Spread guard無効化警告 | Spreadデータ復旧 |
| ERROR-C06 | Fundingデータ未更新 | FundingService | `swap_penalty=0`, `FundingDegraded` | swap_rates更新 |
| ERROR-C07 | Heartbeat停止 | HealthMonitor | 2分未受信で`soft_stop(heartbeat)` | heartbeat再開 + ack |
| ERROR-C08 | Snapshot破損 | SnapshotManager | `hard_stop(snapshot)`・Resync要求 | 最新バックアップ復元 |
| ERROR-C09 | Account CSV不整合 | AccountService | `soft_stop(account)`・詳細ログ | CSV修正 + 再同期 |
| ERROR-C10 | Scheduler遅延 | Scheduler | `SchedulerLagWarning`→`degraded` | ラグ解消 + ack |

#### 7.1 アラート重大度分類
| 重大度 | 説明 | 主な発火イベント | オペレータ対応目標 | 通知経路 |
| --- | --- | --- | --- | --- |
| INFO | 状態遷移や参考情報 | `ResyncCompleted`, `ConfigChanged(safe)` | 監視のみ | CLIログ |
| WARN | 軽微な劣化。即時停止不要 | `DataQualityAlert`(軽微), `SchedulerLagWarning`, `SpreadDataDegraded` | 30分以内に状況確認 | CLI + メール (件名`[tradectl][WARN]`) |
| MAJOR | 新規シグナル停止またはデータ欠損 | `soft_stop(*)`, `TicketValidationError`連発, `FundingDegraded` | 10分以内に原因分析、必要なら手動再開 | CLI + メール (優先度高) |
| CRITICAL | 処理継続不可。Kill Switch=STOP | `hard_stop(*)`, `AuditWriter failure`, `SnapshotCorrupted` | 即時（5分以内）に運用停止と復旧手順 | CLI + メール + 将来Slack |

重大度は`AlertEvent.severity`としてEventBusに出力され、Reporterは拡張ブロック有効時（M1.1以降）に週次レポートへ集計結果を掲載する。Flagが無効なM1 CoreではオペレータがRunbookの重大度別チェックリストを直接参照し、レポートには手動コメントのみを残す。

#### 7.2 BCP/DR指針
| シナリオ | 目標RTO | 目標RPO | 対応概要 |
| --- | --- | --- | --- |
| macOS端末故障 | 8時間 | 1時間 (最新Snapshot) | 予備端末にPython/Poetry環境を構築→バックアップから`data/logs/snapshots`を復元→`tradectl preflight`→`resync`。 |
| ネットワーク長期断 (>=24h) | 4時間 (接続復旧後) | 5分バー全復元 | オフライン中はKill Switch STOP。復旧後にDukascopyでバックフィル→Spread/Funding手動更新→プレフライト。 |
| データ損失 (Parquet破損) | 6時間 | 15分 | バックアップ/再取得で復旧。損失バーは`data/recovery/`に差分保管し再計算。 |
| 運用者不在 (急病等) | - | - | Kill Switch STOP、ポジションクローズ。Runbook contingencyで代替手順を提示。 |
| 重大コンフィグ誤設定 | 2時間 | 5分 | `ConfigRegistry.rollback`(手動)または`git checkout`で復元後、`resync`と回帰テスト。 |

- BCPテストは四半期ごとに机上演習＋年1回の実機復旧テストを実施し、結果を`docs/bcp_test_<YYYY>.md`に記録する。
- DR対応中は`logs/ops/dr.log`へタイムラインを記録し、再開後にポストモーテムを作成する。

#### 7.3 テスト計画（スコアボード/ガバナンス/照合サービス）
| テストID | 対象サービス | カテゴリ | シナリオ/目的 | 関連FR/AC | 期待結果 |
| --- | --- | --- | --- | --- | --- |
| UT-SCB-Stub-01 | Strategy Scoreboard Stub | 単体 | `generate_weekly_snapshot`が副作用なしで終了することを確認 | M1 Scope Guard | 戻り値`None`、EventBus publish未発火、`logger`に`noop`が記録される |
| UT-IDEA-Stub-01 | Idea Pipeline Stub | 単体 | `transition_stage`が`governance_disabled`理由で拒否することを確認 | M1 Scope Guard | `accepted=False`かつ`reason="governance_disabled"`、監査ログ書込を試みない |
| UT-OPS-Stub-01 | Ops Readiness Stub | 単体 | `evaluate`/`explain`が`status="not_assessed"`を返すことを確認 | M1 Scope Guard | 戻り値が固定値、`HealthMonitor`やEventBusに通知しない |
| UT-MR-Stub-01 | Model Risk Stub | 単体 | `scan_register`が空リストを返し、副作用が無いことを確認 | M1 Scope Guard | `[]`を返し、`model_risk.*`イベントが発火しない |
| UT-REC-Stub-01 | Statement Reconciliation Stub | 単体 | `reconcile`が`status="not_available"`を返しファイルI/Oを行わないことを確認 | M1 Scope Guard | `StatementReconciliationResult.status == "not_available"`、ファイルアクセスがモック検証で0回 |
| IT-GOV-Stub-FF-01 | Feature Flag Integration | 統合 | Feature Flag既定`False`でDIがスタブを注入しCLI/Workflowが`(M2+)`案内を表示することを確認 | M1 Scope Guard | `governance.enable_*`が`False`のとき、依存解決が`*Stub`型になり、CLIヘルプに`(M2+)`ラベルが出力される |

- **M2+テスト**: Appendix G.1〜G.5に記載したシナリオ（FR-61/62/63/64, AC-49/51/53対応）は該当マイルストーン承認後に有効化する。
- **テストデータ**: スタブ検証では軽量モックのみ使用。`tests/fixtures/scoreboard/returns_24w.parquet`等のデータセットはM2+用として保持し、M1ではロードしない。
- **CIフック**: `pytest -k "governance_stub"`をPR必須テストに追加し、副作用ゼロを担保する。M2+テスト用コマンドは`pytest -k "(scoreboard or ideas or ops_readiness or model_risk or reconciliation)"`としてコメントアウト状態で`ci/config.yml`にプレースホルダ記載。
- **回帰ライン**: M1期間中はFeature Flagを`False`で維持することを`docs/governance/feature_flag_register.md`で監査。承認後にFlagを切り替える際はAppendix G記載の統合テストを再実施する。
## 8. 非機能要件への対応

### 8.1 性能 (NFR-07, NFR-08)
- バー処理は1.5秒以内を目標。各`PipelineStep`のp95を`metrics/pipeline.jsonl`に記録し、閾値超過でアラート。
- DataIngestionはキャッシュ差分と並列取得（symbol分割）でパフォーマンス確保。
- Backtestは`pyarrow`メモリマップ + マルチプロセス（将来）。

### 8.2 信頼性・可観測性 (NFR-06, NFR-11)
- Snapshotは`config.snapshot.interval_bars`毎＋Kill Switch発火時に保存。復元テストをRunbookに定義（月1）。
- メトリクス/ログ/監査を分離し、`logs/checksums/`で改ざん検知。Heartbeat30秒周期。
- Alertはメール + CLI表示。将来Prometheus Exporterで外部監視連携。

| データセット | 保持ポリシー | バックアップ/アーカイブ | 備考 |
| --- | --- | --- | --- |
| `logs/events/*.jsonl` | 30日ローカル保持→月次で`archive/events/<YYYYMM>/`へgz圧縮 | 週次rsync (増分) + 月次フル | 改ざん防止に日次SHA256。 |
| `logs/audit/*.jsonl` | 365日保持。月次でgz圧縮し暗号化（M2）予定 | 週次rsync + 四半期オフサイト | 監査要求に備え索引を付与。 |
| `snapshots/latest/*` | 最新3世代を保持 | 日次フル（外部ドライブ） | 復元テスト結果をRunbookへ記録。 |
| `data/raw/<provider>/` | 12ヶ月保持。古いバーは再生成可能なため半年でサマリのみ残す | 月次差分 | 再取得不可データは`immutable/`へ保護。 |
| `data/cache/features/` | 30日保持。再計算可能 | バックアップ対象外 | キャッシュ破損時は再構築。 |
| `reports/export/` | 12ヶ月保持→年次アーカイブ | 月次アーカイブzip | 実運用で共有用。 |
| `metrics/*.jsonl` | 90日保持→月次アーカイブ | バックアップ対象外 | 外部監視導入後はPrometheusに移行想定。 |
| `config/*.yaml` | 履歴がGit管理される | Gitリポジトリバックアップ | 秘密情報は`.env`/Keychain。 |

### 8.3 セキュリティ/アクセス (NFR-04/05)
- APIキーは`.env`またはmacOS Keychain（M2予定）で管理し、`.env`は`chmod 600`をRunbookで徹底。`config/`配下に秘密情報を含めない。
- CLI実行は専用ユーザー権限（標準ユーザー）で行い、`sudo`禁止。CLI操作は`user`フィールド付きで監査ログに記録。
- Kill Switch解除や危険操作はCLIで二段確認（Y/N + `--yes`）。`AlertEvent`の重大度に応じてWebhook（将来）を追加。
- macOS端末はFileVault必須、画面ロック10分以内、共有端末での運用禁止。
- 監査ログを1年保管、月次で圧縮アーカイブ。暗号化保管はM2ロードマップに登録。

### 8.4 運用性・保守性
- CLIコマンドは冪等に設計。`tradectl status`で必須情報を1画面に集約。
- Runbookに日次/週次/障害対応手順を整備。`logs/ops/*.log`に人手操作を記録。
- Runbookは詳細設計開始時点で`RUN-DATA-05`/`RUN-DATA-06`/`RUN-RISK-01`/`GOV-AUD-01`のテンプレート骨子（目的・トリガー・チェックリスト・ダブルサイン欄・証跡リンク欄）を`docs/runbooks/`配下にコミットし、レビュー結果を`reports/governance/runbook_templates/<YYYYMMDD>.md`へ記録する。Pull Requestテンプレートに「Runbook差分確認」項目を追加し、テンプレ更新が無い場合も`N/A`記入を必須とする。
- コードはモジュール境界ごとに`tests/`へユニット/統合テストを配置し、CIで`pytest -m "not m2plus"`を実行。

### 8.5 容量・パフォーマンス見積もり
| コンポーネント | 想定データ量 (1年) | 計算コスト/必要リソース | 備考 |
| --- | --- | --- | --- |
| `data/raw/` 5分足 (4ペア) | 約3.5GB (Parquet圧縮後) | I/O帯域 5MB/s (Catch-up時) | Dukascopy: 再取得用に予備容量+2GB確保。 |
| `data/cache/features/` | 約1.2GB | CPU 1.5コア相当 (rolling計算)、メモリ<1GB | キャッシュ再生成時に追加CPU負荷。 |
| `logs/events/` | 約1.0GB (1日8MB想定) | 追記I/O軽微 | gz圧縮後は~200MB。 |
| `logs/audit/` | 200MB | 追記I/O軽微 | JSONL→SQLite移行時は追加20MB。 |
| `metrics/*.jsonl` | 100MB | --- | 90日保持後ローテーション。 |
| Backtest結果 (`reports/optimizer/`) | セットごとに～50MB | CPU: 4コア想定 (マルチプロセス) | 長期最適化時は外部SSD推奨。 |
| Spread/Funding CSV | 数MB | --- | 手動更新フォルダ。 |

- 推奨ディスク空き: **最低20GB**（データ+アーカイブ+バックアップ一時領域）。
- CPU: MacBook Pro M1クラスでバー処理p95 <1.2s、バックテスト4コア並列で月次走査が2時間以内を目標。
- メモリ: ランタイム2GB以下。大規模Backtest時は4GB程度必要。

### 8.6 Feature Flag管理
| Flag key | 既定値 (M1) | 対象機能 | 切替手順 | 備考 |
| --- | --- | --- | --- | --- |
| `feature_flags.sprt_guard` | `false` | ライブSPRT健全性ガード | `config/profile`でtrueにし、`NextBarChangeQueue`で次バー適用 | M2で有効化想定。dangerous扱い。 |
| `feature_flags.reduce_only_advisor` | `false` | Reduce-Only自動提案 | 同上 | Spread異常時の提案。運用訓練後に有効化。 |
| `feature_flags.slack_alert` | `false` | Slack通知Dispatcher | `.env`設定後にtrue | safeキー。Slack webhook検証必要。 |
| `feature_flags.gui_ws` | `false` | `/ws/signals`とGUIプレビュー | `tradectl cfg patch` (将来) | 実装済みでもM2+で段階的解放。 |

Flag切替時は`ConfigChanged`イベントに`flag_delta`が記録され、ReporterはFeature Flag有効化後に週次レポートへ差分を掲載する（M1 Coreでは`not_applicable`表示）。Runbookは各Flagの前提テストを提示。

### 8.7 検証環境・テストデータ管理
- **ローカル環境**: `poetry shell`で仮想環境作成。`.env.test`にテスト用メール設定を定義し、本番用とは分離。
- **テストデータ**:
  - `tests/fixtures/market/`にローリング30日分の疑似OHLCVを保持。生成スクリプト`tools/gen_fixture.py`で再生成可。
  - Spread/Fundingは`fixtures/spread.csv`, `fixtures/swap_rates.csv`。バージョン管理し、差分をPull Requestでレビュー。
  - コンフィグ差分テスト用に`config/profile_test.yaml`を用意し、CIで利用。
- **CI**: M1ではローカルGit hook (`pre-push`)で`pytest -m "not m2plus"`＋`black --check`（任意）を推奨。M2でGitHub Actions導入時はmacOS runnerを利用し、スナップショットテストの差分承認を自動化。
- **データサニタイズ**: 監査ログ・レポートを共有する際は氏名/メールをマスク。`tools/redact_logs.py`で自動化。
- **負荷テスト**: `tests/load/`（将来）でSignal 100件/日シナリオをリプレイする計画。準備が整い次第CI optionalジョブとして追加。

### 8.8 リリース/デプロイプロセス
| フェーズ | 手順 | 成果物 |
| --- | --- | --- |
| 事前準備 | `git flow`でリリースブランチ作成 (`release/x.y`)。`poetry version`更新。 | リリースノート草案。 |
| 検証 | `pytest -m "m1 or m2plus"`、`tradectl backtest`(基準期間)、`tradectl preflight`。 | テストレポート、Backtest結果。 |
| 承認 | PO+運用担当が`docs/release_checklist.md`を承認。 | 承認サイン（`logs/ops/release.log`）。 |
| デプロイ | `git tag vx.y.z`, `poetry export --format requirements.txt --output requirements.lock`。 | タグ、ロックファイル。 |
| 配布 | Releaseパッケージ（zip）作成→外部ストレージへ配置。 | `dist/tradectl-vx.y.z.zip`。 |
| ポストリリース | 24hモニタリング。異常があれば即ロールバック（タグ戻し＋設定復旧）。 | Postmortemレポート。 |

- バージョニングはSemVer準拠。設定変更は`config/CHANGELOG.md`で別途管理し、アプリバージョンとセットで運用する。
- ロールバック時は最新スナップショット＋`requirements.lock`＋`config`を復元し、`tradectl preflight`→`resync`で整合を取る。
- M2でCI/CD導入後はGitHub Actionsで自動テスト→手動承認→Artifacts配布を実施する計画。

### 8.9 運用スループット計測と自動化準備
- **ワークロードメトリクス**: `ops_worklog.jsonl`を新設し、CLI操作やRunbookステップ完了時に`{"task":"manual_fallback_review","duration_min":37,"owner":"ops","source":"tradectl data manual-report"}`の形式で記録する。Typerコマンドは`--log-duration`オプションで操作時間を入力できるようにし、既定は`config/ops/workload_defaults.yaml`の標準値を採用する。
- **集計ジョブ**: `OpsWorkloadAggregator`を`src/app/telemetry.py`に追加し、毎日24:00に`ops_worklog.jsonl`を読み込んでカテゴリ別の総時間・中央値・標準偏差を計算。結果は`reports/ops/workload_<YYYYMM>.md`と`metrics/ops_workload.json`へ出力し、グラフは`tools/plot_ops_workload.py`で生成する。
- **省力化トラッカー**: 自動化タスクの効果測定のため、`automation_effect.jsonl`に`{"task":"sla_review","before_min":60,"after_min":30,"effective_date":"2025-03-10"}`を記録。`tradectl ops automation log --task sla_review --before 60 --after 30`で更新し、削減時間が30分/週以上のものに`[PRIORITY]`タグを付与してバックログ管理する。
- **アジェンダ生成**: `tradectl ops agenda --date <YYYY-MM-DD>`は`ops_worklog.jsonl`の最新値と未完了Runbook項目を組み合わせ、日次TODO Markdown（`docs/runbooks/daily_agenda/<date>.md`）とCLI出力を同時生成。Acceptable Degradation時は`HealthState`と連動して手動CSVチェックやKill Switchレビューを先頭に挿入する。
- **将来拡張**: M2ではSlack通知へ`ops agenda`を送信できるようWebhook連携を追加し、作業ログ入力のリマインダを実装する。

### 8.10 SLA閾値チューニングファクトリ
- **プロファイル構造**: `config/sla_thresholds/<profile>.yaml`は`provider`×`metric`×`window`の三次元で`target`,`warning`,`critical`を定義し、`profile_version`と`generated_at`をメタデータに含める。`health.threshold_profile`でアクティブなプロファイルを指定し、未設定時は`default`を読み込む。
- **生成スクリプト**: `tools/sla/generate_profile.py`は`metrics/data_ingestion_sla.jsonl`を入力に、(1) p50/p75/p95/p99算出、(2) 外れ値除外（IQR×1.5）、(3) 候補しきい値の提案（`warn = max(p95*1.15, p95+max(2,1σ))`、`critical = max(p99*1.25, p95+max(8,2σ))`）を行う。結果は`reports/ops/sla_review/<YYYYWW>.md`と`config/sla_thresholds/candidate_<YYYYWW>.yaml`として出力する。
- **適用フロー**: `tradectl sla profile apply --file config/sla_thresholds/candidate_<YYYYWW>.yaml`でシンタックス・単調性（`target ≤ warning ≤ critical`）を検証後、`config/sla_thresholds/active.yaml`へコピー。適用時に`health.changed(reason=sla_profile_update)`を発火し、`metrics/data_ingestion_sla.jsonl`へ`profile_version`を追記する。
- **逸脱検知**: `SlaDeviationMonitor`がローリング7日間で`observed_p95`が`warning`を連続3回超過した場合に`health.changed(reason=sla_threshold_mismatch)`を通知。通知には`current_profile_version`と直近のp95/p99値を含め、レビュー用URL（`reports/ops/sla_review/<YYYYWW>.md`）を添付する。
- **将来オートチューニング**: M2ではベイズ更新で`warning`/`critical`を自動調整するために`metrics/data_ingestion_sla.jsonl`に`posterior_mean`/`posterior_std`フィールドを追加し、学習済み値との乖離を監視する。

## 9. テスト計画とカバレッジ

| テストID | 関連AC/FR | 内容 | カテゴリ |
| --- | --- | --- | --- |
| UT-ING-01 | FR-01/FR-02 | DataIngestionが欠損補完・フォールバックする | ユニット |
| UT-FEAT-01 | FR-03 | FeaturePipeline差分更新の正当性 | ユニット |
| UT-STR-01 | FR-04 | 戦略プラグイン出力検証（MA+RSI/Donchian） | ユニット |
| UT-EXEC-01 | FR-27/FR-29 | ExecutionModelが滑り・TTLを補正 | ユニット |
| UT-RISK-01 | FR-05/FR-36 | リスク閾値超過時のReject | ユニット |
| UT-SIZE-01 | FR-06 | サイジング単調性・ロット丸め property | ユニット |
| UT-TKT-01 | FR-07/FR-38 | TicketBuilderチェックリスト生成 | ユニット |
| UT-CFG-01 | FR-14/FR-33 | Configホットリロード/遅延適用 | ユニット |
| UT-RL-01 | FR-01/AC-45 | RateLimitGuardステージ遷移（429閾値・トークン計算・手動操作記録）の検証 (`tests/unit/test_rate_limit_guard.py`) | ユニット |
| IT-PIPE-01 | AC-10 | データ→チケット統合フロー（モックデータ）＋Live実績CSV突合（`actual_fill_imported`/`summary`検証） | 統合 |
| IT-RESYNC-01 | AC-04 | Resync後TTL/ドリフト整合 | 統合 |
| IT-RL-01 | AC-45 | `tradectl data rate-limit stage` CLIと`metrics/rate_limit_window.jsonl`出力の整合（429シナリオ/Acceptable Degradation復帰） | 統合 |
| IT-SPREAD-01 | AC-34 | Spread閾値→クールダウン→解除 | 統合 |
| IT-KILL-01 | FR-05/FR-22 | Kill Switch遷移（soft/hard） | 統合 |
| IT-RISK-02 | FR-05/FR-18 | `risk_summary`が`risk_policy`閾値とKill Switchイベントに一致するか検証 (`tradectl report weekly --since 7d`) | 統合 |
| IT-FUND-01 | FR-28 | FundingService三倍日処理（CSV手動更新, 三倍日補正） | 統合 (M1 Core) |
| IT-COR-01 | FR-37 | 相関閾値でシグナル抑制 | 統合 |
| PT-CLI-01 | AC-G1/G2 | `tradectl board`操作100件連続 | CLI |
| PT-BT-01 | AC-13 | Backtest再現性（hash固定） | Property |
| FUT-SPRT-01 | FR-22(M2) | SPRTしきい値で提案停止 | 拡張 |
| FUT-SCORE-01 | AC-07/AC-08 (M2+) | `scoring.hybrid_enabled`時にPF_recent/PF_all/レジーム別PFが閾値を満たすか検証 | 拡張 |
| FUT-SCORE-02 | AC-09/AC-16 (M2+) | Stabilityスコアと±5〜10%摂動時ランク反転率をリグレッションテスト | 拡張 |

### 9.1 テストデータ戦略
- `tests/fixtures/market/`に代表的OHLCVサンプル（高ボラ/低ボラ/欠損）を配置。
- Spread/Fundingは`fixtures/spread.csv`, `fixtures/swap_rates.csv`で再現。
- CLIスナップショットは`pytest-approvaltests`で管理し、必要に応じて`--approve`で更新。

### 9.2 QAゲートと品質指標
| ゲート | 適用フェーズ | 基準/メトリクス | 判定責任 | 備考 |
| --- | --- | --- | --- | --- |
| 単体テスト | 各PR | `pytest -m "not m2plus"`成功、カバレッジ>=70% (M1目標) | 開発 | Git hook推奨。 |
| 統合テスト | スプリント末 | IT-PIPE/IT-RESYNC/IT-SPREAD/IT-KILL/IT-FUNDを通過 | 開発+運用 | CIで自動化予定。 |
| 回帰テスト | リリース候補 | Backtest差分±0.1%、CLI snapshot差異なし | 開発 | リリースチェックリスト参照。 |
| プレフライト | 本番起動前 | `tradectl preflight` OK、バックアップ確認、Kill Switch=RUNNING | 運用 | 失敗時は起動不可。 |
| UAT | 主要機能追加時 | Paperモードで2週間評価、指標が基準内 | PO+運用 | KPI (Sharpe/MaxDD)を確認。 |
| ポストリリース | リリース24h後 | 重大アラート0件、処理時間p95<1.5s | 開発+運用 | メトリクスで確認。 |

- QA指標は`metrics/qa.json`に日次で集計し、週次レポートに掲載。達成未満の場合は改善タスクを`backlog/qa_improvements.md`に登録する。

### 9.3 KPI検証とライブトラッキング
| 段階 | KPI | 手法/データ | 判定基準 | 頻度 |
| --- | --- | --- | --- | --- |
| バックテスト | Sharpe, Sortino, 最大DD, WinRate, PF | `backtest/engine.py`で複数期間評価 (全体+直近6-12ヶ月) | Sharpe≥0.8, Sortino≥1.0, MaxDD≤15%, 年率+12% | リリース毎 |
| ウォークフォワード | 同上 + Stability Score | Walk-Forward結果をヒートマップ化 | Stability Score≥0.7, 直近期間のSharpe差±0.2以内 | 四半期 |
| PaperTrade | WinRate, Expected R, Hit Ratio | Paperログ vs Backtestの乖離分析 | WinRate乖離≤5pp, Expected R乖離≤0.2R | 月次 |
| LiveTrade | Sharpe (累積/直近60日), SPRT, 偏差検定 | ライブ fills とバックテスト比較, SPRT閾値 | SPRT警告時は提案縮小、Sharpe<0.5で戦略レビュー | 週次 |
| KPIレビュー会 | KPI総括, 改善Plan | Reporter週次＋ダッシュボード | KPI未達なら改善タスク→Feature Flag調整 | 月次 |

- KPI成績は`metrics/performance.jsonl`と`reports/kpi_snapshot.md`に出力し、PO承認を得る。
- KPI未達時のアクション: `sprt_guard`で提案頻度縮小→戦略OFF→パラメータ調整→Backtest再検証。決定はPO/運用/開発のレビューで確定。
- KPI達成を維持するため、Paper/LIVE乖離が継続する場合は`walkforward`再評価とFeature Flagの切替を実施。

### 9.4 M1ベース戦略データセット/パラメータ参照

#### 9.4.1 データセット一覧
| Dataset ID | パス | TF | 期間 | ソース/備考 | `data_manifest`キー |
| --- | --- | --- | --- | --- | --- |
| `usdjpy_m5_core` | `data/research/curated/usdjpy/usdjpy_m5_20210101_20241231.parquet` | 5m | 2021-01-01〜2024-12-31 | Dukascopyベース、欠損はyfinanceで補完 | `m1_baseline.usdjpy.m5` |
| `eurusd_m5_core` | `data/research/curated/eurusd/eurusd_m5_20210101_20241231.parquet` | 5m | 同上 | Dukascopy+yfinance補完 | `m1_baseline.eurusd.m5` |
| `gbpusd_m5_core` | `data/research/curated/gbpusd/gbpusd_m5_20210101_20241231.parquet` | 5m | 同上 | Dukascopy+yfinance補完 | `m1_baseline.gbpusd.m5` |
| `eurjpy_m5_core` | `data/research/curated/eurjpy/eurjpy_m5_20210101_20241231.parquet` | 5m | 同上 | Dukascopy+yfinance補完 | `m1_baseline.eurjpy.m5` |
| `major_h1_filter` | `data/research/curated/common/majors_h1_20210101_20241231.parquet` | 1h | 2021-01-01〜2024-12-31 | 5m→1h集計済みキャッシュ | `m1_baseline.majors.h1` |
| `daily_bias` | `data/research/curated/common/majors_d1_bias.parquet` | 1d | 2020-01-01〜最新 | 日次終値Zスコア用、週次更新 | `m1_baseline.majors.d1` |
| `spread_hist` | `data/research/curated/common/spread_hist_m5.json` | 5m | 2018-01-01〜2024-12-31 | 公開CSVから生成した分位テーブル | `m1_baseline.spread.hist` |

> **保管ルール**: 生成時に`reports/data_manifest.json`へハッシュ/サイズ/取得コマンドを登録し、`reports/research/m1_baseline/validation_YYYYMMDD.md`へ`dataset_hash`を転載する。トレーダーと実装者は本表を照合して同一データセットで検証・ライブ監視を行う。

#### 9.4.2 パラメータテーブル（`strategy_manifest.yaml::strategies.m1_baseline_ma_rsi.parameters`）
> **PO/Ops合意メモ（2025-02-21）**: M1 Coreは**per-trade=0.75% / 日次=-2.5% / 週次=-5%**を正式基準とする。`risk_policy.yaml`、`config/profiles/*`, Runbook、および検証シナリオは同じ値で初期化し、逸脱時は`reports/governance/risk_policy_changes/`で承認ログを残す。
| パラメータ | 値 | 説明 | 根拠/関連要件 |
| --- | --- | --- | --- |
| `entry_tf` | `5m` | トリガー足 | 要件§3.2, FR-16 |
| `regime_tf` | `1h` | トレンドフィルタ用上位TF | 要件§3.2 |
| `ema_fast` | 21 | 5m EMA(21) | 研究ノート `reports/research/m1_baseline/validation_*.md` |
| `ema_slow` | 55 | 5m EMA(55) | 同上 |
| `ema_slope_window` | 8 | 1h EMA傾き計算バー数 | 遅延ノイズ緩和 |
| `rsi_period` | 14 | RSI基準期間 | 標準設定 |
| `rsi_long_thresholds` | `[45, 55]` | ロング判定: 45→55クロス | 要件§3.2シグナル |
| `rsi_short_thresholds` | `[55, 45]` | ショート判定: 55→45クロス | 同上 |
| `atr_period` | 14 | ATRベースボラ計測 | 要件§3.2, FR-27 |
| `atr_sl_mult` | 1.2 | 初期SL=ATR×1.2 | 要件§3.2リスク |
| `tp_r_multiple` | 2.0 | TP=2R（ATR基準） | 要件§3.2, AC-07 |
| `protect_pips` | 3.0 | Marketable Limit保護幅 | FR-39 |
| `spread_guard_multiplier` | 2.0 | Spread許容=通常分位×2 | 要件§3.2フィルタ |
| `decision_delay_triangular` | `[30,45,75]` | 手動遅延の三角分布(sec) | 要件§3.2, AC-09 |
| `per_trade_risk_pct` | 0.75 | 1トレードリスク（口座残高比） | 要件§3.2リスク |
| `daily_drawdown_stop_pct` | 2.5 | 日次Kill Switch | 要件§3.2 |
| `weekly_drawdown_stop_pct` | 5.0 | 週次Kill Switch | 要件§3.2 |
| `max_concurrent_positions` | `{bucket:2,total:4}` | 通貨バケット/全体上限 | 要件§3.2, AC-09 |
| `r_eff_cap` | 2.5 | 相関合算R上限 | 要件§3.2 |

#### 9.4.3 検証シナリオ（実装者/トレーダー共通）
| Scenario ID | コマンド / ノート | 期待結果 | 対応AC |
| --- | --- | --- | --- |
| `BT-IS` | `tradectl backtest run --strategy m1_baseline_ma_rsi --profile paper-m1-baseline --from 2021-01-01 --to 2023-06-30 --out reports/backtest/m1_baseline/is` | `PF=1.20±0.05`, `Sharpe=0.90±0.05`, 取引数≈260（IS） | AC-07 |
| `BT-OOS` | `tradectl backtest run --strategy m1_baseline_ma_rsi --profile paper-m1-baseline --from 2023-07-01 --to 2024-12-31 --out reports/backtest/m1_baseline/oos` | `PF≥1.10`, `Sharpe=0.88±0.07`, `MaxDD≤13%`, `HitRate=48〜55%` | AC-07 |
| `STRESS-SPREAD+50` | `tradectl backtest run ... --what-if spread=1.5,slip=1.5` | レジーム別PF中央値≥1.0、`MaxDD`増分≤+3% | AC-08 |
| `RISK-DIAG` | `tradectl diagnostics risk --strategy m1_baseline_ma_rsi --from 2023-07-01 --to 2024-12-31 --mode backtest` | `per_trade_R_stdev∈[0.70,0.80]`, `max_concurrent`違反0件、`R_eff_cap`違反0件 | AC-09 |
| `LATENCY-PAPER` | `tradectl metrics latency --mode paper --from 2024-01-01 --to 2024-12-31` | 承認→OCO設定 `median≤60s`, `p90≤120s`, 遅延サンプル>200 | AC-09 |

> **シナリオ運用メモ**: 各シナリオで生成された`metrics.json`/`stress_tests.json`/`latency_stats.json`は`reports/research/m1_baseline/validation_YYYYMMDD/`配下に保存し、週次レビューで`reports/weekly/<YYYY-WW>.md`へ転載する。閾値逸脱時は`strategy.watchlist`を付与し、再検証チケット（`tickets/strategy_revalidation/<date>.md`）を起票する。

#### 9.4.4 データ品質・ガード連携
- `multi_tf_joiner`はIS/OOS区間の欠損率・再計算範囲を`reports/research/m1_baseline/data_quality.json`へ出力し、欠損率>0.5%/日でAC-22のアラートテストを再実行する。
- Spread分位テーブルは`reports/research/m1_baseline/spread_verification.md`に直近90営業日のp50/p95/p99を記録し、Spread Guard閾値2.0×が適切かを四半期レビューで確認する。
- 手動遅延ログ（Paper/Live）は`logs/hitl/latency_samples.jsonl`に追記し、月次で`reports/performance/<mode>/latency_stats.json`へ集計する。90パーセンタイルが閾値を超えた場合はRunbook `HITL-LATENCY`の改善アクションを実施する。

### 9.5 Codex QAハーモニクス（v2.0追加）
- **3レイヤーQA**: Unit（高速）、Integration（実データ結合）、Scenario（Runbook追従）の3段階を必須化する。Codexは各PRで最低1件ずつサンプルを提出し、`docs/qa/results/<date>_<epic>.md`へ実行ログを貼付する。
- **データ拘束条件**: `tests/fixtures/market/usdjpy_m5_sample.parquet`などの縮小版データを使用し、個人情報や機密ロジックを含まないことを確認する。必要に応じて`tools/make_fixture.py`で最新データから縮小サンプルを生成し、ハッシュを`reports/data_manifest.json`に登録する。
- **しきい値追跡**: テストで使用する性能/SLA閾値は`tests/thresholds.yaml`に集約し、変更時は`docs/change_requests/threshold_update_<date>.md`へ理由と影響範囲を記録する。閾値変更はPO承認必須。

| QAレイヤー | コマンド例 | 入力データ/モック | 合格基準 | 失敗時の処置 |
| --- | --- | --- | --- | --- |
| Unit | `pytest tests/unit/test_rate_limit_guard.py` | `tests/fixtures/rate_limit/log_stage0.jsonl` | Stage遷移ロジックが仕様通り、429率閾値判定が正しい | Prompt Bundleへ失敗ケース追記、`rate_limit_stage_eval`再現手順をRunbookに記載 |
| Integration | `pytest tests/integration/test_pipeline_end_to_end.py` | `tests/fixtures/market/usdjpy_m5_sample.parquet`, `tests/fixtures/config/profile_paper.yaml` | Backtest/Paper/Live共通フローで同一チケットが生成される | データ差異は`reports/validation_log/<date>_integration.md`に記録し、`data_manifest`との差分を調査 |
| Scenario | `tradectl scenario run --id AC-45 --profile paper-m1-core` | Runbook手順、`data/manual_fallback/*`双子CSV（サンプル） | Acceptable Degradationチェックリスト全項目パス、`degraded_ack`記録あり | Runbook更新と`feedback_loop.md`への反省点記録、Hardeningフェーズで再実行 |

- **自動収集**: `make qa-report`が上表のテスト結果を集約し、`reports/qa/<date>.md`へ出力する。CIでは`make qa-report --ci`を週次で回し、合格証跡を残す。
- **Codexハンドオーバー**: PRマージ前にCodexへ`qa-report`の要約と`feedback_loop.md`の該当行をフィードバックし、次回プロンプト改善へ反映する。

## 10. 要件トレーサビリティ

| 要件ID | 本書記載箇所 |
| --- | --- |
| FR-01, FR-02 | §3.1, §3.2, §4.1, §5.2 |
| FR-03 | §3.3, §5.2 |
| FR-04 | §3.5, §5.2 |
| FR-05 | §3.8, §3.9, §5.3, §7 |
| FR-06 | §3.11 |
| FR-07, FR-38 | §3.16, §4.3, §5.5 |
| FR-08 | §2.1, §2.2, §5.2 |
| FR-09 | §3.17, §5.7 |
| FR-10 | §3.18 |
| FR-11 | §2.4, §3.20, §4.5 |
| FR-12 | §3.9, §3.19, §7 |
| FR-13 | §3.13, §5.2 |
| FR-14, FR-33 | §3.19, §4.4, §5.6 |
| FR-15 | §3.13 |
| FR-16, FR-18 | §2.1, §2.4, §3.15, §5.1 |
| FR-17 | §3.16, §5.5 |
| FR-19, FR-21 | §3.7（M2+ハイブリッド設計）, §3.17 |
| FR-20 | §3.4 |
| FR-22 | §3.8, §3.9, §7 (M2フック含む) |
| FR-23 | §3.19, §5.6 |
| FR-24 | §3.11, §4.4 |
| FR-25 | §8 |
| FR-26 | §3.13, §5.2 |
| FR-27 | §3.6, §5.2 |
| FR-28 | §3.12 |
| FR-29 | §3.6 |
| FR-30 | §3.16 |
| FR-31 | §3.14, §4.1 |
| FR-32 | §2.4, §3.1, §5.1 |
| FR-34 | §3.6, §5.4 |
| FR-35 | §3.16, §3.17 |
| FR-36 | §3.8 |
| FR-37 | §3.10 |
| FR-39 | §3.6, §3.16 |
| FR-40 | §3.13, §5.2 |
| FR-41 | §3.6, §5.4 |
| FR-42 | §3.10 (M2+), §5.3 |
| FR-61 | §1.3, §3.25, §5.11, §7.3 |
| FR-62 | §1.3, §3.26, §3.28, §5.11, §7.3 |
| FR-63 | §1.3, §3.27, §5.12, §7.3 |
| FR-64 | §1.3, §3.29, §5.13, §7.3 |
| AC-G1/G2 | §2.6, §5.5 |
| NFR-04/05/06/07/08/11 | §8 |

## 11. リスクと未解決課題

### 11.1 技術的リスク
- **執行モデルの実績データ不足**: ブローカーAPI未連携のため、滑り・ヒューマン遅延パラメータの検証が限定的。Paper/LIVE実績から`execution_model.yaml`を半月ごとに更新する運用手順をRunbookに追記予定。
- **Reduce-Only運用負荷**: Spread/相関異常時に提案が集中する可能性。M1では手動レビューだが、M2で優先度キューとバッチ操作UIを設計する。
- **SPRTチューニング**: 戦略追加時にSPRT閾値が不安定。ウォームアップ期間とベイズ更新をM2バックログに登録。
- **データ供給レイテンシ**: macOSローカル運用でネットワーク品質が不安定な場合、Catch-up時間が延びる。`provider.timeout`と`retry`を調整し、長時間停止時はバックフィルを分割する。

### 11.2 運用課題
- Spread/Funding CSVの手動更新頻度が高い場合、Human Errorが発生しやすい。将来的に自動取得スクリプトを追加し、`logs/ops`へ自動記録する計画。
- Snapshot破損や`hard_stop`後の復旧訓練を四半期ごとに実施し、Runbookの精度を高める必要がある。
- `tradectl` CLIのUX向上（検索/絞り込み）とGUI化（M2）を段階的に検討。

### 11.3 リスクログ (2025-02時点)
| ID | リスク概要 | 影響 | 発生確率 | 緩和策 | ステータス |
| --- | --- | --- | --- | --- | --- |
| R-01 | API仕様変更によるデータ取得停止 | 中 | 中 | API監視/代替CSV準備 | 監視中 |
| R-02 | 運用者不在時のアラート未対応 | 高 | 中 | RACI整備、代替手順、Kill Switch STOP | 対策中 |
| R-03 | ローカル端末故障で運用停止 | 高 | 低 | 予備端末準備、バックアップ/BCPテスト | 監視中 |
| R-04 | コンフィグ誤編集 | 中 | 中 | Configレビュー、dangerousキー遅延適用 | 監視中 |
| R-05 | 監査ログ肥大化 | 低 | 中 | 週次アーカイブ、自動圧縮 | 対策中 |
| R-06 | セキュリティインシデント（端末盗難） | 高 | 低 | FileVault, 画面ロック, Keychain管理 | 監視中 |
| R-07 | KPI未達（Sharpe/MaxDD） | 中 | 中 | 戦略評価会、最適化、Feature Flag | 監視中 |

- リスクログは月次レビュー時に更新し、閾値を超えたリスクはIssue Trackerへ登録する。

---

本詳細設計は要件定義・基本設計に基づき、M1リリースの実装に必要なインターフェース・データモデル・フロー・テスト計画を整備した。拡張機能はFeature Flagとガバナンス手順を通じて安全に段階導入できるよう設計している。

## 12. 付録

### 付録A: Health/Kill Switch状態遷移簡易図
```
ok ──(spread degrade / data warn)──▶ degraded
▲                                   │
│  (auto recovery)                  │ (drawdown / heartbeat timeout / manual stop)
└──────────────▶ soft_stop ──(audit failure / snapshot corruption)──▶ hard_stop
                                   │                                     │
                                   └────(cause resolved + ack)───────────┘
```
- 各遷移は`HealthStateChanged`イベントでログに残り、`alert_id`でRunbookと紐付く。

### 付録B: Feature Flag導入チェックリスト
| Flag | 有効化前提テスト | ロールバック手順 |
| --- | --- | --- |
| `sprt_guard` | IT-KILL-01, FUT-SPRT-01, Paperモードで2営業日連続稼働 | Flagをfalseに戻し、`HealthMonitor.reset_kill_switch()`後Resync。 |
| `reduce_only_advisor` | Spread異常シナリオ再現、Runbookトレーニング完了 | Flagをfalseに、Reduce-Onlyキューを手動クリア。 |
| `slack_alert` | SMTP併用試験、Webhook疎通テスト | Flag false、`Dispatcher`をSMTPへ戻す。 |
| `gui_ws` | `/ws/signals`負荷テスト、GUI利用トライアル | Flag false、CLIのみで運用。 |

### 付録C: CLI操作例
```
$ tradectl board --filter symbol=USDJPY
[12:05:00][ticket_issued] id=TK-20250220-001 score=84.2 TTL=14:59 spread_ok✓ news_ok✓

$ tradectl ticket approve --id TK-20250220-001 --note "追随"
[INFO] ticket.approve: Ticket TK-20250220-001 approved, audit logged.

$ tradectl status --verbose
Mode: LIVE | Health: degraded(data_quality) | KillSwitch: STOP
SpreadCooldown: cooldown (ETA 12:15) | Snapshot hash: a1c3...
```
- エラー時ログは`logs/ops/cli.log`に二重化し、Runbookのトラブルシュート手順と連携する。


### 付録D: エラーコードと通知マッピング
| エラーコード | 重大度 | 発火元 | 通知チャネル | Runbook参照 |
| --- | --- | --- | --- | --- |
| ERROR-C01 (データ欠損) | WARN/MAJOR | DataQualityGuard | CLI + メール(WARN) | Runbook §2.1 |
| ERROR-C02 (指標計算失敗) | CRITICAL | FeaturePipeline | CLI + メール(CRITICAL) | Runbook §2.2 |
| ERROR-C03 (Config検証NG) | WARN | ConfigRegistry | CLI | Runbook §3.1 |
| ERROR-C04 (監査ログ書込失敗) | CRITICAL | AuditWriter | CLI + メール(CRITICAL) | Runbook §4.3 |
| ERROR-C05 (Spread欠損) | WARN | SpreadMonitor | CLI + メール(WARN) | Runbook §2.3 |
| ERROR-C06 (Funding未更新) | WARN | FundingService | CLI | Runbook §2.4 |
| ERROR-C07 (Heartbeat停止) | MAJOR | HealthMonitor | CLI + メール(MAJOR) | Runbook §5.1 |
| ERROR-C08 (Snapshot破損) | CRITICAL | SnapshotManager | CLI + メール(CRITICAL) | Runbook §4.1 |
| ERROR-C09 (Account CSV不整合) | MAJOR | AccountService | CLI + メール(MAJOR) | Runbook §3.2 |
| ERROR-C10 (Scheduler遅延) | WARN | Scheduler | CLI | Runbook §2.3 |

- `AlertDispatcher`は重大度ごとに件名 `[tradectl][<SEVERITY>] <reason>` を付与する。Slack/Webhook有効時は同じpayloadを送信。
- Runbook参照欄は対応手順を示し、アフターアクションレビューで更新する。

### 付録D: エラーコードと通知マッピング
| エラーコード | 重大度 | 発火元 | 通知チャネル | Runbook参照 |
| --- | --- | --- | --- | --- |
| ERROR-C01 (データ欠損) | WARN/MAJOR | DataQualityGuard | CLI + メール(WARN) | Runbook §2.1 |
| ERROR-C02 (指標計算失敗) | CRITICAL | FeaturePipeline | CLI + メール(CRITICAL) | Runbook §2.2 |
| ERROR-C03 (Config検証NG) | WARN | ConfigRegistry | CLI | Runbook §3.1 |
| ERROR-C04 (監査ログ書込失敗) | CRITICAL | AuditWriter | CLI + メール(CRITICAL) | Runbook §4.3 |
| ERROR-C05 (Spread欠損) | WARN | SpreadMonitor | CLI + メール(WARN) | Runbook §2.3 |
| ERROR-C06 (Funding未更新) | WARN | FundingService | CLI | Runbook §2.4 |
| ERROR-C07 (Heartbeat停止) | MAJOR | HealthMonitor | CLI + メール(MAJOR) | Runbook §5.1 |
| ERROR-C08 (Snapshot破損) | CRITICAL | SnapshotManager | CLI + メール(CRITICAL) | Runbook §4.1 |
| ERROR-C09 (Account CSV不整合) | MAJOR | AccountService | CLI + メール(MAJOR) | Runbook §3.2 |
| ERROR-C10 (Scheduler遅延) | WARN | Scheduler | CLI | Runbook §2.3 |

- `AlertDispatcher`は重大度ごとに件名 `[tradectl][<SEVERITY>] <reason>` を付与する。Slack/Webhook有効時は同じpayloadを送信。
- Runbook参照欄は対応手順を示し、アフターアクションレビューで更新する。

### 付録E: ログ/メトリクスタグ規約
| タグ | 対象ログ | 意味 | 例 |
| --- | --- | --- | --- |
| `signal.*` | `logs/events` | シグナル生成/評価プロセス | `signal.generated`, `signal.rejected.low_score` |
| `risk.*` | `logs/events` | リスク評価/Kill Switch関連 | `risk.reject.margin`, `risk.kill_switch.soft_stop` |
| `report.generated` | `reports/` | レポート生成 | `weekly_report` |
| `governance.action_item` | `reports/meetings/` | アクションアイテム | `ops_automation` |
| `validation.playbook` | `reports/validation_log/` | Validation Data Playbookエントリ | `AC-45_20250301` |
| `rate_limit.*` | `metrics/rate_limit_window.jsonl`, `logs/audit/rate_limit.jsonl` | RateLimitステージ評価/手動操作ログ | `rate_limit.stage_suggest`, `rate_limit.stage_set` |

### 付録F: Validation Data Playbookテンプレート
```
---
id: AC-XX-<YYYYMMDD>
requirement: <FR/AC番号>
dataset: <データセット名 or ファイルパス>
hash: <SHA256>
source: <取得元URL/Runbook手順>
owner: <記録者>
reviewer: <サイン者>
due_date: <YYYY-MM-DD>
status: pending | provisional | confirmed
fallback_applied: true | false
fallback_reason: <欠損補完理由>
linked_runbook: docs/runbooks/RUN-XXXX-YY.md
---

## 1. 受け入れ条件
- [ ] データ期間: <例: 2024-01-01〜2024-01-31>
- [ ] 欠損率 ≤ <閾値>
- [ ] 二重入力ハッシュ一致

## 2. 検証ログ
| チェック | 実施者 | 実施日時 | 結果 | 証跡 |
| --- | --- | --- | --- | --- |
| レコード件数検証 |  |  |  |  |
| スキーマ検証 (`tools/validate_schema.py`) |  |  |  |  |
| ハッシュ再計算 (`tradectl data hash`) |  |  |  |  |

## 3. コメント
-

## 4. サインオフ
- 運用者: <署名/日時>
- PO: <署名/日時>

```
- テンプレートは`reports/validation_log/templates/playbook_entry.md`として保管し、`tradectl validation new`が本雛形をもとにエントリを生成する。`due_date`超過で`status∈{pending,provisional}`の場合は`tradectl validation audit`が`severity=warn`イベントを発行する。
| `ticket.*` | `logs/audit` | HITL操作 | `ticket.approve`, `ticket.edit.sl` |
| `cfg.*` | `logs/events` | 設定変更/検証 | `cfg.change.safe`, `cfg.reject.schema` |
| `spread.*` | `metrics/network.jsonl` | スプレッド監視 | `spread.cooldown.start`, `spread.cooldown.clear` |
| `preflight.*` | `logs/ops/preflight.log` | プレフライト結果 | `preflight.fail.ntp` |
| `backup.*` | `logs/ops/backup.log` | バックアップ実行情報 | `backup.weekly.ok` |
| `perf.*` | `metrics/pipeline.jsonl` | パフォーマンス指標 | `perf.step.feature_update` |
| `alert.*` | `logs/events`, メール | アラート通知 | `alert.warn.network`, `alert.critical.audit` |

- ログは`orjson`で出力し、`tag`フィールドを必須化。タグプレフィックスでフィルタリングを容易にする。
- メトリクスはJSONLのほか、M2でPrometheus Exporterを実装する際に同タグをラベルに使用する。

### 3.30 RiskDisclosureService (`src/compliance/risk_disclosure.py`)
- **公開API**: `fetch_state()`（最新承諾ステータス取得）、`prompt(current_state)`（CLI対話の起動）、`record_consent(decision, metadata)`（承諾/拒否イベントの保存）、`link_event(consent_id, event_payload)`（監査イベントへの紐付けヘルパ）。
- **データモデル**: `ConsentState`は`status∈{accepted,pending,expired,warning}`、`consent_version_hash`, `accepted_at`, `expires_at`, `device_fingerprint`, `last_prompted_at`を保持。永続化は`consent_state.json`（ローカル）と`logs/audit/risk_consent_*.jsonl`（イベント）。
- **M1 Core実装**: `fetch_state()`で期限切れ/未承諾の場合は`status=pending`を返し、Signal Boardは読み取り専用モードへ切り替える。`prompt()`は承諾文面を表示せずRunbookリンクとTODOを出すのみで、ユーザーが`--ack`オプションで暫定承諾時刻を記録できる。`record_consent()`は`consent_state.json`更新と`audit`イベントへ`consent_warning=true`フラグを付与するが、高リスク操作はブロックしない。`link_event()`は`consent_reference_id=None`のまま警告を残す。
- **M1.1以降の拡張**: `prompt()`がMarkdownダイアログ（投資助言禁止・主要リスク・損失可能性・利用範囲・約款リンク・前回承諾ログ）を描画し、承諾完了までは`ConsentRequiredError`を発生させてCLI制御を停止。`record_consent()`は`audit`イベントストアへ`risk_consent`エントリをWORM保存し、`consent_reference_id`と`consent_version_hash`を返却。`link_event()`は各操作イベントへ上記IDを付与し、週次ガバナンスレポートと`tradectl audit export --type risk_consent`に連携する。拒否時は`status=warning`を維持し、Signal Boardは高リスク操作を不可・低リスク閲覧もロックする。
- **異常系**: `consent_state.json`破損→`ConsentStateCorrupted`例外で`BoardMode=halted(consent)`へ遷移。`audit`書き込み失敗時はM1 CoreではWARNログのみ、M1.1では`HealthMonitor.soft_stop(consent_audit)`でKill Switchを保持し再承諾を禁止する。
- **設定**: `config/compliance/risk_disclosure.yaml`に承諾有効期間（日数）、文面ファイルパス、端末識別子算出方式（シリアル+MACハッシュ）、四半期レビュー週定義、Runbookリンクを定義。M1 Coreでは`enforce=false`、M1.1以降は`enforce=true`として同一コードパスで切り替える。

### 付録G: ガバナンスサービス（M2+実装ガイド）

#### 付録G.1 Strategy Scoreboard Service (`src/scoreboard/service.py`)
- **公開API**: `generate_weekly_snapshot(week_ending)`, `get_latest()`, `trigger_watchlist(strategy_id)`。
- **入力データ**: `data/returns/returns_24w.parquet`, `metrics/kpi_cache.parquet`, `reports/research/alpha_score/<YYYYWW>.md`, 戦略ごとの`reports/strategy_review_<id>.md`。
- **主要ロジック**: KPIキャッシュからPF/Sharpe/Stabilityを標準化→`decay_score`は24週リニア回帰から傾きを算出。`alpha_score`<`config.scoreboard.alpha_threshold`または`decay_score`>`config.scoreboard.decay_threshold`で`strategy.watchlist`イベントをEventBusへ送信（AC-49, FR-61）。
- **イベント/連携**: `scoreboard.generated`でJSONサマリを`scoreboard/alpha/<YYYYWW>.json`と`reports/research/alpha_score/<YYYYWW>.md`へ書き込み。`strategy.watchlist`受信時にTicketBuilderへウォーニングバッジを追加、Model Risk Register Serviceへ`watchlist=true`を通知。
- **異常系**: KPI計算失敗→`ScoreboardComputationFailed`イベント→`HealthMonitor.degraded(scoreboard)`。証跡Markdown欠損時は`evidence_missing`フラグを立て、Ops Readiness Evaluatorにも不足として反映。
- **設定ファイル**: `config/scoreboard.yaml`（閾値、重み、対象戦略リスト、runbookリンク）。週次ジョブは`config.scheduler.jobs.scoreboard`で定義し、SessionManager起動時に`AsyncOneShotJob`として登録。

#### 付録G.2 Idea Pipeline Manager (`src/ideas/manager.py`)
- **公開API**: `load_manifest(idea_id)`, `transition_stage(idea_id, target_stage, actor)`, `validate_evidence(idea_id)`。
- **入力データ**: `ideas/<id>/manifest.yaml`, `ideas/<id>/evidence/*.md`, `ideas/<id>/metrics/*.json`, チェックリストテンプレート`ideas/templates/checklists/<stage>.md`。
- **主要ロジック**: `manifest`を`schema.py`で検証し、`stage`遷移要求ごとにチェックリスト完了率とPaper整合ログを評価。Paper移行には4週連続で`consistency_score`>=`config.ideas.paper_gate.min_consistency`を要求し、未達時は`stage.blocked`イベントを返却し`ideas/<id>/actions.md`へTODOを追記（FR-62, AC-49）。
- **イベント/連携**: `stage.changed`でReporterに通知し、Strategy Scoreboard Serviceへ新規戦略登録を要求。Model Risk Register Serviceは`stage=live_candidate`到達時に初回評価タスクを起票。
- **異常系**: 必須ファイル欠損→`IdeaEvidenceMissing`で`HealthMonitor.degraded(idea_pipeline)`、Ops Readiness Evaluatorにも不足が反映。`manifest`スキーマ違反は`ConfigRejected`同様に扱い、ステージはロールバック。
- **設定ファイル**: `config/ideas.yaml`（ステージ順序、必須証跡種別、整合度閾値、Runbook ID）。CLI `tradectl research stage`は`manager.transition_stage`を呼び出し監査ログに記録。

#### 付録G.3 Ops Readiness Evaluator (`src/ops_readiness/evaluator.py`)
- **公開API**: `evaluate(period)`, `explain(period)`, `record_override(reason, actor)`。
- **入力データ**: `reports/governance/ops_readiness_<YYYYWW>.md`, `logs/ops/backup.log`, `docs/runbook/*.md`, `ops_readiness/evidence/*.json`, バックアップ検証結果`reports/drill/*.md`。
- **主要ロジック**: 証跡ファイルの存在・ハッシュを`evidence.py`で検証し、バックアップ整合度/Runbook更新率/演習完遂率/緊急プロトコル検証スコアを加重平均。`ops_readiness_score`<`config.ops_readiness.min_score`で`health.changed(status=degraded, reason="ops_readiness_low")`を発火しKill Switchを`soft_stop`へ誘導（FR-63, AC-51）。
- **イベント/連携**: `ops_readiness.evaluated`でスコアと欠損証跡リストをEventBusに出力。ScoreboardジョブはOpsスコア<閾値の場合に`alpha_score`を最大70へクリップしリリースを防止。Idea Pipeline ManagerはOps低下中に新規Paper昇格を保留。
- **異常系**: 証跡が404またはハッシュ不一致→該当項目スコア0かつ`OpsEvidenceMissing`イベント。評価実行中にIO例外が連続した場合は`health.changed(reason="ops_readiness_blocked")`でKill Switchを維持し、手動確認をRunbook `OPS-READINESS-01`に記録。
- **設定ファイル**: `config/ops_readiness.yaml`（重み、閾値、必須証跡パス、Runbook ID、評価スケジュール）。週次自動実行ジョブをSchedulerに登録し、CLI `tradectl ops readiness --explain`で内訳を取得。

#### 付録G.4 Model Risk Register Service (`src/governance/model_risk.py`)
- **公開API**: `scan_register()`, `open_gap(strategy_id, reason)`, `resolve_gap(gap_id, evidence_paths)`。
- **入力データ**: `model_risk_register.md`, `reports/model_risk/<strategy>.md`, `tickets/model_revalidate/*.md`, Scoreboardの`watchlist`フラグ。
- **主要ロジック**: `scan_register`が`model_risk_register.md`をAST解析し、各戦略の最終評価日/担当/エビデンスリンクを抽出。未更新>90日、Explainability添付欠落、`watchlist=true`でタスク未完了の場合は`model_risk_gap`を生成しEventBusへ通知（FR-62, AC-49）。
- **イベント/連携**: `model_risk.gap_opened`でOps Readiness Evaluatorへ通知しOpsスコアからペナルティ。`resolve_gap`完了時は`model_risk.gap_resolved`を発火し、Scoreboardへ解除を通知。Kill Switch解除条件に`gap_status=closed`が追加される。
- **異常系**: Registerファイル解析失敗→`ModelRiskRegisterCorrupted`で`HealthMonitor.soft_stop(model_risk)`。証跡リンク無効時は`OpsEvidenceMissing`と同じ扱いでOpsスコアを強制減点。
- **設定ファイル**: `config/model_risk.yaml`（評価周期、必須ドキュメント、担当者マッピング、ギャップ閾値）。CLI `tradectl model risk resolve <id>`は`resolve_gap`を呼び出し監査ログにエビデンスハッシュを記録。

#### 付録G.5 Statement Reconciliation Service (`src/reconciliation/service.py`)
- **公開API**: `reconcile(from_date, to_date, mode)`, `load_statement(path)`, `export_summary(result)`。
- **入力データ**: ブローカーステートメント（CSV/PDF→CSV）、`logs/audit/*.jsonl`, `reports/audit/trade_log.parquet`, `account/balances.parquet`, Idea/Ticket履歴。
- **主要ロジック**: `normalizer.py`でステートメント形式を標準化し、`matcher.py`でLive/Paperログと突合。残高差分> `config.reconciliation.max_balance_delta_r`または取引突合率<`config.reconciliation.min_match_pct`で`HealthMonitor.degraded(statement_gap)`および`reconciliation.discrepancy`イベントを発火（FR-64, AC-53）。
- **イベント/連携**: 正常終了時は`reconciliation.completed`でOps Readiness Evaluatorへスコア加点、Reporterが`reports/audit/reconciliation/<date>.md`を生成。差分時はKill Switchを`soft_stop`に遷移し、Idea Pipeline Managerが新規昇格を停止。
- **異常系**: ステートメントファイル欠損/解析失敗→`StatementImportError`でリトライ案内。差分特定不可の場合は`reconciliation.escalated`を発火しRunbook `AUD-REC-02`手順へ誘導。証跡出力失敗はOps Readiness Evaluatorの証跡欠損として扱う。
- **設定ファイル**: `config/reconciliation.yaml`（ブローカー別カラムマッピング、差分閾値、フェイルセーフ条件、Kill Switchハンドリング）。CLI `tradectl reconcile statements --from <date>`が`reconcile`を呼び出し監査に結果を追記。

### 付録H: トレーダー運用シナリオ（M1 Core運用ガイド）

HITLトレーダーとCodex開発者が同じ前提でレビューできるよう、代表的な運用シナリオごとの「検知→判断→操作→検証」手順を以下に整理する。Runbook参照番号とCLIコマンド、必要メトリクスを明示し、Acceptable Degradation移行時の判断材料を平文化する。

| シナリオ | トリガー指標 | トレーダーの判断ポイント | Codex実装フック | 推奨CLI/ツール | Runbook/Validationリンク | 復旧完了チェック |
| --- | --- | --- | --- | --- | --- | --- |
| 正常稼働 (`OPS-NOMINAL`) | `HealthState=ok`, `board_mode=normal`, `catch_up_lag_minutes<10` | 週次レビューまでにSharpe/最大DD/WinRateを記録し、KPI未達なら改善チケット起票 | Reporter (`§3.18`), KPI Snapshot (`§9.3`) | `tradectl board`, `tradectl status`, `tradectl report weekly --dry-run` | `RUN-OPS-04`, `reports/weekly/<YYYYWW>.md` | KPIサマリと`reports/kpi_snapshots`が最新、`logs/audit/ticket.jsonl`に異常なし |
| Acceptable Degradation移行 (`OPS-DEG-01`) | `catch_up_lag_minutes≥30` or `HealthState=degraded(data_latency_*)` | Guardedへ切替えるか、手動CSV投入で凌ぐか。主要4ペアのデータ鮮度と429頻度を確認 | DataIngestionService (`§3.1`), RateLimitGuard (`§3.1.1`), Board Guard Policy (`§3.8`) | `tradectl board --guarded`, `tradectl data failover --mode manual`, `make sla-report` | `RUN-DATA-05`, `RUN-DATA-06`, `reports/validation_log/AC-45_sla_<date>.md` | `catch_up_lag_minutes<30`、`metrics/rate_limit_window.jsonl`で429率回復、`degraded_ack`イベントをRunbookでサイン |
| Spread急拡大 (`RISK-SPREAD-02`) | `SpreadCooldownState=cooldown`, `spread_pips>threshold` | Reduce-Only運用に移行し、ニュース/カレンダーと矛盾がないか確認 | SpreadMonitor (`§3.6`), CalendarService (`§3.13`), Risk Manager (`§3.8`) | `tradectl spread status`, `tradectl board --guarded --reason spread`, `tradectl calendar upcoming --impact high` | `RUN-RISK-02`, `RUN-HITL-01` | Spreadが閾値内へ連続Nバー収束、`reports/performance/<mode>/spread_review.md`に結果記録、Kill Switch解除サイン取得 |
| Rate Limit退行 (`OPS-RL-03`) | `metrics/rate_limit_window.jsonl`で`rolling_1h_429_rate>1.5%` or `consecutive_429≥3` | Stageを下げる/ポーリング停止/手動CSV投入の優先度を判断 | RateLimitGuard (`§3.1.1`), ManualCsvIngestionTask (`§3.1`) | `tradectl data rate-limit stage inspect`, `tradectl data rate-limit stage set 0 --provider yfinance`, `tradectl benchmark validate-manual` | `RUN-DATA-05`, `reports/validation_log/AC-45_sla_<date>.md` | `rolling_1h_429_rate<1.0%`に回復、Stage履歴とRunbookチェックが一致、`manual_csv.log`にダブルサイン |
| Live fills取り込み (`OPS-ACCT-04`) | 取引実績CSVの新規行、`logs/audit/live.jsonl`未反映チケット | CSV整合→スリッページ評価→Journal更新。欠損時はKill Switch soft_stop検討 | AccountService (`§3.14`), Trade Journal (`§3.14.1`), Reporter (`§3.18`) | `tradectl account sync --path data/account/live_account.csv`, `tradectl journal summarize`, `tradectl audit export --type live` | `RUN-OPS-03`, `reports/validation_log/AC-44_live_fill_<date>.md` | `actual_fill_imported`イベントが全件生成、`unmatched_ticket`が0、週次レポートにスリッページ統計掲載 |
| Kill Switch発動 (`RISK-KS-05`) | `daily_loss`/`weekly_loss`閾値超、`HealthMonitor`推奨`hard_stop` | 即時停止/Reduce-Only/再開判断。承認ログとスナップショット整合を確認 | Risk Manager (`§3.8`), Health Monitor (`§3.9`), SnapshotManager (`§3.15`) | `tradectl kill-switch engage --reason <code>`, `tradectl snapshot verify`, `tradectl health ack --reason hard_stop` | `RUN-RISK-01`, `RUN-POST-03`, `reports/ops/incidents/<date>_killswitch.md` | `kill_switch_events.jsonl`に承認者記録、`snapshot hash`一致、`tradectl board --normal`実行時にRunbook承認済 |

#### 付録H.1 シナリオ遂行チェックリスト

各シナリオ実行時は以下の共通チェックリストをRunbook添付で管理する。

1. **検知証跡**: トリガーとなったメトリクス/イベントファイルのパスとハッシュをRunbookに記載。
2. **オペレーションログ**: 実行したCLIコマンドと引数を`logs/ops/command.log`へ記録し、承認者を添付。
3. **Codex差分レビュー**: 対応中に発生したコード/設定の変更点を`docs/prompt_packages/<date>_<scenario>.md`へ追記し、次回再発時のプロンプト準備を短縮。
4. **事後レビュー**: `RUN-POST-03`のテンプレートに沿って原因分析・恒久対策・フォローアップIssueを整理。Acceptable Degradation時は「復旧目標時間」「実績時間」「差異理由」を必ず記録。
5. **メトリクス確認**: 復旧後30分以内に`metrics/data_ingestion_sla.jsonl`・`metrics/rate_limit_window.jsonl`・`reports/weekly`の該当箇所をチェックし、未回復指標があれば`HealthMonitor`へ再通知。

Codexは上記シナリオを前提にテストデータ/ログを準備し、PR説明時に「対象シナリオ」「操作ステップ」「検証結果」を必ず紐付ける。トレーダーはRunbookに沿った証跡をレビューし、承認サインを`reports/validation_log`系ドキュメントへ記録する。

## 13. Codex開発準備チェックリスト（v2.4追加）

Codexへ実装タスクを引き渡す際に必要な準備作業を標準化し、スプリントごとの手戻りを防ぐ。以下のチェックリストはIssue/PRテンプレートにも紐付け、未完了項目がある場合は`status=blocked`として扱う。

### 13.1 事前準備フロー

1. **差分基準の明確化**
   - `git status --short`がクリーンであることを確認し、`docs/prompt_packages/<date>_<epic>.md`にベースラインコミットハッシュを記録する。
   - `make ci-lite`実行ログを`ci/baseline_<commit>.log`として保存。失敗時はCodexへ渡す前に原因を解決する。
2. **プロンプト資材の整備**
   - 必要ファイルの抜粋（最大200行）を`docs/snippets/<epic>/<module>.py`に更新。`# region`コメントで差分境界を明示する。
   - テレメトリやメトリクスの抜粋（§6.8）を`docs/prompt_packages/...`の`Context`節に添付。Acceptable Degradation関連タスクでは`metrics/cli_commands.jsonl`と`reports/validation_log/AC-45*`を必ず含める。
3. **Runbook・メトリクス整合**
   - 影響するRunbook節番号とチェックボックスをIssue本文に列挙し、運用担当と整合する。
   - `make sla-report`または該当スクリプトを実行し、最新メトリクスを`reports/validation_log/<date>_<topic>.md`へ貼り付ける。Codexはこれをベースラインとし、差分報告に活用する。
4. **テスト指示の具体化**
   - `pytest -k <keyword>`や`tradectl ... --dry-run`など、Codexが実行すべきコマンドをIssueに明示し、成功判定（閾値・期待出力）を表形式で記載。
   - 追加で必要なフィクスチャ・モックは`tests/fixtures/README.md`と`docs/prompt_packages/...`へ追記し、生成スクリプトを併記する。
5. **リスク通知**
   - 既知のリスク（§11）やAcceptable Degradation発生履歴を`feedback_loop.md`から抜粋し、Issueに`Known Risks`セクションとして貼り付ける。
   - 緊急度が高い場合は`AlertDispatcher`ログ（`logs/alerts/*.jsonl`）を添付し、Codexが原因トリアージを再現できるようにする。

### 13.2 チェックリスト（Issue/PR用）

| # | 項目 | 完了状態 | 証跡 |
| --- | --- | --- | --- |
| 1 | ベースラインCIログ（`make ci-lite`）を`ci/baseline_<commit>.log`へ保存した | ☐ | `ci/baseline_<commit>.log` |
| 2 | Prompt Bundleに対象セクション引用・I/O契約表・テレメトリ抜粋を追加した | ☐ | `docs/prompt_packages/<date>_<epic>.md` |
| 3 | 影響Runbook節とチェックボックスをIssue本文に列挙した | ☐ | Issue/PR本文 |
| 4 | テストコマンドと判定基準を表形式で記載した | ☐ | Issue/PR本文（`<Tests>`節） |
| 5 | 既知リスク/Acceptable Degradation履歴を添付した | ☐ | `feedback_loop.md`, `reports/validation_log/*` |
| 6 | 必要なフィクスチャ/データ抜粋を更新し、生成スクリプトを明記した | ☐ | `tests/fixtures/README.md`, `tools/*` |
| 7 | Feature Flag既定値と切替条件を明記した | ☐ | Issue/PR本文（`Feature Flags`節） |
| 8 | Codex成果物レビュー用の`make <target>`コマンド（例:`make sla-report`）を指定した | ☐ | Issue/PR本文 |
| 9 | 関連Runbook/Validationログの最新ハッシュを記録した | ☐ | `reports/validation_log/<date>_*.md` |
| 10 | Codex再依頼時のフィードバック（`feedback_loop.md`該当行）を引用した | ☐ | Issue/PR本文 |

### 13.3 Codex成果物受領後の確認

1. `git diff --stat`で設計指定外ファイルが含まれていないか確認。逸脱があれば即差戻し。
2. `make ci-lite`とIssueで指定したテストコマンドを再実行し、`ci/results/<date>_<epic>.log`へ保存。
3. Acceptable Degradationが絡む場合は`tradectl telemetry report --window 1d`（実装前は`make telemetry-report`）でコマンドログ差分を確認し、Runbookサインオフに添付。
4. `docs/prompt_packages/...`へレビューメモ（良かった点/改善点/想定外差分）を追記し、`feedback_loop.md`を更新。次回のPrompt改善に繋げる。
5. `docs/change_requests/`や`reports/validation_log/`の該当ファイルへサインオフ者と日時を追記し、監査ログと整合させる。

これらの手順を遵守することで、Codexとの反復速度を維持しつつ将来の仕様変更にも耐えられるドキュメント・証跡を確保する。

## 14. シナリオランナーとRunbook自動演習設計（v2.4追加）

### 14.1 目的と適用範囲

- Acceptable Degradation手順やKill Switch演習など、Runbookで定義されたシナリオを**半自動的に再現**し、Codex成果物の検証とトレーダー教育を効率化する。
- 対象モジュール: `src/scenario/runner.py`, `src/scenario/loader.py`, `src/scenario/models.py`, `src/scenario/validators.py`, `src/interfaces/cli/scenario.py`, `tests/unit/test_scenario_runner.py`, `tests/integration/test_scenario_cli.py`。
- 運用環境: macOSローカルでのPaper/Backtestモード（Liveでは`dry-run`のみ許可）。Runbook参照: `docs/runbooks/RUN-DATA-05`, `RUN-DATA-06`, `RUN-RISK-01`, `RUN-HITL-01`, `RUN-POST-03`。

### 14.2 ディレクトリ構成と成果物

| パス | 役割 | 備考 |
| --- | --- | --- |
| `src/scenario/__init__.py` | シナリオパッケージ初期化 | Feature Flag `scenario.runner_enabled`が`False`の場合は`noop`実装を返す |
| `src/scenario/models.py` | `ScenarioDefinition`, `ScenarioStep`, `ValidationRule`などの`pydantic`モデル | `__schema_version__ = 1`を定義し、`tests/contracts/test_scenario_schema.py`で互換性検証 |
| `src/scenario/loader.py` | YAML/Markdownシナリオの読み込みと検証 | `docs/scenarios/<id>.yaml`/`docs/scenarios/<id>.md`を対象 |
| `src/scenario/runner.py` | 実行エンジン（ステップ制御/リトライ/ドライラン） | `ScenarioRunner.run`がメインエントリ |
| `src/scenario/validators.py` | CLI出力/メトリクスの検証ユーティリティ | Acceptable Degradation判定の閾値ロジックを集約 |
| `src/interfaces/cli/scenario.py` | `tradectl scenario run/list/show`コマンド | `instrument_command`（§6.8）でテレメトリを記録 |
| `docs/scenarios/` | シナリオ定義YAML + 参考Markdown（Runbook差分） | `OPS-DEG-01.yaml`, `RISK-KS-05.yaml`など |
| `tests/fixtures/scenario/` | モックレスポンス（CLIログ/メトリクスJSON） | CLI整合性テストで使用 |

- Codexは上記各ファイルを最大200行単位の抜粋としてPrompt Bundleへ添付する。`docs/scenarios/README.md`にシナリオ命名規約とRunbook対応表を追加予定（別タスク）。

### 14.3 シナリオ定義モデル

| フィールド | 型 | 説明 |
| --- | --- | --- |
| `id` | `ScenarioId`（`Literal` + 正規表現`^[A-Z0-9\-]+$`） | `OPS-DEG-01`, `RISK-KS-05`など。Runbookセクションと整合 |
| `title` | `str` | Runbookでの見出しと一致させる |
| `tags` | `list[str]` | `['acceptable_degradation','guarded']`等。`qa_tags`（§6.8）と同期 |
| `mode` | `Literal['backtest','paper','live','dry-run']` | Liveでは`dry-run`のみ許可 |
| `preconditions` | `list[Precondition]` | `config`/`metrics`/`health`などの前提チェック |
| `steps` | `list[ScenarioStep]` | CLI実行/手動確認/メトリクス検証を順序付け |
| `success_criteria` | `list[ValidationRule]` | `metrics.data_ingestion_sla.p95 <= 18`等 |
| `rollback_plan` | `ScenarioRollback` | 失敗時の手動手順とRunbookリンク |
| `artifacts` | `list[ArtifactSpec]` | 収集すべきログ/レポート（`reports/validation_log/...`） |
| `prompt_notes` | `str | None` | Codexへ渡す際に注意する設計観点 |

- `ScenarioStep`は`CommandStep`/`ManualStep`/`ValidationStep`の3種を`discriminator='kind'`で表現。`CommandStep`には`cmd`, `args`, `timeout`, `expected_exit_code`を保持し、`dry_run`時は実行をスキップして`note`を出力する。
- `Precondition`は`type`に応じて`metrics`（JSONL照会）、`feature_flag`、`file_exists`等をサポート。未達成の場合は実行を停止し`ScenarioPreconditionError`を返す。

### 14.4 CLI仕様 (`tradectl scenario ...`)

| コマンド | 用途 | 主な引数/フラグ | 成功時挙動 | 代表エラー |
| --- | --- | --- | --- | --- |
| `tradectl scenario list` | 登録シナリオの列挙 | `--tag acceptable_degradation`, `--mode paper` | `ScenarioSummary`テーブルを表示。`--json`でJSON出力 | シナリオファイル不備→`ScenarioRegistryError` |
| `tradectl scenario show <id>` | 詳細表示 | `--format yaml|table`, `--include-steps` | YAML整形出力＋Runbookリンク一覧 | `ScenarioNotFound` |
| `tradectl scenario run <id>` | シナリオ実行 | `--profile`, `--dry-run`, `--step-from`, `--step-to`, `--auto-ack`, `--collect-artifacts` | ステップ毎にRichログ。成功で`ScenarioRunResult`サマリと収集アーティファクトパスを表示 | `ScenarioExecutionError`, `ValidationFailed`, `PreconditionFailed` |
| `tradectl scenario run --plan <id>` | 実行プラン確認 | `--format table|json` | 実行コマンド/想定所要時間を表示 | 同上 |

- CLIは`ScenarioRunner`をDIし、`instrument_command`デコレータで`metrics/cli_commands.jsonl`へ記録。Acceptable Degradation中の実行では`qa_tags`へシナリオIDを付与する。

### 14.5 実行フロー

1. CLIから`ScenarioRunner.run`呼び出し。
2. `ScenarioLoader.load(id)`がYAMLを読み込み、`ScenarioDefinition`へパース。`docs/scenarios/<id>.md`（任意）を添付し、`prompt_notes`があればログに表示。
3. `PreconditionEvaluator.evaluate(definition.preconditions, context)`で前提チェック。失敗時は例外を投げ、`--dry-run`でも実行しない。
4. ステップごとに`StepExecutor`が種類に応じて処理。
   - `CommandStep`: `subprocess`（同期）または`asyncio.create_subprocess_exec`（非同期）でコマンドを実行し、標準出力を`logs/scenario/<id>/step_<n>.log`に保存。
   - `ManualStep`: 実行者へプロンプト表示。`--auto-ack`指定時は`note`をログ化のみ。
   - `ValidationStep`: `validators.evaluate(metric_spec, tolerance)`で閾値判定し、失敗時に`ValidationFailed`を投げる。
5. 全ステップ成功後、`SuccessCriteriaEvaluator`が`success_criteria`を検証。Passなら`ScenarioRunResult(status='success')`を返却し、`reports/validation_log/scenario/<id>_<timestamp>.md`を生成。
6. 途中失敗した場合は`rollback_plan`を表示し、`--auto-rollback`（将来フラグ）未設定なら手動対応を要求。失敗時の状態は`ScenarioRunResult(status='failed', failed_step=<n>, reason=<error>)`として返す。

### 14.6 Codex実装契約

| 関数/クラス | シグネチャ | 主な例外/戻り値 | テスト観点 | 備考 |
| --- | --- | --- | --- | --- |
| `ScenarioLoader.load` | `def load(self, scenario_id: str) -> ScenarioDefinition` | `ScenarioNotFound`, `ScenarioSchemaError` | `pytest -k scenario_loader` | YAMLとMarkdown（任意）の整合を検証。`schema_version`不一致時は警告 |
| `ScenarioRunner.run` | `async def run(self, definition: ScenarioDefinition, context: ScenarioContext) -> ScenarioRunResult` | `ScenarioExecutionError`, `ValidationFailed`, `ScenarioPreconditionError` | `pytest -k scenario_runner::test_run_success`, `test_run_validation_failure` | `context`には`mode`, `profile`, `dry_run`, `collect_artifacts`を含む |
| `PreconditionEvaluator.evaluate` | `def evaluate(preconditions: Sequence[Precondition], context: ScenarioContext) -> None` | `ScenarioPreconditionError` | `pytest -k scenario_precondition` | メトリクス照会は`metrics.loaders.jsonl_reader`ユーティリティを利用 |
| `StepExecutor.execute` | `async def execute(self, step: ScenarioStep, context: ScenarioContext) -> StepResult` | `StepExecutionError` | `pytest -k scenario_steps` | `CommandStep`は`timeout`/`expected_exit_code`を必須検証 |
| `validators.evaluate` | `def evaluate(rule: ValidationRule, context: ScenarioContext) -> ValidationOutcome` | `ValidationFailed` | `pytest -k scenario_validators` | `ValidationRule`は`metric_path`, `comparator`, `threshold`, `window`などを保持 |

- Codexは各実装で`pydantic` v2を使用し、`model_config = {'extra': 'forbid'}`を設定する。例外メッセージにはRunbook参照（例:`runbook:RUN-DATA-05#guarded_checklist`）を含め、運用者が即座に対処できるようにする。

### 14.7 ロギングとテレメトリ

- `ScenarioRunner`は`logs/scenario/<id>/<timestamp>/`配下に以下を保存する。
  - `scenario_summary.json`: `ScenarioRunResult`のJSONシリアライズ。
  - `step_<n>_stdout.log`/`step_<n>_stderr.log`: コマンド実行ログ。
  - `artifacts.json`: 収集対象ファイルと保存先のリスト。
- `metrics/scenario_runs.jsonl`に`{ts, id, status, duration_sec, failed_step, qa_tags}`を追記。`TelemetryAggregatorJob`が週次でCLI実行回数と結果を集計し、`reports/telemetry/cli/<YYYYWW>.md`へ転載。
- Acceptable Degradation演習時は`qa_tags`へ`['scenario', <ScenarioId>, 'degraded']`を付与し、`CommandTelemetryRecord`と相互参照できるようにする。

### 14.8 テスト・検証方針

| テストID | 目的 | 内容 |
| --- | --- | --- |
| UT-SCN-01 | YAMLスキーマ検証 | `ScenarioLoader`が必須フィールド欠落を検出し`ScenarioSchemaError`を投げる |
| UT-SCN-02 | ステップ実行成功 | `ScenarioRunner`で`CommandStep`/`ManualStep`/`ValidationStep`が順に成功するケース |
| UT-SCN-03 | バリデーション失敗時のロールバック案内 | `ValidationFailed`で`rollback_plan`がログ出力される |
| IT-SCN-01 | Acceptable Degradation演習 | `tradectl scenario run OPS-DEG-01 --dry-run`でCLI出力が期待と一致、`metrics/scenario_runs.jsonl`に記録 |
| IT-SCN-02 | Kill Switch演習 | `tradectl scenario run RISK-KS-05 --profile paper-m1-core`実行後に`logs/scenario/...`へ証跡が作成される |

- `pytest`マーカー: `@pytest.mark.scenario`を導入し、`pytest -m scenario`で集中実行可能とする。CIでは週次で`pytest -m "scenario and not slow"`を実施。
- CLIスナップショットは`pytest-approvaltests`を用い、`tests/snapshots/scenario/`へ保存。更新時は`--approve`で承認し、`docs/prompt_packages/<date>_scenario_runner.md`へスクリーンショット差分を添付する。

### 14.9 Runbook・メトリクス連携

- 各シナリオYAMLは`runbook_refs`に`['RUN-DATA-05#guarded', 'RUN-POST-03#review']`のような節IDを列挙し、成功時に自動で`reports/validation_log/scenario/<id>_<timestamp>.md`へ引用を貼り付ける。
- `ScenarioRunner`は成功時に`EventBus.publish('scenario.completed', payload)`を発火し、`payload`に`runbook_refs`, `artifacts`, `metrics_snapshot`を含める。Opsはこのイベントを監視し、Runbook更新漏れを検知できる。
- メトリクス照会は`metrics`ディレクトリのJSONLを直接読むのではなく、`infra.metrics`モジュールの`load_window(metric_path, window)`ユーティリティを経由して取得し、将来Prometheus化してもAPI互換を維持する。

### 14.10 将来拡張フック

- `scenario.runner_enabled` Feature FlagでON/OFF制御。M1 Coreは`True`で提供するが、`dry-run`モードを既定とする。Liveモードでの実行は`config.scenario.allow_live=false`が既定で、M1.1で手動承認ステップを追加予定。
- `ScenarioStep`に`WaitForEventStep`（EventBus待機）、`WebhookStep`（Slack通知検証）を追加できる余地を残し、`StepExecutor`は`match step.kind`構造で拡張しやすくする。
- GUI/Tauri移行時には`scenario` APIをHTTP/IPC越しに再利用できるよう、`ScenarioRunner`のI/Oを`dataclass`ベースで整理し、シリアライズ可能に保つ。Codexは例外に`error_code`を付与し、将来GUIでハンドリングしやすいようにする。

- 追加シナリオのレビュー手順として、`docs/scenarios/CHANGELOG.md`にID/目的/Runbookリンク/テスト結果を追記し、`docs/prompt_packages/<date>_scenario_runner.md`へ差分を保存する。これによりCodexが次回シナリオ改修を行う際に参照可能な履歴が整備される。

## 15. CLIテレメトリアグリゲータとQAダッシュボード統合（v2.4追加）

### 15.1 目的と適用範囲
- CLIテレメトリ（§6.8）とシナリオランナー（§14）の計測データを**定期バッチで集約し、QA/運用レビューに直結するダッシュボード**を生成する。
- Codexが実装する主モジュール: `src/telemetry/aggregator.py`, `src/telemetry/models.py`, `src/telemetry/repository.py`, `src/interfaces/cli/telemetry.py`, `src/reports/telemetry_renderer.py`, `tests/unit/test_telemetry_aggregator.py`, `tests/integration/test_cli_telemetry_report.py`。
- 対象データソース: `metrics/cli_commands.jsonl`, `metrics/scenario_runs.jsonl`, `health_state_transitions.jsonl`, `logs/ops/command.log`, `reports/telemetry/cli/<YYYYWW>.md`（既存ファイルへの追記）。
- 運用頻度: `TelemetryAggregatorJob`を**日次**で自動実行し、週次レビュー前に`tradectl telemetry report --window 7d`を人手で確認する。

### 15.2 モジュール構成と責務
| モジュール | 主責務 | Codex実装ガイド |
| --- | --- | --- |
| `src/telemetry/models.py` | `CliCommandSample`, `ScenarioRunSample`, `AggregationWindow`, `TelemetryDigest`等の`pydantic`モデル定義。 | `__schema_version__ = 1`を設定し、`tests/contracts/test_telemetry_schema.py`で互換性検証。浮動小数は`Decimal`で保持し丸めは表示段階に限定。 |
| `src/telemetry/repository.py` | JSONL読み込み/ウィンドウ抽出/ローテーション確認。 | `load_cli_samples(window: AggregationWindow) -> Iterable[CliCommandSample]`などのAPIを提供し、ファイル欠損時は空イテレータを返す。将来S3移行時に差し替え可能な設計とする。 |
| `src/telemetry/aggregator.py` | 集計ロジック。p95/p99計算、エラーレート算出、`qa_tags`別ブレークダウンを実装。 | `TelemetryAggregator.aggregate(window, *, include_scenarios: bool = True) -> TelemetryDigest`。p95/p99は最近傍補間で計算し、サンプル数<20件の場合は`insufficient_sample=True`を立てる。Acceptable Degradation時の実行(`qa_tags`に`degraded`)を別集計する。 |
| `src/interfaces/cli/telemetry.py` | `tradectl telemetry report`コマンド。`--window`, `--command`, `--format`, `--qa-tag`等を受け取り、Richテーブル/Markdown/JSONで出力。 | `instrument_command`デコレータ適用。Markdown出力時は`reports/telemetry/cli/<YYYYMMDD>.md`へ保存し、週次モードでは`reports/telemetry/cli/<YYYYWW>.md`に追記。 |
| `src/reports/telemetry_renderer.py` | Markdownテンプレ生成、スパークライン描画、QAサマリ挿入。 | `render_digest(digest: TelemetryDigest, *, profile: str, window: AggregationWindow) -> str`。`jinja2`テンプレート利用可。 |
| `src/app/jobs/telemetry.py` | Scheduler登録。日次`02:15 JST`実行、失敗時は3回再試行。 | `TelemetryAggregatorJob`がDigest生成→Markdown/JSON書込→`EventBus.publish('telemetry.digest_generated', payload)`。 |

### 15.3 データパイプライン
1. `instrument_command`が`metrics/cli_commands.jsonl`へ逐次追記。シナリオランナーは`metrics/scenario_runs.jsonl`へ書込。
2. `TelemetryAggregatorJob`が`AggregationWindow(start, end)`を決定（既定: 前日00:00〜23:59, `tz=UTC`）。
3. `TelemetryRepository`がウィンドウ内サンプルを読み込み、`CliCommandSample`/`ScenarioRunSample`へ変換。欠損/破損行は`invalid_records.jsonl`へ退避し、`EventBus.publish('telemetry.invalid_record')`。
4. `TelemetryAggregator.aggregate`が以下を計算:
   - `command_stats[command] = {count_success, count_error, median_ms, p95_ms, p99_ms, error_codes}`。
   - `qa_tag_stats[tag] = {count, success_rate, median_ms}`。
   - `scenario_stats`（`scenario_id`, `status`, `duration_p95`, `artifact_count`）。
   - `health_state_correlation`: コマンド実行時の`HealthStateSummary.status`分布。
5. `TelemetryDigest`へまとめ、`TelemetryRenderer`がMarkdown/JSON/CSVを生成。
6. CLI `tradectl telemetry report`はDigestを読み込み、必要に応じて`--persist`でファイル出力。

### 15.4 CLI仕様 (`tradectl telemetry report`)
| オプション | 説明 | 既定値 | 備考 |
| --- | --- | --- | --- |
| `--window <int>` | 過去n日（最大90日） | 7 | `AggregationWindow`に変換。`--since/--until`で明示指定も可能。 |
| `--command board,status,...` | 対象コマンドをカンマ区切りで絞り込み | 全コマンド | `command_stats`からフィルタ。 |
| `--qa-tag degraded,scenario` | `qa_tags`ベースで集計 | 全タグ | Acceptable Degradation影響を確認する際に使用。 |
| `--format table|markdown|json` | 出力形式 | table | `markdown`で`reports/telemetry/cli/<window>.md`へ保存。 |
| `--persist` | 出力ファイルを保存 | False | Markdown/JSONを所定パスに保存。 |
| `--include-scenarios/--no-include-scenarios` | シナリオ集計の有無 | include | シナリオが多い週は集計除外可能。 |
| `--threshold-profile <path>` | SLA閾値と比較 | `config/sla_thresholds/active.yaml` | `TelemetryAggregator`が閾値差分を計算し、逸脱をハイライト。 |

- エラーコード: `TelemetryReportGenerationError`, `TelemetryDataMissing`。処理失敗時はExit code 121。
- `--format markdown --persist`使用時は`reports/telemetry/cli/<YYYYWW>.md`をテンプレ更新し、週次レビューに添付する。

### 15.5 TelemetryDigest スキーマ
```python
class TelemetryDigest(BaseModel):
    schema_version: Literal[1]
    window: AggregationWindow
    generated_at: datetime
    command_stats: dict[str, CommandStats]
    qa_tag_stats: dict[str, QaTagStats]
    scenario_stats: dict[str, ScenarioStats]
    health_state_correlation: dict[str, HealthDistribution]
    insufficient_sample_commands: list[str]
    notes: list[str]
```
- `CommandStats`は`count_success`, `count_error`, `median_ms`, `p95_ms`, `p99_ms`, `error_codes: dict[str, int]`, `board_mode_distribution: dict[str, int]`。
- `QaTagStats`は`count`, `success_rate`, `median_ms`, `p95_ms`, `health_state_distribution`。
- `ScenarioStats`は`status_counts`, `duration_median_ms`, `duration_p95_ms`, `artifact_count_avg`, `last_run_at`。
- `notes`にはサンプル不足や閾値逸脱を列挙し、Markdown出力時に`⚠️`バッジで強調。

### 15.6 テスト計画
| テストID | 目的 | 内容 |
| --- | --- | --- |
| UT-TEL-01 | コマンド集計の正確性 | `tests/unit/test_telemetry_aggregator.py::test_basic_stats`でサンプルを与え、p95/p99/エラーレートが期待値通りか検証。 |
| UT-TEL-02 | `qa_tags`フィルタ | `test_qa_tag_breakdown`で`degraded`タグを分離集計できることを確認。 |
| UT-TEL-03 | サンプル不足フラグ | サンプル<20件の場合に`insufficient_sample_commands`へ登録されるか検証。 |
| UT-TEL-04 | スキーマ互換性 | `tests/contracts/test_telemetry_schema.py`で`TelemetryDigest`がバージョン1を維持するか確認。 |
| IT-TEL-01 | CLI出力整合 | `tests/integration/test_cli_telemetry_report.py::test_table_output`でCLI出力がRichテーブル形式/ヘッダ一致を確認。 |
| IT-TEL-02 | Markdown永続化 | `test_markdown_persist`で`--persist`指定時にファイルが生成され、テンプレヘッダ（週次サマリ/Acceptable Degradationログ）が埋まるか検証。 |
| IT-TEL-03 | SLA閾値比較 | `test_threshold_profile_diff`で`config/sla_thresholds/sample.yaml`を読み込み、逸脱箇所に`⚠️`注記が表示されるか確認。 |

### 15.7 Codex実装ハンドオフ要件
1. Prompt Bundleに`metrics/cli_commands.jsonl`と`metrics/scenario_runs.jsonl`の最新10行を添付し、`CLI_ACTOR`や`qa_tags`の意味を注記する。
2. `TelemetryAggregator.aggregate`の数式（p95/p99計算、エラーレート = `count_error / max(1, count_total)`）を明示し、浮動小数→`Decimal`変換の方針を記載。
3. CLIテストでは`pytest-approvaltests`によるスナップショット更新手順を指定し、差分が発生した際の承認フローをIssueに追記。
4. `reports/telemetry/cli/<YYYYWW>.md`のテンプレート断片（ヘッダ/サマリ/アクションアイテム）をPrompt Bundleへ添付し、Codexに整形ルールを明示。
5. Runbook整合: `RUN-OPS-02`のレビュー手順に新しいレポートセクションを追記するタスクを併記し、Codex成果物レビュー時にRunbook更新漏れがないか確認する。

### 15.8 運用/QAとの接続
- `TelemetryDigest`生成後に`EventBus.publish('telemetry.digest_generated')`を発火し、`payload`へ`insufficient_sample_commands`や`notes`を含める。`HealthMonitor`は`p95_ms`が`config.telemetry.board.p95_warn_ms`を超えた場合に`health.changed(reason='cli_latency')`を発火する。
- 週次レビューでは以下を行う:
  1. `reports/telemetry/cli/<YYYYWW>.md`を開き、`Acceptable Degradation`タグ付きコマンドのp95/p99がRunbook許容内か確認。
  2. `scenario_stats`で`OPS-DEG-01`など主要シナリオの成功率が100%か確認。未達の場合は`docs/prompt_packages/<date>_scenario_runner.md`へ追記し、次スプリントでハードニング。
  3. `health_state_correlation`で`soft_stop/hard_stop`状態中に実行されたCLIが適切にRunbookサイン済みか、`logs/ops/command.log`と突合。
- Acceptable Degradation解除時は`tradectl telemetry report --qa-tag degraded --window 3`の出力を`reports/validation_log/AC-45_sla_<date>.md`に添付し、オペレーション時間短縮効果を定量化する。

### 15.9 将来拡張フック
- `TelemetryDigest.schema_version`は`Feature Flag telemetry.digest_v2`で新フィールド追加に備える。Codex実装時はバージョンアップ手順（スキーマテスト更新、`reports`テンプレ更新、Runbook修正）をIssueへ記載する。
- GUI/Tauri移行時にWebSocket操作を集計するため、`CliCommandSample`に`origin: Literal['cli','gui','api']`フィールドを追加する余地を残す。M1では`'cli'`固定。
- `TelemetryAggregatorJob`は将来Prometheusプッシュゲートウェイをサポートするため、`ExporterAdapter`インターフェースを用意しておく（M2+）。

---

## 16. Acceptable Degradation ナレッジパックとCodex活用指針（v2.4追加）

### 16.1 目的
- Acceptable Degradation発生時の対応品質を高めるため、**運用証跡・シナリオ・計測値をCodex向けに体系化**し、再発時に即座に改善タスクへ落とし込めるようにする。
- 成果物: `docs/knowledge_packs/acceptable_degradation/`配下のテンプレート、`metrics`タグリングルール、`tradectl`コマンド出力例、Codexプロンプト雛形。

### 16.2 ディレクトリ/成果物構成
| パス | 役割 | 形式 |
| --- | --- | --- |
| `docs/knowledge_packs/acceptable_degradation/README.md` | 運用ガイド、タグ定義、更新手順 | Markdown |
| `docs/knowledge_packs/acceptable_degradation/case_<YYYYMMDD>.md` | 事例テンプレ（発生日・原因・対応・改善タスク） | Markdown |
| `docs/knowledge_packs/acceptable_degradation/metrics_snapshot_<id>.json` | `metrics/data_ingestion_sla.jsonl`等から抽出した定量データ | JSON |
| `docs/knowledge_packs/acceptable_degradation/prompt_context_<scenario>.md` | Codexへ渡す際の情報まとめ | Markdown |
| `docs/knowledge_packs/acceptable_degradation/checklist.yaml` | 更新チェックリスト（Runbook整合、メトリクス抽出、教訓） | YAML |
| `docs/knowledge_packs/acceptable_degradation/index.json` | 事例メタデータ（シナリオID、影響度、再発率） | JSON |

### 16.3 ナレッジ更新フロー
1. Acceptable Degradation発生時に`reports/validation_log/AC-45_sla_<date>.md`へ一次記録。
2. 対応完了後24h以内に`docs/knowledge_packs/.../case_<date>.md`を作成し、以下を記載。
   - `Scenario ID`（§14参照）、`board_mode`推移、`metrics`抜粋。
   - 実行したCLI/Runbook手順、所要時間（分単位）。
   - 恒久対策タスク（Issueリンク）と担当。
3. `metrics_snapshot_<id>.json`を生成するスクリプト`tools/acceptable_deg/export_snapshot.py`を実行し、再現に必要なメトリクスを抽出。
4. `prompt_context_<scenario>.md`にCodexへ渡すべきポイント（背景/現象/課題/期待する改善）を200〜300字でまとめ、対応する詳細設計セクション番号を列挙。
5. `index.json`を更新し、`impact_score`（1〜5）、`recurrence`（例: `rare`, `occasional`）を記載。`impact_score≥4`は次スプリントのレビュー議題とする。

### 16.4 Codex向けプロンプトテンプレ
```
<Scenario ID>: Acceptable Degradation Knowledge Pack
背景:
  - 発生日/状況/board_mode推移
  - 既存実装の課題（セクション番号、例: §3.1.1 RateLimitGuard）
  - メトリクス抜粋（p95遅延、429率など）
要求:
  - 修正対象モジュール（ファイルパス + 関数名）
  - 期待する改善（例: 手動CSV投入ステップの自動化、TelemetryDigestへのタグ追加）
  - Feature Flag有無・切替条件
テスト:
  - `pytest -k <case>`、`tradectl scenario run <ID>`、`tradectl telemetry report --qa-tag degraded`
証跡:
  - `reports/validation_log/AC-45_sla_<date>.md`
  - `docs/knowledge_packs/.../metrics_snapshot_<id>.json`
レビューポイント:
  - トレーダーUX/Runbook整合/リスク影響/メトリクス差分
```
- テンプレは`docs/knowledge_packs/acceptable_degradation/prompt_template.md`として管理し、更新時は`CHANGELOG`を付与する。

### 16.5 メトリクスとタグ規約
| タグ | 対応メトリクス | 付与条件 | 参照Runbook |
| --- | --- | --- | --- |
| `degraded` | `HealthState.status` | `status in {'degraded','soft_stop','hard_stop'}`で自動付与 | `RUN-DATA-05`, `RUN-RISK-01` |
| `manual_csv` | `metrics/data_ingestion_sla.jsonl`, `logs/ops/manual_csv.log` | 手動CSV投入ステップ実行時 | `RUN-DATA-06` |
| `rate_limit_stage` | `metrics/rate_limit_window.jsonl` | Stage変更イベント時 | `RUN-DATA-05` |
| `guarded_board` | `metrics/cli_commands.jsonl` | `tradectl board --guarded`実行時 | `RUN-HITL-01` |
| `kill_switch` | `kill_switch_events.jsonl` | Kill Switch遷移 | `RUN-RISK-01` |

- `TelemetryDigest`と`ScenarioRunner`は上記タグを共有し、Acceptable Degradationの頻度と復旧時間をクロス分析できるようにする。
- `tools/acceptable_deg/tag_sync.py`が`metrics`/`logs`/`reports`からタグの整合性をチェックし、欠損があれば`health.changed(reason='knowledge_pack_desync')`で通知。

### 16.6 QA/レビュー連携
- 週次レビューでは`docs/knowledge_packs/.../index.json`を参照し、`impact_score≥3`のケースを優先的にハードニング対象へ割り当てる。
- `tradectl scenario run <ID>`実行後に`--collect-artifacts`で得たログを`case_<date>.md`へ添付し、再現性を保証する。
- `make qa-report`は`knowledge_packs`の更新有無をチェックし、未更新の場合は`WARN knowledge_pack.stale`を出力。CIで検知した場合はPRを`needs-knowledge-pack`ラベルでブロックする。

### 16.7 将来拡張
- M1.1でGUI通知を追加する際に、Knowledge PackからSlack用の要約を自動生成する`tools/acceptable_deg/render_slack_summary.py`を導入予定。
- M2ではAcceptable Degradationからの復旧時間を自動計測し、`TelemetryDigest`に`recovery_time_minutes`を追加。`index.json`の`recovery_time_median`をダッシュボードへ出力する。
- データストアは当面ローカルJSON/Markdownだが、将来は`docs/knowledge_packs`をGitサブモジュール化し、組織共有リポジトリでバージョン管理することを想定。

---

## 17. 変更管理と監査証跡の高度化（v2.4追加）

Acceptable DegradationやTelemetry改善に伴い、変更管理の透明性をさらに高めるための仕組みを追補する。

### 17.1 Change Ledger サービス
- モジュール: `src/governance/change_ledger.py`（M1 Core: append-onlyロガー）。
- API: `record_change(ChangeRecord)`, `list_changes(filter)`, `export_digest(window)`。
- `ChangeRecord`フィールド: `change_id`, `timestamp`, `actor`, `category`（`code`, `config`, `runbook`, `knowledge_pack`）, `summary`, `related_artifacts`, `runbook_refs`, `accept_degradation_case`。
- 実装方針: M1ではJSONL（`logs/governance/change_ledger.jsonl`）へ追記。M2で外部システム連携予定。Codex実装時は`pydantic`モデルで入力検証し、Runbook整合性を保つ。
- CLI: `tradectl governance change log --window 30`で最近の変更を表示。`instrument_command`でテレメトリ記録。

### 17.2 監査ログ相互参照
- `ChangeLedger`は記録時に`AuditService.append`を呼び、`audit_ref`を返却。Ticket/Auditログ/Knowledge Packで相互リンクを作成する。
- `TelemetryDigest`出力に直近`change_ledger`エントリ5件を添付し、CLI改善と運用変更の因果を把握できるようにする。
- `ScenarioRunner`成功時は関連する`ChangeRecord` IDを付与し、再演習時の根拠を可視化。

### 17.3 Codex実装チェックポイント
- Prompt Bundleに`change_ledger`の最新10行と`ChangeRecord`スキーマを含める。
- `tests/unit/test_change_ledger.py`を追加し、`record_change`が重複`change_id`を拒否すること、`export_digest`がウィンドウ境界を尊重することを確認。
- `tests/integration/test_change_ledger_cli.py`でCLI出力のスナップショットを維持。
- Runbook `RUN-GOV-01`に`change_ledger`追記手順を追加し、Acceptable Degradation後24h以内に記録するルールを明文化。

### 17.4 将来拡張
- M1.1: `change_ledger`を`docs/knowledge_packs`と同期し、ケースファイルに自動でリンクを挿入。
- M2: ガバナンスサービス本実装と連携し、承認ワークフロー（承認者、署名ハッシュ）を追加。

---

これらの追補により、Codex実装チームはAcceptable Degradation対応とCLIテレメトリ改善を高速に反復でき、トレーダー/運用チームは一貫した証跡とレビュー材料を確保できる。今後の設計更新では、上記セクションを基準にPrompt Bundleとテスト計画を組み立て、将来の仕様変更にも耐えうる抽象化境界を維持する。
