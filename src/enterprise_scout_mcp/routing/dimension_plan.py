"""Dimension → fields / tier / channel policy (architecture §执行采集)."""

from __future__ import annotations

from enterprise_scout_mcp.defaults import DEFAULT_REGISTRY_FIELDS
from enterprise_scout_mcp.models import ChannelKind, CollectTask, Dimension, SourceTier

# ENScan section keys per dimension (see ENSMapLN / ENScan_GO common/config.go).
DIMENSION_FIELDS: dict[Dimension, tuple[str, ...]] = {
    Dimension.REGISTRY: ("enterprise_info",),
    Dimension.EQUITY: ("partner", "holds", "invest", "branch"),
    Dimension.DIGITAL: ("icp", "app", "wechat", "wx_app", "weibo"),
    Dimension.IP: ("icp",),
    Dimension.CREDIT: (),
    Dimension.JUDICIAL: (),
}

_STUB_DIMENSIONS = frozenset({Dimension.CREDIT, Dimension.JUDICIAL})


def resolve_fields(task: CollectTask, dimension: Dimension) -> tuple[str, ...]:
    """Merge task.fields with dimension defaults (deduped, order preserved)."""
    base = task.fields if task.fields != DEFAULT_REGISTRY_FIELDS else ()
    defaults = DIMENSION_FIELDS.get(dimension, ())
    seen: set[str] = set()
    out: list[str] = []
    for key in (*base, *defaults):
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return tuple(out) if out else DEFAULT_REGISTRY_FIELDS


def is_stub_dimension(dimension: Dimension) -> bool:
    return dimension in _STUB_DIMENSIONS


def channel_for(
    dimension: Dimension,
    tier: SourceTier,
    *,
    handaas_available: bool = False,
) -> ChannelKind:
    if tier == SourceTier.L3:
        return ChannelKind.ACADEMIC_L3
    if is_stub_dimension(dimension):
        if handaas_available and dimension == Dimension.CREDIT:
            return ChannelKind.HANDAAS_API
        return ChannelKind.DEFERRED
    if dimension == Dimension.REGISTRY and tier == SourceTier.L1:
        return ChannelKind.GSXT_OFFICIAL
    return ChannelKind.ENSCAN_GO
