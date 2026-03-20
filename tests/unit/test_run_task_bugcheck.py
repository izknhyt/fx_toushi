from __future__ import annotations

from tools.run_task_bugcheck import build_bugcheck_plan, infer_scopes


def test_infer_scopes_from_shadow_and_agenda_files() -> None:
    scopes = infer_scopes(
        [
            "src/interfaces/gui/shadow_daily_review.py",
            "src/ops/agenda.py",
            "tools/gui_ops_loop.py",
        ]
    )

    assert "shadow_monitor" in scopes
    assert "ops_agenda" in scopes
    assert "portfolio_parity" in scopes
    assert "python_compile" in scopes


def test_build_bugcheck_plan_warns_when_development_plan_missing() -> None:
    plan = build_bugcheck_plan(
        [
            "src/interfaces/gui/shadow_daily_review.py",
            "tests/unit/test_shadow_daily_review.py",
        ]
    )

    assert "development_plan_not_in_changed_files" in plan["warnings"]
    assert any("test_shadow_daily_review.py" in command for command in plan["commands"])
    assert any(command.startswith("python3 -m py_compile") for command in plan["commands"])


def test_build_bugcheck_plan_accepts_explicit_scope_without_changed_files() -> None:
    plan = build_bugcheck_plan([], explicit_scopes=["ops_agenda"])

    assert plan["scopes"] == ["ops_agenda"]
    assert plan["warnings"] == []
    assert plan["commands"] == [
        "pytest -q tests/unit/test_ops_agenda_status.py tests/unit/test_ops_agenda_drills.py"
    ]
