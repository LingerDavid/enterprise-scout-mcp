"""Tier-aware routing for L1 GSXT registry spike."""

from __future__ import annotations

import pytest

from enterprise_scout_mcp.config import RoutingConfig
from enterprise_scout_mcp.models import ChannelKind, CollectTask, Dimension, Platform, SourceTier
from enterprise_scout_mcp.routing.tier_router import TierAwareRouter


def test_tier_router_l1_registry_gsxt():
    router = TierAwareRouter(RoutingConfig())
    task = CollectTask(
        keyword="苏州挚途",
        platform=Platform.GSXT,
        dimensions=(Dimension.REGISTRY,),
        prefer_tier=SourceTier.L1,
        fields=("enterprise_info",),
    )
    decision = router.select(task, gsxt_available=True, ensan_available=True)
    assert decision.channel == ChannelKind.GSXT_OFFICIAL
    assert decision.source_tier == SourceTier.L1
    assert decision.dimension == Dimension.REGISTRY


def test_tier_router_l2_registry_enscan():
    router = TierAwareRouter(RoutingConfig())
    task = CollectTask(
        keyword="x",
        platform=Platform.GSXT,
        dimensions=(Dimension.REGISTRY,),
        prefer_tier=SourceTier.L2,
        fields=("enterprise_info",),
    )
    decision = router.select(task, gsxt_available=False, ensan_available=True)
    assert decision.channel == ChannelKind.ENSCAN_GO
    assert decision.source_tier == SourceTier.L2


def test_tier_router_unimplemented_dimension():
    router = TierAwareRouter(RoutingConfig())
    task = CollectTask(
        keyword="x",
        platform=Platform.GSXT,
        dimensions=(Dimension.EQUITY,),
        prefer_tier=SourceTier.L1,
    )
    with pytest.raises(RuntimeError, match="not implemented"):
        router.select(task, gsxt_available=True, ensan_available=True)
