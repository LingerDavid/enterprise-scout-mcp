"""Behavior orchestrator - quotas, cooldowns, dynamic delay."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass

from enterprise_scout_mcp.config import BehaviorConfig


@dataclass
class PersonaState:
    daily_count: int = 0
    cooldown_until: float = 0.0


class BehaviorOrchestrator:
    def __init__(self, config: BehaviorConfig) -> None:
        self._config = config
        self._global_count = 0
        self._persona: dict[str, PersonaState] = {}

    def _state(self, persona_id: str) -> PersonaState:
        return self._persona.setdefault(persona_id, PersonaState())

    def can_proceed(self, persona_id: str) -> tuple[bool, str]:
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
        self._global_count += 1
        self._state(persona_id).daily_count += 1

    def on_captcha(self, persona_id: str) -> None:
        until = time.time() + self._config.cooldown_after_captcha_seconds
        self._state(persona_id).cooldown_until = until

    def on_block(self, persona_id: str) -> None:
        until = time.time() + self._config.cooldown_after_block_seconds
        self._state(persona_id).cooldown_until = until
