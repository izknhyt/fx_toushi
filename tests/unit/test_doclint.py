from __future__ import annotations

from pathlib import Path

from tools.doclint import DocLint


def test_doclint_ux_color_validation(tmp_path: Path) -> None:
    ux_path = tmp_path / "docs" / "ux_feedback.md"
    ux_path.parent.mkdir(parents=True, exist_ok=True)
    ux_path.write_text(
        "\n".join(
            [
                "# UX Feedback",
                "",
                "Use color #FF5F57 for warnings.",
                "Avoid #123456 in docs.",
            ]
        ),
        encoding="utf-8",
    )
    issues = DocLint(category="ux").lint_paths([ux_path])
    assert any("unsupported color" in issue.message for issue in issues)
