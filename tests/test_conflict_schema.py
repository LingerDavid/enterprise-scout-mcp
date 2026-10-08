"""L1/L2 registry conflict detection."""

from __future__ import annotations

from enterprise_scout_mcp.models import (
    ChannelKind,
    CollectResult,
    CollectTask,
    Platform,
    ResultGrade,
    SourceTier,
)
from enterprise_scout_mcp.output.conflict_schema import detect_registry_conflicts


def _l1(**info) -> CollectResult:
    return CollectResult(
        task=CollectTask(keyword="苏州挚途", platform=Platform.GSXT),
        channel=ChannelKind.GSXT_OFFICIAL,
        grade=ResultGrade.PARTIAL,
        data={"enterprise_info": [info]},
        source_tier=SourceTier.L1,
    )


def _l2(**info) -> CollectResult:
    return CollectResult(
        task=CollectTask(keyword="苏州挚途", platform=Platform.GSXT),
        channel=ChannelKind.ENSCAN_GO,
        grade=ResultGrade.OK,
        data={"enterprise_info": [info]},
        source_tier=SourceTier.L2,
        degraded=True,
    )


def test_no_conflict_when_l1_empty() -> None:
    l1 = CollectResult(
        task=CollectTask(keyword="x", platform=Platform.GSXT),
        channel=ChannelKind.GSXT_OFFICIAL,
        grade=ResultGrade.AUTH_EXPIRED,
        data={},
    )
    l2 = _l2(name="苏州挚途科技有限公司", credit_code="91320594MA1XXXXXX")
    assert detect_registry_conflicts(l1, l2) == []


def test_conflict_on_credit_code_mismatch() -> None:
    rows = detect_registry_conflicts(
        _l1(name="苏州挚途科技有限公司", credit_code="91320594MA1AAAAAA"),
        _l2(name="苏州挚途科技有限公司", credit_code="91320594MA1BBBBBB"),
    )
    assert len(rows) == 1
    assert rows[0]["field"] == "credit_code"
    assert rows[0]["l1_value"] == "91320594MA1AAAAAA"
    assert rows[0]["l2_value"] == "91320594MA1BBBBBB"


def test_no_conflict_when_values_match() -> None:
    payload = {"name": "苏州挚途科技有限公司", "credit_code": "91320594MA1XXXXXX"}
    assert detect_registry_conflicts(_l1(**payload), _l2(**payload)) == []
