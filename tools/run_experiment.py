"""Execute an experiment run from the scheduler queue."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.research.experiment import ExperimentTrackerService


def _load_metrics(path: Path | None) -> dict[str, object]:
    if not path:
        return {}
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute experiment runs.")
    parser.add_argument("--manifest", required=True, help="Experiment manifest ID")
    parser.add_argument("--run", dest="run_id", required=True, help="Run ID to complete")
    parser.add_argument("--metrics", type=Path, help="Metrics JSON file")
    parser.add_argument("--artifact", action="append", type=Path, default=[], help="Artifacts to attach")
    args = parser.parse_args()

    service = ExperimentTrackerService()
    metrics = _load_metrics(args.metrics)
    service.complete_run(args.run_id, metrics=metrics, artifacts=args.artifact)
    print(json.dumps({"status": "ok", "run_id": args.run_id}, ensure_ascii=False))


if __name__ == "__main__":
    main()
