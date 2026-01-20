from __future__ import annotations

from pathlib import Path

from tools.docbuild import DocBuildPipeline


def test_docbuild_dry_run(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    docs_root.mkdir(parents=True, exist_ok=True)
    docs_root.joinpath("runbooks").mkdir(parents=True, exist_ok=True)
    docs_root.joinpath("runbooks", "RUN-TEST-01.md").write_text(
        "# RUN-TEST-01: Demo\n", encoding="utf-8"
    )

    pipeline = DocBuildPipeline(
        docs_root=docs_root,
        templates_root=tmp_path / "docs" / "templates",
        weekly_templates_root=tmp_path / "reports" / "weekly" / "templates",
        prompt_packages_root=tmp_path / "docs" / "prompt_packages",
        output_dir=tmp_path / "site",
        build_dir=tmp_path / "reports" / "build",
    )
    result = pipeline.build_site(run_mkdocs=False)
    assert Path(result.log_path).exists()
    assert Path(result.config_path).exists()
