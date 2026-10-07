"""Persona engine — device + network + behavior bound as one virtual identity."""

from __future__ import annotations

from pathlib import Path

import yaml

from enterprise_scout_mcp.models import PersonaProfile


class PersonaEngine:
    def __init__(self, personas_dir: str | Path) -> None:
        self._dir = Path(personas_dir)
        self._cache: dict[str, PersonaProfile] = {}

    def list_ids(self) -> list[str]:
        if not self._dir.is_dir():
            return []
        return sorted(p.stem for p in self._dir.glob("*.yaml"))

    def load(self, persona_id: str) -> PersonaProfile:
        if persona_id in self._cache:
            return self._cache[persona_id]
        path = self._dir / f"{persona_id}.yaml"
        if not path.is_file():
            raise FileNotFoundError(f"Persona not found: {persona_id} ({path})")
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        profile = PersonaProfile(
            id=str(raw.get("id", persona_id)),
            device=dict(raw.get("device") or {}),
            network=dict(raw.get("network") or {}),
            behavior=dict(raw.get("behavior") or {}),
        )
        self._cache[persona_id] = profile
        return profile

    def pick_for_platform(self, platform: str, *, default: str) -> PersonaProfile:
        """Rotate persona by platform tag; falls back to default."""
        tagged = [
            pid
            for pid in self.list_ids()
            if platform in (self.load(pid).network.get("platforms") or [])
        ]
        persona_id = tagged[0] if tagged else default
        return self.load(persona_id)
