"""Validation playbook sync helpers."""

from __future__ import annotations

from pathlib import Path

from src.data.manifest import DataManifestService


def sync_playbook(*, manifest_path: Path, output_dir: Path) -> dict[str, object]:
    service = DataManifestService(path=manifest_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, str] = {}
    for entry in service.entries:
        if not entry.validation_playbook_id:
            continue
        playbook_id = entry.validation_playbook_id
        path = output_dir / f"{playbook_id}.md"
        lines = [
            f"# Validation Playbook {playbook_id}",
            "",
            f"- Entry ID: {entry.id}",
            f"- Kind: {entry.kind}",
            f"- Path: {entry.path}",
            f"- Hash: {entry.hash_sha256}",
            f"- Owner: {entry.owner or 'n/a'}",
            f"- Status: {entry.status}",
        ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        outputs[playbook_id] = str(path)
    return {"status": "ok", "outputs": outputs}


__all__ = ["sync_playbook"]
