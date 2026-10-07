"""JSON state persistence for behavior quotas and routing stats."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any


class StateStore:
    def __init__(self, state_dir: Path) -> None:
        self._dir = state_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def path(self, name: str) -> Path:
        return self._dir / name

    def load(self, name: str) -> dict[str, Any]:
        path = self.path(name)
        if not path.is_file():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8")) or {}
        except json.JSONDecodeError:
            return {}

    def save(self, name: str, payload: dict[str, Any]) -> None:
        path = self.path(name)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def today_key(self) -> str:
        return date.today().isoformat()
