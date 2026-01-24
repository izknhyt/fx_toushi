"""Feature flag utilities for Shadow Gateway."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

import yaml


@dataclass(slots=True)
class ShadowGatewayFeature:
    path: Path = Path("config/feature_flags.yaml")

    def is_enabled(self, flag: str, *, mode: str) -> bool:
        payload = self._load()
        defaults = payload.get("defaults")
        if not isinstance(defaults, Mapping):
            return False
        profile_defaults = defaults.get(mode)
        if not isinstance(profile_defaults, Mapping):
            return False
        return bool(profile_defaults.get(flag, False))

    def set_flag(self, flag: str, *, mode: str, value: bool) -> dict[str, Any]:
        payload = self._load()
        defaults = payload.setdefault("defaults", {})
        if not isinstance(defaults, dict):
            defaults = {}
            payload["defaults"] = defaults
        profile_defaults = defaults.get(mode)
        if not isinstance(profile_defaults, dict):
            profile_defaults = {}
            defaults[mode] = profile_defaults
        profile_defaults[flag] = bool(value)
        dumper = getattr(yaml, "safe_dump", None) or getattr(yaml, "dump", None)
        if dumper:
            text = dumper(payload, sort_keys=False)
        else:
            text = json.dumps(payload, ensure_ascii=False, indent=2)
        self.path.write_text(text, encoding="utf-8")
        return {"flag": flag, "mode": mode, "value": bool(value), "path": str(self.path)}

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            text = self.path.read_text(encoding="utf-8")
            if text.lstrip().startswith("{"):
                payload = json.loads(text)
            else:
                loader = getattr(yaml, "safe_load", None)
                payload = loader(text) if loader else json.loads(text)
            payload = payload or {}
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}


__all__ = ["ShadowGatewayFeature"]
