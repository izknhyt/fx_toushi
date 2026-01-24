"""GUI state store with persistence helpers."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:  # optional encryption dependency
    from cryptography.fernet import Fernet, InvalidToken
except Exception:  # pragma: no cover - optional dependency
    Fernet = None
    InvalidToken = Exception


Reducer = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]


@dataclass(slots=True)
class GuiStateStore:
    state_path: Path
    schema_version: str = "gui.state.v1"
    state: dict[str, Any] = field(default_factory=dict)
    reducers: dict[str, Reducer] = field(default_factory=dict)
    encryption_key: str | None = None
    allow_plaintext: bool = False

    def rehydrate(self) -> dict[str, Any]:
        if not self.state_path.exists():
            self.state = self._default_state()
            return self.state
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        if payload.get("encrypted"):
            decrypted = _decrypt_payload(payload.get("payload"), self._effective_key())
            payload = json.loads(decrypted)
        self.state = {**self._default_state(), **payload}
        return self.state

    def persist(self) -> Path:
        payload = dict(self.state)
        payload["schema_version"] = self.schema_version
        payload["updated_at"] = _utcnow_iso()
        serialized = json.dumps(payload, ensure_ascii=False, indent=2)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.state_path.with_suffix(".tmp")
        if self._effective_key():
            encrypted = _encrypt_payload(serialized, self._effective_key())
            wrapper = {"encrypted": True, "payload": encrypted}
            tmp_path.write_text(
                json.dumps(wrapper, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        elif self.allow_plaintext:
            tmp_path.write_text(serialized + "\n", encoding="utf-8")
        else:
            raise ValueError("GUI_STATE_KEY is required for encrypted state store")
        os.replace(tmp_path, self.state_path)
        os.chmod(self.state_path, 0o600)
        return self.state_path

    def reduce(self, action_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        reducer = self.reducers.get(action_type)
        if reducer is None:
            self.state = {**self.state, "last_action": action_type, "last_payload": payload}
            return self.state
        self.state = reducer(self.state, payload)
        self.state["last_action"] = action_type
        return self.state

    def register_reducer(self, action_type: str, reducer: Reducer) -> None:
        self.reducers[action_type] = reducer

    def _default_state(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "updated_at": _utcnow_iso(),
            "board": {},
            "tickets": [],
            "agenda": [],
            "alerts": [],
        }

    def _effective_key(self) -> str | None:
        return self.encryption_key or os.getenv("GUI_STATE_KEY")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _encrypt_payload(payload: str, key: str | None) -> str:
    cipher = _build_cipher(key)
    token = cipher.encrypt(payload.encode("utf-8"))
    return token.decode("utf-8")


def _decrypt_payload(token: str | None, key: str | None) -> str:
    if not token:
        raise ValueError("encrypted state payload missing")
    cipher = _build_cipher(key)
    try:
        return cipher.decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:  # pragma: no cover - defensive
        raise ValueError("invalid GUI state encryption key") from exc


def _build_cipher(key: str | None):
    if Fernet is None:
        raise ValueError("cryptography is required for GUI state encryption")
    if not key:
        raise ValueError("GUI_STATE_KEY is required for GUI state encryption")
    return Fernet(key)


__all__ = ["GuiStateStore"]
