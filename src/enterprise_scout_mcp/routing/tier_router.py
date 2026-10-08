"""Tier-aware routing — L1 official > L2 commercial > L3 academic."""

from __future__ import annotations

from dataclasses import dataclass

from enterprise_scout_mcp.config import RoutingConfig
from enterprise_scout_mcp.models import ChannelKind, CollectTask, Dimension, SourceTier


@dataclass(frozen=True)
class RouteDecision:
    channel: ChannelKind
    source_tier: SourceTier
    dimension: Dimension


_IMPLEMENTED: dict[tuple[Dimension, SourceTier], ChannelKind] = {
    (Dimension.REGISTRY, SourceTier.L1): ChannelKind.GSXT_OFFICIAL,
}


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
    ) -> RouteDecision:
        if task.force_channel:
            tier = SourceTier.L2 if task.force_channel == ChannelKind.ENSCAN_GO else SourceTier.L1
            dim = task.dimensions[0] if task.dimensions else Dimension.REGISTRY
            return RouteDecision(channel=task.force_channel, source_tier=tier, dimension=dim)

        dim = task.primary_dimension
        tier = task.prefer_tier or SourceTier.L1

        if dim != Dimension.REGISTRY:
            raise RuntimeError(
                f"dimension {dim.value!r} not implemented yet; only registry L1 spike is available"
            )

        if tier == SourceTier.L1:
            if not gsxt_available and not self._config.gsxt_allow_unavailable:
                raise RuntimeError(
                    "GSXT L1 unavailable: no personal session — "
                    "run escout sync-gsxt-session --from-file <cookies.json>"
                )
            return RouteDecision(
                channel=ChannelKind.GSXT_OFFICIAL,
                source_tier=SourceTier.L1,
                dimension=Dimension.REGISTRY,
            )

        if tier == SourceTier.L2:
            if not ensan_available:
                raise RuntimeError("ENScan L2 unavailable for registry fallback")
            return RouteDecision(
                channel=ChannelKind.ENSCAN_GO,
                source_tier=SourceTier.L2,
                dimension=Dimension.REGISTRY,
            )

        raise RuntimeError(f"source tier {tier.value!r} not implemented for {dim.value!r}")
