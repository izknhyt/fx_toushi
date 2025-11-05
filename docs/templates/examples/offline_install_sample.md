# Offline Install Template Sample

このドキュメントは`render_install_doc()`により`docs/templates/offline_install.md`から生成される想定出力の例です。DR演習および月次Opsレビューでの証跡イメージを示します。

## Rendered Output Snapshot
```markdown
# Offline Bundle Install & Verification Guide

- **Bundle Version**: 2.3.7
- **Release Window**: 2024-Q2
- **Generated At (UTC)**: 2024-06-14T01:25:33Z
- **Prepared By**: ops-bot@example.com
- **Verification Status**: PASSED
- **Verification Report**: reports/offline_bundle/20240614/verification_report.json
- **Attachments**: INSTALL_LOG.md, WORM_receipt.pdf

## 1. Overview
- 配布対象: macOS Ventura 13.6 / Trader DR Workstation
- オフラインバンドル構成: Wheels(18), SBOM(spdx), hashes, INSTALL.md, post_install.sh
- 依存整合性: manifest `bundles/2.3.7/manifest.json`, SBOM `bundles/2.3.7/sbom.spdx.json`
- 関連Runbook: RUN-RELEASE-01, DR-LOCAL-01
```

## Expected Markdown Diff (INSTALL.md)
```diff
--- a/dist/offline_bundle/INSTALL.md
+++ b/dist/offline_bundle/INSTALL.md
@@
- **Verification Status**: DRAFT
+ **Verification Status**: PASSED
@@
-| 動作確認 | (記入してください) | 主要シグナル生成が成功 |
+| 動作確認 | ./scripts/run_smoke.sh | 主要シグナル生成が成功 |
@@
-| Ops Engineer | | | |
+| Ops Engineer | K.Okada | 2024-06-14 10:03 | Smokeテスト完了 |
```

## Attachment Manifest Example
| Attachment | Path | Notes |
| --- | --- | --- |
| Verification Report | `reports/offline_bundle/20240614/verification_report.json` | `make bundle-verify`の生成結果 |
| Install Log | `reports/offline_bundle/20240614/INSTALL_LOG.md` | コマンド履歴とハッシュ検証の証跡 |
| WORMコピー控え | `evidence/worm/20240614/SHA256_receipt.pdf` | 監査用電子署名付きレシート |

> 添付ファイルは`render_install_doc()`実行時に`attachments`配列へ渡されることを想定しています。
