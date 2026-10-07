"""Shared request/response contracts for the orchestration layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Platform(str, Enum):
    AIQICHA = "aiqicha"
    TIANYANCHA = "tianyancha"
    KUAICHA = "kuaicha"
    RISKBIRD = "riskbird"
    HANDAAS = "handaas"


class ChannelKind(str, Enum):
    ENSCAN_GO = "enscan_go"
    PLAYWRIGHT = "playwright"
    HANDAAS_API = "handaas_api"


class ResultGrade(str, Enum):
    OK = "ok"
    PARTIAL = "partial"
    CAPTCHA = "captcha"
    BLOCKED = "blocked"
    ERROR = "error"


@dataclass(frozen=True)
class CollectTask:
    keyword: str
    platform: Platform
    fields: tuple[str, ...] = ("enterprise_info",)
    depth: int = 1
    force_channel: ChannelKind | None = None


@dataclass
class PersonaProfile:
    id: str
    device: dict[str, Any]
    network: dict[str, Any]
    behavior: dict[str, Any]

    @property
    def user_agent(self) -> str:
        return str(self.device.get("user_agent", ""))

    @property
    def timezone(self) -> str:
        return str(self.device.get("timezone", "Asia/Shanghai"))

    @property
    def locale(self) -> str:
        return str(self.device.get("locale", "zh-CN"))


@dataclass
class ChannelStats:
    attempts: int = 0
    successes: int = 0
    captchas: int = 0
    blocks: int = 0

    @property
    def success_rate(self) -> float:
        if self.attempts == 0:
            return 1.0
        return self.successes / self.attempts


@dataclass
class CollectResult:
    task: CollectTask
    channel: ChannelKind
    grade: ResultGrade
    data: dict[str, Any] = field(default_factory=dict)
    message: str = ""
    persona_id: str = ""
