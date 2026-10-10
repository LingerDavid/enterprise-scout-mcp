"""Dimension field resolution and channel mapping."""

from __future__ import annotations

from enterprise_scout_mcp.models import ChannelKind, CollectTask, Dimension, Platform, SourceTier
from enterprise_scout_mcp.routing.dimension_plan import channel_for, resolve_fields


def test_resolve_fields_equity_adds_partner_sections():
    task = CollectTask(
        keyword="x",
        platform=Platform.AIQICHA,
        fields=("enterprise_info",),
        dimensions=(Dimension.EQUITY,),
    )
    fields = resolve_fields(task, Dimension.EQUITY)
    assert "enterprise_info" in fields
    assert "partner" in fields
    assert "invest" in fields


def test_channel_for_registry_l1_gsxt():
    assert channel_for(Dimension.REGISTRY, SourceTier.L1) == ChannelKind.GSXT_OFFICIAL


def test_channel_for_equity_l2_enscan():
    assert channel_for(Dimension.EQUITY, SourceTier.L2) == ChannelKind.ENSCAN_GO


def test_channel_for_l3_academic():
    assert channel_for(Dimension.REGISTRY, SourceTier.L3) == ChannelKind.ACADEMIC_L3


def test_channel_for_credit_handaas():
    assert channel_for(Dimension.CREDIT, SourceTier.L2, handaas_available=True) == ChannelKind.HANDAAS_API
    assert channel_for(Dimension.CREDIT, SourceTier.L2, handaas_available=False) == ChannelKind.DEFERRED
