---
runbook_id: RUN-INC-01
title: Incident Response & Postmortem
owner: ops
version: 0.1
last_updated: 2026-01-12
---

# Incident Response & Postmortem

## Purpose
Define the standard flow for opening, documenting, and closing incident postmortems.

## Checklist
- [ ] インシデント開始を記録し、`IncidentPostmortemService.open`でIDを発行する
- [ ] タイムラインにRunbook手順と証跡を追記する
- [ ] フォレンジクス結果を`reports/ops/incidents/<id>/`へ保存する
- [ ] フォローアップタスクを登録し、完了状況を確認する
- [ ] 検証メモと署名を添えてクローズする

## Evidence
- `reports/ops/incidents/<id>/postmortem.md`
- `metrics/incident_postmortem.jsonl`
- `docs/validation_playbook/AC43_postmortem.yaml`
