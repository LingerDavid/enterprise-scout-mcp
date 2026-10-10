"""Tier-aware routing — L1 official > L2 commercial > L3 academic."""

from __future__ import annotations

from dataclasses import dataclass

from enterprise_scout_mcp.config import RoutingConfig
from enterprise_scout_mcp.models import ChannelKind, CollectTask, Dimension, SourceTier
from enterprise_scout_mcp.routing.dimension_plan import channel_for, is_stub_dimension


@dataclass(frozen=True)
class RouteDecision:
    channel: ChannelKind
    source_tier: SourceTier
    dimension: Dimension


class TierAwareRouter:
    """Select channel by dimension + preferred source tier."""

    def __init__(self, config: RoutingConfig) -> None:
        self._config = config

    def select(
        self,
        task: CollectTask,
        *,
        gsxt_available: bool,
        ensan_available: bool,
        handaas_available: bool = False,
    ) -> RouteDecision:
        if task.force_channel:
            tier = SourceTier.L2 if task.force_channel == ChannelKind.ENSCAN_GO else SourceTier.L1
            dim = task.dimensions[0] if task.dimensions else Dimension.REGISTRY
            return RouteDecision(channel=task.force_channel, source_tier=tier, dimension=dim)

        dim = task.primary_dimension
        tier = task.prefer_tier or SourceTier.L1

        if tier == SourceTier.L3:
            return RouteDecision(
                channel=ChannelKind.ACADEMIC_L3,
                source_tier=SourceTier.L3,
                dimension=dim,
            )

        channel = channel_for(dim, tier, handaas_available=handaas_available)
        if channel == ChannelKind.DEFERRED:
            return RouteDecision(
                channel=ChannelKind.DEFERRED,
                source_tier=SourceTier.L2,
                dimension=dim,
            )
        if channel == ChannelKind.HANDAAS_API:
            if not handaas_available:
                raise RuntimeError(f"Handaas unavailable for dimension {dim.value!r}")
            return RouteDecision(
                channel=ChannelKind.HANDAAS_API,
                source_tier=SourceTier.L2,
                dimension=dim,
            )

        if channel == ChannelKind.GSXT_OFFICIAL:
            if not gsxt_available and not self._config.gsxt_allow_unavailable:
                raise RuntimeError(
                    "GSXT L1 unavailable: no personal session — "
                    "run escout sync-gsxt-session --from-file <cookies.json>"
                )
            return RouteDecision(
                channel=ChannelKind.GSXT_OFFICIAL,
                source_tier=SourceTier.L1,
                dimension=dim,
            )

        if channel == ChannelKind.ENSCAN_GO:
            if not ensan_available:
                raise RuntimeError(f"ENScan L2 unavailable for dimension {dim.value!r}")
            return RouteDecision(
                channel=ChannelKind.ENSCAN_GO,
                source_tier=SourceTier.L2,
                dimension=dim,
            )

        raise RuntimeError(f"no route for dimension={dim.value!r} tier={tier.value!r}")
