"""L1 GSXT fail → L2 ENScan degraded fallback."""

from __future__ import annotations

from unittest.mock import patch

from enterprise_scout_mcp.config import AppConfig, RoutingConfig
from enterprise_scout_mcp.models import (
    ChannelKind,
    CollectResult,
    CollectTask,
    Dimension,
    Platform,
    ResultGrade,
    SourceTier,
)
from enterprise_scout_mcp.scheduler import CollectorScheduler


def test_l1_auth_expired_falls_back_to_l2_degraded() -> None:
    config = AppConfig(routing=RoutingConfig(l1_fallback_to_l2=True))
    scheduler = CollectorScheduler(config)
    task = CollectTask(
        keyword="苏州挚途",
        platform=Platform.GSXT,
        dimensions=(Dimension.REGISTRY,),
        prefer_tier=SourceTier.L1,
        fields=("enterprise_info",),
    )
    try:
        gsxt = scheduler._channels[ChannelKind.GSXT_OFFICIAL]
        ensan = scheduler._channels[ChannelKind.ENSCAN_GO]
        with patch.object(gsxt, "available", return_value=True), \
             patch.object(ensan, "available", return_value=True), \
             patch.object(gsxt, "collect") as mock_l1, \
             patch.object(ensan, "collect") as mock_l2, \
             patch.object(scheduler._output, "persist"), \
             patch.object(scheduler._behavior, "wait_before_request"), \
             patch.object(scheduler._behavior, "can_proceed", return_value=(True, "")):
            mock_l1.return_value = CollectResult(
                task=task,
                channel=ChannelKind.GSXT_OFFICIAL,
                grade=ResultGrade.AUTH_EXPIRED,
                message="session missing",
                source_tier=SourceTier.L1,
            )
            mock_l2.return_value = CollectResult(
                task=task,
                channel=ChannelKind.ENSCAN_GO,
                grade=ResultGrade.OK,
                data={"enterprise_info": [{"name": "苏州挚途科技有限公司", "pid": "p1"}]},
                message="ok",
            )
            result = scheduler.run(task, import_neo4j=False)
        assert result.grade == ResultGrade.OK
        assert result.degraded is True
        assert result.channel == ChannelKind.ENSCAN_GO
        assert result.source_tier == SourceTier.L2
        assert "L1→L2 fallback" in result.message
        mock_l2.assert_called_once()
    finally:
        scheduler.close()


def test_l1_ok_skips_l2_fallback() -> None:
    config = AppConfig(routing=RoutingConfig(l1_fallback_to_l2=True))
    scheduler = CollectorScheduler(config)
    task = CollectTask(
        keyword="苏州挚途",
        platform=Platform.GSXT,
        dimensions=(Dimension.REGISTRY,),
        prefer_tier=SourceTier.L1,
    )
    try:
        gsxt = scheduler._channels[ChannelKind.GSXT_OFFICIAL]
        ensan = scheduler._channels[ChannelKind.ENSCAN_GO]
        with patch.object(gsxt, "available", return_value=True), \
             patch.object(ensan, "available", return_value=True), \
             patch.object(gsxt, "collect") as mock_l1, \
             patch.object(ensan, "collect") as mock_l2, \
             patch.object(scheduler._output, "persist"), \
             patch.object(scheduler._behavior, "wait_before_request"), \
             patch.object(scheduler._behavior, "can_proceed", return_value=(True, "")):
            mock_l1.return_value = CollectResult(
                task=task,
                channel=ChannelKind.GSXT_OFFICIAL,
                grade=ResultGrade.OK,
                data={"enterprise_info": [{"name": "苏州挚途", "credit_code": "91320594MA1"}]},
                source_tier=SourceTier.L1,
            )
            result = scheduler.run(task, import_neo4j=False)
        assert result.grade == ResultGrade.OK
        assert result.degraded is False
        mock_l2.assert_not_called()
    finally:
        scheduler.close()


def test_l1_partial_with_conflict_persists_conflicts() -> None:
    config = AppConfig(routing=RoutingConfig(l1_fallback_to_l2=True))
    scheduler = CollectorScheduler(config)
    task = CollectTask(
        keyword="苏州挚途",
        platform=Platform.GSXT,
        dimensions=(Dimension.REGISTRY,),
        prefer_tier=SourceTier.L1,
    )
    try:
        gsxt = scheduler._channels[ChannelKind.GSXT_OFFICIAL]
        ensan = scheduler._channels[ChannelKind.ENSCAN_GO]
        with patch.object(gsxt, "available", return_value=True), \
             patch.object(ensan, "available", return_value=True), \
             patch.object(gsxt, "collect") as mock_l1, \
             patch.object(ensan, "collect") as mock_l2, \
             patch.object(scheduler._output, "persist"), \
             patch.object(scheduler._output, "persist_conflicts") as mock_conflicts, \
             patch.object(scheduler._behavior, "wait_before_request"), \
             patch.object(scheduler._behavior, "can_proceed", return_value=(True, "")):
            mock_l1.return_value = CollectResult(
                task=task,
                channel=ChannelKind.GSXT_OFFICIAL,
                grade=ResultGrade.PARTIAL,
                data={"enterprise_info": [{"name": "A", "credit_code": "111"}]},
            )
            mock_l2.return_value = CollectResult(
                task=task,
                channel=ChannelKind.ENSCAN_GO,
                grade=ResultGrade.OK,
                data={"enterprise_info": [{"name": "B", "credit_code": "222"}]},
            )
            scheduler.run(task, import_neo4j=False)
        mock_conflicts.assert_called_once()
        rows = mock_conflicts.call_args[0][0]
        fields = {r["field"] for r in rows}
        assert "credit_code" in fields
        assert "name" in fields
    finally:
        scheduler.close()
