from __future__ import annotations

from pathlib import Path

from src.data.manifest import DataManifestService


def test_data_manifest_record_and_verify(tmp_path: Path) -> None:
    manifest_path = tmp_path / "data_manifest.json"
    target_path = tmp_path / "sample.txt"
    target_path.write_text("hello", encoding="utf-8")

    service = DataManifestService(path=manifest_path)
    entry = service.record(path=target_path, kind="fixture", owner="tester")
    assert entry.id

    verification = service.verify(path=target_path)
    assert verification["status"] == "ok"
    assert verification["expected_hash"] == entry.hash_sha256


def test_data_manifest_diff(tmp_path: Path) -> None:
    base_path = tmp_path / "base_manifest.json"
    target_path = tmp_path / "target_manifest.json"
    file_a = tmp_path / "a.txt"
    file_b = tmp_path / "b.txt"
    file_a.write_text("a", encoding="utf-8")
    file_b.write_text("b", encoding="utf-8")

    base_service = DataManifestService(path=base_path)
    base_service.record(path=file_a, kind="fixture")

    target_service = DataManifestService(path=target_path)
    target_service.record(path=file_a, kind="fixture")
    target_service.record(path=file_b, kind="fixture")

    diff = target_service.diff(base=base_path, target=target_path)
    assert diff["added"]
