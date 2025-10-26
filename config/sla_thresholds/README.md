# SLA Threshold Profiles (CONFIG-SCAFF-01 scaffold)

- 詳細設計: §3.1 データ取得ガード / §4.4 設定ファイル / §9.4.4 データ品質ガード連携
- Runbook: [RUN-DATA-05](../../docs/runbooks/RUN-DATA-05.md), [RUN-DATA-06](../../docs/runbooks/RUN-DATA-06.md)
- Validation Data Playbook: [AC-45 Data SLA](../../reports/validation_log/AC-45_sla_20250220.md)
- Schema: `docs/schemas/sla_threshold_profile.schema.json`（`schema_version`更新時に同期）

## Structure

```yaml
schema_version: 0  # docs/schemas/sla_threshold_profile.schema.json に追従
profile_id: default
provider_thresholds:
  yfinance:
    fetch:
      target_ms: 60000
      warning_ms: 90000
      critical_ms: 120000
    processing:
      target_ms: 18000
      warning_ms: 24000
      critical_ms: 30000
  dukascopy:
    fetch:
      target_ms: 15000
      warning_ms: 20000
      critical_ms: 25000
notes: |
  Runbook RUN-DATA-05 の手順1で使用する SLA 参考値。
  実際の値は `metrics/data_ingestion_sla.jsonl` と `reports/performance/data_latency/<date>.md` を根拠に更新。
```

## Authoring guidelines

1. `config/sla_thresholds/<profile>.yaml` を追加する際は `schema_version` を必ずインクリメント。
2. `provider_thresholds.<provider>.fetch|processing` の `target ≤ warning ≤ critical` を維持し、Runbookチェックリストでダブルサインを取得。
3. Pull Request では `pytest -k config_schema_smoke`（スモークテスト予定）と `make sla-report` の結果を添付。
4. 適用後は Validation Data Playbook (AC-45) と Runbook `RUN-DATA-05` の履歴欄を更新し、`reports/governance/runbook_changelog.md` に記録。
