# Audit Event Schema (JSONL)

## Overview
- **Writer**: `AuditWriter` (`src/persistence/audit_writer.py`)
- **Output Path**: `logs/audit/YYYYMMDD.jsonl`
- **Format**: JSON Lines (1 event per line, UTF-8, LF)
- **Retention**: 日次ローテーション、90日保持後に`logs/audit/archive/`へ圧縮移送

各レコードは監査対象操作（HITLチケット、Kill Switch、Config変更など）を記録し、`consent_reference_id`/`cfg_hash`/`board_mode`を必須フィールドとして保持する。`AuditWriter`は同じ構造を`audit_events.db`へ二重書込する実装を想定している。

## JSONL Structure
```json
{
  "ts": "2025-02-21T09:15:32.481+09:00",
  "record_type": "ticket.action",
  "ticket_id": "TCK-20250221-001",
  "action": "approve",
  "actor": "ops_manager",
  "consent_reference_id": "CONSENT-20250115-PO01",
  "board_mode": "guarded",
  "spread_state": "normal",
  "health_state": "ok",
  "cfg_hash": "7f9c2c5c",
  "data_hash": "a1c4e6d0",
  "delta": {
    "before": {"status": "pending"},
    "after": {"status": "approved"},
    "diff": {"status": "approved"}
  },
  "notes": "Approved after spread recheck",
  "extras": {
    "checklist": {
      "field": "sl_tp_verified",
      "ack_actor": "risk_lead",
      "ack_ts": "2025-02-21T09:13:10.012+09:00"
    },
    "cli_command": "tradectl ticket approve --id TCK-20250221-001"
  }
}
```

## Field Definitions
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `ts` | string (RFC 3339, JST) | Yes | レコード発生時刻。`AuditWriter`がUTC→JSTで正規化。 |
| `record_type` | string | Yes | 操作種別。例: `ticket.action`, `killswitch.transition`, `config.apply`, `consent.link`. |
| `ticket_id` | string | Conditional | チケット操作時のID。`record_type`が`ticket.*`の場合は必須。 |
| `action` | string | Yes | 実施した操作。例: `approve`, `reject`, `stop`, `ack`. |
| `actor` | string | Yes | 操作を行ったユーザー/サービス識別子。 |
| `consent_reference_id` | string | Yes | 関連するリスク同意ログID。HITL/Config操作で同意トレーサビリティを保持。 |
| `board_mode` | string | Yes | 操作時のSignal Boardモード。`normal | guarded | halted`。 |
| `spread_state` | string | No | Spread Monitorの状態。`normal | watch | cooldown | halt`。 |
| `health_state` | string | No | `HealthMonitor`の統合状態。`ok | degraded | soft_stop | hard_stop`。 |
| `cfg_hash` | string | Yes | 適用中の設定ハッシュ (`ConfigRegistry.current_hash`)。 |
| `data_hash` | string | No | 同期中データセットのハッシュ (`data_manifest.hash`)。 |
| `delta` | object | Conditional | 状態差分。`before`/`after`/`diff`キーを持つ。操作が状態変化を伴う場合に必須。 |
| `notes` | string | No | 補足コメントや判断理由。 |
| `extras` | object | No | 任意の追加メタデータ。例: `checklist`, `cli_command`, `runbook_ref`. |

### Conditional Requirements
- `ticket_id`: `record_type` が `ticket.*` または `manual.ticket.*` の場合必須。
- `delta`: `action` が状態更新 (`approve`, `reject`, `stop`, `apply`, `rollback`) を伴う場合必須。

## Validation Rules
- `record_type` はドット区切りで最大3セグメント (`domain.category[.detail]`)。
- `cfg_hash`, `data_hash` は16進小文字8桁以上。
- `extras.checklist` が存在する場合、`field`, `ack_actor`, `ack_ts` を含める。
- `notes` は最大1024文字。超過時は`AuditWriter`がトリムし`extras.truncated=true`を付与。

## Schema Evolution & Storage Policy
- JSON Schemaファイルは`docs/schemas/`配下に配置する（将来拡張）。`audit_event.schema.json`の初版はM1.1で追加予定。
- 互換性のある拡張は新フィールドを任意属性として追加し、削除/必須化はバージョン管理 (`schema_version`) を伴う。
- `AuditWriter`のリリースごとに本ドキュメントの改訂履歴を更新し、`docs/development_style_and_linting.md`の指針に従ってテストケース (`pytest -k audit_chain`) を同期させる。
