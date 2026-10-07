"""Behavior orchestrator - quotas, cooldowns, dynamic delay (optionally persisted)."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from enterprise_scout_mcp.config import BehaviorConfig

if TYPE_CHECKING:
    from enterprise_scout_mcp.state.store import StateStore

STATE_FILE = "behavior.json"


@dataclass
class PersonaState:
    daily_count: int = 0
    cooldown_until: float = 0.0


class BehaviorOrchestrator:
    def __init__(self, config: BehaviorConfig, store: StateStore | None = None) -> None:
        self._config = config
        self._store = store
        self._day = ""
        self._global_count = 0
        self._persona: dict[str, PersonaState] = {}
        self._load()

    def _load(self) -> None:
        if self._store is None:
            self._day = self._today()
            return
        raw = self._store.load(STATE_FILE)
        self._day = str(raw.get("day") or self._store.today_key())
        today = self._store.today_key()
        if self._day != today:
            self._day = today
            self._global_count = 0
            self._persona = {}
            self._persist()
            return
        self._global_count = int(raw.get("global_count") or 0)
        self._persona = {}
        for pid, row in (raw.get("personas") or {}).items():
            self._persona[pid] = PersonaState(
                daily_count=int(row.get("daily_count") or 0),
                cooldown_until=float(row.get("cooldown_until") or 0.0),
            )

    def _today(self) -> str:
        from datetime import date

        return date.today().isoformat()

    def _persist(self) -> None:
        if self._store is None:
            return
        payload = {
            "day": self._day,
            "global_count": self._global_count,
            "personas": {
                pid: {
                    "daily_count": st.daily_count,
                    "cooldown_until": st.cooldown_until,
                }
                for pid, st in self._persona.items()
            },
        }
        self._store.save(STATE_FILE, payload)

    def _roll_day_if_needed(self) -> None:
        today = self._store.today_key() if self._store else self._today()
        if self._day != today:
            self._day = today
            self._global_count = 0
            self._persona = {}
            self._persist()

    def _state(self, persona_id: str) -> PersonaState:
        return self._persona.setdefault(persona_id, PersonaState())

    def can_proceed(self, persona_id: str) -> tuple[bool, str]:
        self._roll_day_if_needed()
        now = time.time()
        state = self._state(persona_id)
        if now < state.cooldown_until:
            return False, "persona in cooldown"
        if self._global_count >= self._config.global_daily_quota:
            return False, "global daily quota exhausted"
        if state.daily_count >= self._config.persona_daily_quota:
            return False, "persona daily quota exhausted"
        return True, ""

    def wait_before_request(self, persona_id: str) -> None:
        state = self._state(persona_id)
        base = random.uniform(self._config.min_delay_seconds, self._config.max_delay_seconds)
        jitter = float(state.daily_count) * 0.05
        time.sleep(base + jitter)

    def on_success(self, persona_id: str) -> None:
        self._roll_day_if_needed()
        self._global_count += 1
        self._state(persona_id).daily_count += 1
        self._persist()

    def on_captcha(self, persona_id: str) -> None:
        until = time.time() + self._config.cooldown_after_captcha_seconds
        self._state(persona_id).cooldown_until = until
        self._persist()

    def on_block(self, persona_id: str) -> None:
        until = time.time() + self._config.cooldown_after_block_seconds
        self._state(persona_id).cooldown_until = until
        self._persist()
