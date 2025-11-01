# Templates

運用・リスク・コミュニケーション向けに用意したテンプレート群です。各テンプレートはGit管理下にあるため、利用時にはコピーし適宜編集してください。

## テンプレート一覧
| テンプレート | 用途 | 主な参照Runbook / 手順 |
| --- | --- | --- |
| [Drill Report](drill_report.md) | 運用ドリル完了後のレポート作成 | `RUN-OPS-AGENDA-01`, `RUN-DATA-05`, 設計書§53.4 |
| [Daily Agenda](daily_agenda.md) | 日次オペレーションの進行管理 | `RUN-OPS-AGENDA-01` |
| [Incident Report](incident_report.md) | 障害対応後のポストモーテム | `RUN-INCIDENT-01`, 詳細設計§7.5 |
| [Config Change](config_change.md) | 設定変更の事前レビューと記録 | `RUN-CHANGE-02` |
| [Ops Workload Report](ops_workload_report.md) | Ops負荷の定期報告 | `RUN-OPS-LOAD-03` |
| [Release Announcement](release_announcement.md) | リリース計画・告知 | `RUN-RELEASE-01` |

## 利用手順
1. `docs/templates/<template>.md` をコピーし、対象日のレポートディレクトリ（例: `reports/ops/`）に配置します。
2. コメントやMustacheプレースホルダー（`{{...}}`）を参照し、Runbookに沿って各セクションを埋めます。
3. 関連Runbook（例: ドリルレポートは `RUN-OPS-AGENDA-01` およびデータ復旧検証手順 `RUN-DATA-05`）を確認し、証跡・メトリクスリンクを添付します。
4. 完成したレポートは所定の承認フロー（Ops Lead → Risk Lead → Product Owner など）に従い、必要な署名欄を更新してください。

> Runbook IDは `docs/runbooks/` 配下に格納されているドキュメントと対応しています。不明な場合は運用チームに確認してください。
