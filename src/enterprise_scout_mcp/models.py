"""Shared request/response contracts for the orchestration layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from enterprise_scout_mcp.defaults import DEFAULT_REGISTRY_FIELDS


class Platform(str, Enum):
    GSXT = "gsxt"
    AIQICHA = "aiqicha"
    TIANYANCHA = "tianyancha"
    KUAICHA = "kuaicha"
    RISKBIRD = "riskbird"
    HANDAAS = "handaas"


class ChannelKind(str, Enum):
    GSXT_OFFICIAL = "gsxt_official"
    ENSCAN_GO = "enscan_go"
    PLAYWRIGHT = "playwright"
    HANDAAS_API = "handaas_api"


class SourceTier(str, Enum):
    L1 = "l1"
    L2 = "l2"
    L3 = "l3"


class Dimension(str, Enum):
    REGISTRY = "registry"
    EQUITY = "equity"
    CREDIT = "credit"
    JUDICIAL = "judicial"
    IP = "ip"
    DIGITAL = "digital"


class ResultGrade(str, Enum):
    OK = "ok"
    PARTIAL = "partial"
    CAPTCHA = "captcha"
    BLOCKED = "blocked"
    AUTH_EXPIRED = "auth_expired"
    ERROR = "error"


@dataclass(frozen=True)
class CollectTask:
    keyword: str
    platform: Platform
    fields: tuple[str, ...] = DEFAULT_REGISTRY_FIELDS
    dimensions: tuple[Dimension, ...] = (Dimension.REGISTRY,)
    prefer_tier: SourceTier | None = None
    depth: int = 1
    force_channel: ChannelKind | None = None

    @property
    def primary_dimension(self) -> Dimension:
        return self.dimensions[0] if self.dimensions else Dimension.REGISTRY

    @property
    def tiered_collect(self) -> bool:
        return self.platform == Platform.GSXT or self.prefer_tier is not None


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
    source_tier: SourceTier | None = None
    dimension: Dimension | None = None
    degraded: bool = False
