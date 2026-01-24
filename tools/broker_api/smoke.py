"""Broker API smoke verification runner."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from src.execution.order_router import OrderDispatchRejected, OrderRouter


def _feature_enabled(*, flag: str, profile: str, path: Path) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    defaults = payload.get("defaults") if isinstance(payload, dict) else {}
    profile_flags = defaults.get(profile) if isinstance(defaults, dict) else {}
    return bool(profile_flags.get(flag)) if isinstance(profile_flags, dict) else False


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_validation_log(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Broker API Smoke ({payload['status']})",
        "",
        f"- Timestamp: {payload['timestamp']}",
        f"- Adapter: {payload.get('adapter')}",
        f"- Ticket ID: {payload.get('ticket_id')}",
        f"- Order ID: {payload.get('order_id')}",
        f"- Profile: {payload.get('profile')}",
        "",
        "## Notes",
        f"- Result: {payload.get('status')}",
        f"- Reason: {payload.get('reason', 'n/a')}",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticket", type=Path, help="Ticket payload JSON")
    parser.add_argument("--symbol", help="Symbol for manual smoke")
    parser.add_argument("--side", default="buy", help="Side (buy/sell)")
    parser.add_argument("--qty", type=float, default=0.1, help="Quantity")
    parser.add_argument("--entry-price", type=float, help="Entry price for marketable limit")
    parser.add_argument("--profile", default="paper", help="Profile (paper/live)")
    parser.add_argument("--adapter", default="sandbox", help="Broker adapter")
    parser.add_argument("--principal-id", required=True, help="Access principal ID")
    parser.add_argument("--device-id", required=True, help="Access device ID")
    parser.add_argument(
        "--feature-flags",
        type=Path,
        default=Path("config/feature_flags.yaml"),
        help="Feature flags path",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("reports") / "validation_log",
        help="Validation log output dir",
    )
    args = parser.parse_args()

    if not _feature_enabled(
        flag="brokers.api_enabled", profile=args.profile, path=args.feature_flags
    ):
        print("brokers.api_enabled is false; aborting smoke run", file=sys.stderr)
        return 2

    if args.ticket:
        payload = json.loads(args.ticket.read_text(encoding="utf-8"))
    else:
        if not args.symbol or not args.entry_price:
            print("--symbol and --entry-price required for manual smoke", file=sys.stderr)
            return 1
        payload = {
            "ticket_id": f"broker-smoke-{datetime.now(timezone.utc):%Y%m%d%H%M%S}",
            "symbol": args.symbol,
            "side": args.side,
            "quantity": args.qty,
            "entry_type": "marketable_limit",
            "entry_price": args.entry_price,
        }

    payload.setdefault("adapter", args.adapter)
    payload.setdefault("profile", args.profile)
    payload.setdefault("principal_id", args.principal_id)
    payload.setdefault("device_id", args.device_id)

    router = OrderRouter.from_defaults(feature_flags_path=args.feature_flags)
    timestamp = _utc_stamp()
    result: dict[str, object]
    try:
        order = router.submit(payload)
        result = {
            "status": "ok",
            "timestamp": timestamp,
            "adapter": order.adapter,
            "ticket_id": order.ticket_id,
            "order_id": order.order_id,
            "profile": payload.get("profile"),
        }
        exit_code = 0
    except OrderDispatchRejected as exc:
        result = {
            "status": "blocked",
            "timestamp": timestamp,
            "adapter": payload.get("adapter"),
            "ticket_id": payload.get("ticket_id"),
            "order_id": None,
            "profile": payload.get("profile"),
            "reason": exc.reason,
        }
        exit_code = 2
    except Exception as exc:  # pragma: no cover - defensive
        result = {
            "status": "error",
            "timestamp": timestamp,
            "adapter": payload.get("adapter"),
            "ticket_id": payload.get("ticket_id"),
            "order_id": None,
            "profile": payload.get("profile"),
            "reason": str(exc),
        }
        exit_code = 1

    date_label = datetime.now(timezone.utc).strftime("%Y%m%d")
    log_path = args.outdir / f"AC-06_broker_api_{date_label}.md"
    _write_validation_log(log_path, result)
    print(json.dumps({"validation_log": str(log_path), **result}, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
