"""Persisted behavior and routing state."""

from __future__ import annotations

from pathlib import Path

from enterprise_scout_mcp.behavior.orchestrator import BehaviorOrchestrator
from enterprise_scout_mcp.config import BehaviorConfig, RoutingConfig
from enterprise_scout_mcp.models import ChannelKind, Platform
from enterprise_scout_mcp.routing.risk_router import RiskAwareRouter
from enterprise_scout_mcp.state.store import StateStore


def test_behavior_persists_across_instances(tmp_path: Path) -> None:
    store = StateStore(tmp_path)
    orch = BehaviorOrchestrator(
        BehaviorConfig(
            global_daily_quota=10,
            persona_daily_quota=10,
            min_delay_seconds=0,
            max_delay_seconds=0,
        ),
        store=store,
    )
    orch.on_success("p1")
    orch2 = BehaviorOrchestrator(
        BehaviorConfig(global_daily_quota=10, persona_daily_quota=10),
        store=store,
    )
    assert orch2._global_count == 1
    assert orch2._state("p1").daily_count == 1


def test_router_persists_stats(tmp_path: Path) -> None:
    store = StateStore(tmp_path)
    router = RiskAwareRouter(RoutingConfig(), store=store)
    router.record(Platform.AIQICHA, ChannelKind.ENSCAN_GO, "ok")
    router2 = RiskAwareRouter(RoutingConfig(), store=store)
    stats = router2.stats_for(Platform.AIQICHA, ChannelKind.ENSCAN_GO)
    assert stats.attempts == 1
    assert stats.successes == 1
