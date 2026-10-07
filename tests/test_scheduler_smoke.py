"""Smoke tests - routing, behavior gates, consistency (no live network)."""

from __future__ import annotations

import pytest

from enterprise_scout_mcp.behavior.orchestrator import BehaviorOrchestrator
from enterprise_scout_mcp.config import AppConfig, BehaviorConfig, RoutingConfig
from enterprise_scout_mcp.consistency.validator import EnvironmentValidator
from enterprise_scout_mcp.models import ChannelKind, CollectTask, PersonaProfile, Platform
from enterprise_scout_mcp.routing.risk_router import RiskAwareRouter


def test_router_ensan_only_uses_enscan_even_if_playwright_up():
    router = RiskAwareRouter(RoutingConfig(ensan_only=True))
    task = CollectTask(keyword="x", platform=Platform.AIQICHA, fields=("captcha", "partner"))
    channel = router.select_channel(
        task,
        ensan_available=True,
        playwright_available=True,
        handaas_available=False,
    )
    assert channel == ChannelKind.ENSCAN_GO


def test_router_ensan_only_raises_when_enscan_down():
    router = RiskAwareRouter(RoutingConfig(ensan_only=True))
    task = CollectTask(keyword="x", platform=Platform.TIANYANCHA)
    with pytest.raises(RuntimeError, match="ENScan_GO unavailable"):
        router.select_channel(
            task,
            ensan_available=False,
            playwright_available=True,
            handaas_available=False,
        )


def test_router_prefers_enscan_for_bulk_fields():
    router = RiskAwareRouter(RoutingConfig(ensan_only=True))
    task = CollectTask(keyword="test", platform=Platform.AIQICHA, fields=("icp",))
    channel = router.select_channel(
        task,
        ensan_available=True,
        playwright_available=True,
        handaas_available=False,
    )
    assert channel == ChannelKind.ENSCAN_GO


def test_behavior_quota_blocks():
    orch = BehaviorOrchestrator(BehaviorConfig(global_daily_quota=1, persona_daily_quota=1))
    ok, _ = orch.can_proceed("p1")
    assert ok
    orch.on_success("p1")
    ok, reason = orch.can_proceed("p1")
    assert not ok
    assert "quota" in reason


def test_consistency_detects_ua_mismatch():
    persona = PersonaProfile(
        id="t",
        device={"user_agent": "UA-A"},
        network={},
        behavior={},
    )
    report = EnvironmentValidator().validate(
        persona,
        outbound_headers={"User-Agent": "UA-B"},
    )
    assert not report.ok
    assert any("user-agent" in v for v in report.violations)


def test_load_default_config():
    cfg = AppConfig()
    assert cfg.integrations.ensan_go.base_url.startswith("http")
    assert cfg.routing.ensan_only is True
    assert cfg.integrations.playwright.enabled is False
