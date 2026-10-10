"""Multi-dimension collect merge (no live network)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from enterprise_scout_mcp.config import AppConfig
from enterprise_scout_mcp.models import (
    ChannelKind,
    CollectResult,
    CollectTask,
    Dimension,
    Platform,
    ResultGrade,
)
from enterprise_scout_mcp.scheduler import CollectorScheduler


def _result(dim: Dimension, grade: ResultGrade, data: dict, msg: str = "") -> CollectResult:
    return CollectResult(
        task=CollectTask(keyword="测试", platform=Platform.GSXT, dimensions=(dim,)),
        channel=ChannelKind.DEFERRED if dim == Dimension.CREDIT else ChannelKind.ENSCAN_GO,
        grade=grade,
        data=data,
        message=msg,
        dimension=dim,
    )


def test_merge_multi_dimension_stub_and_ok():
    scheduler = CollectorScheduler(AppConfig())
    try:
        with patch.object(scheduler, "_run_single") as run_single:
            run_single.side_effect = [
                _result(Dimension.REGISTRY, ResultGrade.OK, {"enterprise_info": [{"name": "A"}]}),
                _result(Dimension.CREDIT, ResultGrade.PARTIAL, {"stub": True}, "credit deferred"),
            ]
            task = CollectTask(
                keyword="测试",
                platform=Platform.GSXT,
                dimensions=(Dimension.REGISTRY, Dimension.CREDIT),
                prefer_tier=None,
            )
            merged = scheduler.run(task, import_neo4j=False)
        assert merged.grade == ResultGrade.PARTIAL
        assert "enterprise_info" in merged.data
        assert merged.data.get("stub") is True
        assert run_single.call_count == 2
    finally:
        scheduler.close()
