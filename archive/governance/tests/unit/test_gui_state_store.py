from __future__ import annotations

from pathlib import Path

import pytest

from src.interfaces.gui.tauri_app.state_store import GuiStateStore


def test_gui_state_store_persist_and_rehydrate(tmp_path: Path) -> None:
    fernet = pytest.importorskip("cryptography.fernet")
    state_path = tmp_path / "state.json"
    store = GuiStateStore(state_path=state_path, encryption_key=fernet.Fernet.generate_key().decode("utf-8"))
    store.state["board"] = {"status": "ok"}
    store.persist()

    rehydrated = GuiStateStore(
        state_path=state_path, encryption_key=store.encryption_key
    ).rehydrate()
    assert rehydrated["board"]["status"] == "ok"
