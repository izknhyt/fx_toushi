"""Scaffold required configuration files for FX Signal Tool.

This script materialises the CONFIG-SCAFF-01 templates described in
``detailed_design_fx_signal_tool_v1.md`` so that developers can quickly
bootstrap a working repository. It is idempotent by default: existing files
will not be overwritten unless ``--overwrite`` is specified.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from textwrap import dedent

REPO_ROOT = Path(__file__).resolve().parents[2]

_TEMPLATES: dict[Path, str] = {
    Path("config/scoring.yaml"): dedent(
        """\
        # config/scoring.yaml -- CONFIG-SCAFF-01 scaffold
        # このファイルは ScoringService / Strategy Scoreboard で共有する係数を定義します。
        # 実運用値に変更する際は detailed_design_fx_signal_tool_v1.md §3.7, §4.4.4 と
        # docs/runbooks/RUN-SCORE-01.md の承認手順を参照し、承認ログを残してください。

        version: 1
        # TODO: 係数セットをローリング運用する場合はバージョンを更新し、関連テストを同期する。
        weights:
          expected_r: 0.55       # TODO: バックテスト/ライブ乖離レビューで再調整する。
          pf_all: 0.35
          drawdown_penalty: 0.07
          spread_penalty: 0.03
        drift_penalty:
          max_pf_drift: 0.10     # PF ライブ/バックテスト比がこの閾値を超えた場合に警告。
          kappa: 0.35            # 乖離ペナルティの強度（ScoringDiagnostics で記録）。
        volatility_cap:
          max_expected_r: 2.5
          regime_weights:
            trend: 1.0
            range: 0.85
            spike: 0.65
        diagnostics:
          report_path: reports/diagnostics
          alert_delta_pf: 0.15        # TODO: Live Guard レポートと整合させる。
          alert_latency_p75: 150
        """
    ),
    Path("config/scoreboard.yaml"): dedent(
        """\
        # config/scoreboard.yaml -- CONFIG-SCAFF-01 scaffold
        # Strategy Scoreboard Service と Reporter 週次レビューで使用する閾値・重み設定。
        # 変更時は付録G.1および docs/runbooks/RUN-GOV-BOARD-01.md, RUN-RISK-07.md を確認し、
        # ガバナンスレビューでダブルサインを取得してください。

        version: 1
        thresholds:
          alpha: 75                 # TODO: StrategyScoringService の監視メトリクスと整合させる。
          decay: 35
          watchlist_cooldown_weeks: 4
        weights:
          profit_factor: 0.35
          sharpe: 0.30
          stability_index: 0.20
          regime_fit: 0.15
        watchlist_rules:
          min_consecutive_breaches: 2  # 閾値逸脱が連続 N 週でウォッチリスト追加。
          review_window_weeks: 4
        runbook_refs:
          watchlist: RUN-GOV-BOARD-01
          escalation: RUN-RISK-07
        """
    ),
    Path("config/risk_live_guard.yaml"): dedent(
        """\
        # config/risk_live_guard.yaml -- CONFIG-SCAFF-01 scaffold
        # ライブ性能ガードの閾値・通知設定。変更時は docs/runbooks/RUN-RISK-07.md と
        # detailed_design_fx_signal_tool_v1.md §4.4.3 を参照してください。

        version: 1
        window_days: 28             # ローリング評価日数（14〜60 の範囲で調整）。
        warmup_trades: 30
        pf_threshold: 1.08
        sharpe_threshold: 0.90
        latency_p75_threshold: 120  # 秒単位。Reduce-Only 推奨の境界値。
        live_guard_mode: paper      # TODO: Paper/Live 切替時は ModeContext と同期する。
        notify:
          kill_switch_review: true
          ops_agenda_task: true
        runbook_ref: RUN-RISK-07
        """
    ),
    Path("config/ops_readiness.yaml"): dedent(
        """\
        # config/ops_readiness.yaml -- CONFIG-SCAFF-01 scaffold
        # Ops Readiness レビュー用の重み・証跡パス・閾値。
        # 更新時は docs/runbooks/OPS-READINESS-01.md と
        # detailed_design_fx_signal_tool_v1.md §4.4.6 を参照してください。
        # 証跡は ops_worklog に記録してください。

        version: 1
        weights:
          backup_integrity: 0.30
          runbook_updates: 0.20
          drills_completed: 0.30
          incident_followup: 0.20
        evidence_paths:
          backups: reports/drill/backup_integrity.md    # TODO: 実際の証跡パスに合わせて更新。
          runbooks: docs/runbooks/
          incidents: docs/incident_reports/
          agenda: docs/runbooks/daily_agenda/
        thresholds:
          min_score: 80
          warn_score: 85
        runbook_refs:
          review: OPS-READINESS-01
          escalation: RUN-RISK-07
        """
    ),
}


def _write_file(path: Path, content: str, *, dry_run: bool, overwrite: bool) -> str:
    """Create or update a scaffold file."""

    action = "created"
    if path.exists():
        if not overwrite:
            rel = path.relative_to(REPO_ROOT).as_posix()
            return f"skipped {rel} (exists)"
        action = "overwrote"

    if dry_run:
        rel = path.relative_to(REPO_ROOT).as_posix()
        return f"[dry-run] {action} {rel}"

    path.parent.mkdir(parents=True, exist_ok=True)
    # Ensure trailing newline for POSIX compatibility.
    path.write_text(content.rstrip() + "\n", encoding="utf-8")
    rel = path.relative_to(REPO_ROOT).as_posix()
    return f"{action} {rel}"


def run(*, dry_run: bool, overwrite: bool) -> list[str]:
    """Apply scaffolds and return operation summaries."""

    summaries: list[str] = []
    for rel_path, template in sorted(_TEMPLATES.items()):
        output_path = REPO_ROOT / rel_path
        summaries.append(_write_file(output_path, template, dry_run=dry_run, overwrite=overwrite))
    return summaries


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialise required config scaffolds.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which files would be created without writing them.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing files with the scaffold content.",
    )
    args = parser.parse_args()

    results = run(dry_run=args.dry_run, overwrite=args.overwrite)
    for message in results:
        sys.stdout.write(f"{message}\n")


if __name__ == "__main__":
    main()
