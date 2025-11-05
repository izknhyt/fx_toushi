<!-- オフラインバンドル受領者へ配布する標準インストール手順テンプレート。 -->
# Offline Bundle Install & Verification Guide

- **Bundle Version**: {{bundle.version}}
- **Release Window**: {{bundle.release_window}}
- **Generated At (UTC)**: {{generated_at}}
- **Prepared By**: {{prepared_by}}
- **Verification Status**: {{verification.status}}
- **Verification Report**: {{verification.report_path}}
- **Attachments**: {{#attachments.summary}}{{.}}{{/attachments.summary}}

## 1. Overview
- 配布対象: {{bundle.target_environment}}
- オフラインバンドル構成: {{bundle.contents_summary}}
- 依存整合性: manifest `{{bundle.manifest_path}}`, SBOM `{{bundle.sbom_path}}`
- 関連Runbook: {{bundle.runbook_refs}}

> `render_install_doc()`が上記メタデータを埋め込み、DR演習およびOpsレビューへ提出する想定。

## 2. Prerequisites
| Item | Requirement | Notes |
| --- | --- | --- |
| 対象ホスト | {{prerequisites.host_spec}} | CPUコア、メモリ、ディスク要件を含む |
| OS / Shell | {{prerequisites.os_shell}} | `zsh`推奨、`/usr/local/bin`に書込権限が必要 |
| Python / Poetry | {{prerequisites.python_poetry}} | `python --version`, `poetry --version`で事前確認 |
| 検証用ディレクトリ | {{prerequisites.workspace}} | 例: `/opt/fx-signal/{{bundle.version}}` |
| 検証担当者 | {{prerequisites.owners}} | Ops/QA/Traderの3者確認 |

## 3. Artifact Inventory
| Artifact | Path | Hash (SHA-256) | Notes |
| --- | --- | --- | --- |
{{#bundle.artifacts}}
| {{name}} | `{{path}}` | `{{sha256}}` | {{notes}} |
{{/bundle.artifacts}}

- 署名ファイル: {{bundle.signature_path}}
- 添付物 (ログ・スクリーンショット等): {{#attachments.detail}}{{.}}{{/attachments.detail}}

## 4. Acquisition Steps
1. 受信チャネル確認 (`tradectl audit inbox` または社内SFTP): {{acquisition.channel}}
2. バンドル取得 (`curl/scp` 等): `{{acquisition.fetch_command}}`
3. 転送後のハッシュ確認: `shasum -a 256 {{bundle.filename}}`
4. 配布メディアへのコピー: {{acquisition.media}}
5. WORM保管更新ログ: {{acquisition.audit_log}}

## 5. Installation Steps
1. 展開: `tar -xzf {{bundle.filename}} -C {{install.workdir}}`
2. 仮想環境作成: `python -m venv {{install.venv_path}} && source {{install.venv_path}}/bin/activate`
3. Wheelインストール: `pip install wheels/*.whl --no-index --find-links wheels`
4. Poetryロック同期: `poetry install --sync --no-root`
5. 追加スクリプト: `./scripts/post_install.sh` (必要時)
6. Makeターゲット (オフライン再現性テスト):
   - `make bundle-offline VERSION={{bundle.version}}`
   - `make bundle-verify BUNDLE={{bundle.filename}}`

## 6. Verification Steps
| Check | Command | Expected Outcome |
| --- | --- | --- |
| Manifest整合性 | `tradectl release bundle-verify --bundle {{bundle.filename}} --check-poetry --check-wheel-integrity` | Exit code 0, `verification_report.json`生成 |
| ハッシュ照合 | `shasum -c hashes.txt` | All OK |
| SBOM差分 | `syft packages --file sbom.spdx.json --scope all --fail-on-diff` | No diff |
| 動作確認 | {{verification.functional_test}} | 主要シグナル生成が成功 |
| ログ確認 | `grep -i "ERROR" logs/bundle_verify.log` | No matches |

> `make bundle-verify` 完了後、`verification_result={{verification.result}}`, `completed_at={{verification.completed_at}}` を記録。

## 7. Hash & Signature Verification
1. ハッシュファイル読み込み: `cat hashes.txt`
2. 署名検証: `gpg --verify {{bundle.signature_path}} {{bundle.filename}}`
3. 署名者Fingerprint: {{verification.signer_fingerprint}}
4. チェーン検証: {{verification.trust_chain}}
5. 監査記録追記: `logs/audit/release/offline_bundle_{{bundle.version}}.jsonl` へ結果追記

## 8. Troubleshooting
| Symptom | Diagnostic | Resolution |
| --- | --- | --- |
| `pip`が外部へアクセスしようとする | `pip install`ログに`files.pythonhosted.org`が出力 | `--no-index --find-links wheels` が指定されているか確認 |
| `make bundle-verify`失敗 (exit=120) | `verification_report.json`の`failures`参照 | `poetry lock --no-update`再実行 → Wheel再生成 |
| `gpg --verify`で署名不正 | キーリングに署名者キーがない | `gpg --recv-keys {{verification.signer_key_id}}` (オフライン環境では事前輸入) |
| ハッシュ不一致 | `shasum`結果が`FAILED` | バンドル再配布を要求し、監査ログに記録 |
| Venvが壊れている | `source venv/bin/activate`で`No such file` | 仮想環境ディレクトリを削除し再作成 |

## 9. Sign-off
| Role | Name / Initials | Timestamp (JST) | Notes |
| --- | --- | --- | --- |
| Ops Engineer | {{signoff.ops.name}} | {{signoff.ops.timestamp}} | {{signoff.ops.note}} |
| QA Lead | {{signoff.qa.name}} | {{signoff.qa.timestamp}} | {{signoff.qa.note}} |
| Trader / Desk Lead | {{signoff.trader.name}} | {{signoff.trader.timestamp}} | {{signoff.trader.note}} |
| Risk / Compliance | {{signoff.risk.name}} | {{signoff.risk.timestamp}} | {{signoff.risk.note}} |

## 10. Maintenance & Contacts
- **Template Owner**: {{contacts.template_owner}}
- **Maintenance Group**: {{contacts.maintenance_group}}
- **Fallback Contact**: {{contacts.fallback_contact}}
- **Escalation Runbook**: {{contacts.escalation_runbook}}
- **Last Review Date**: {{contacts.last_reviewed_at}}

> Opsレビュー時にテンプレート更新要否を確認し、`render_install_doc()`の生成ログ (`{{attachments.render_log}}`) を添付すること。
