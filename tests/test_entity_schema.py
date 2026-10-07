"""EnterpriseLake entity row normalization."""

from __future__ import annotations

from enterprise_scout_mcp.models import ChannelKind, CollectResult, CollectTask, Platform, ResultGrade
from enterprise_scout_mcp.output.entity_schema import entity_row


def test_entity_row_maps_aiqicha_fields() -> None:
    task = CollectTask(keyword="小米", platform=Platform.AIQICHA)
    result = CollectResult(
        task=task,
        channel=ChannelKind.PLAYWRIGHT,
        grade=ResultGrade.OK,
        data={"aiqicha_id": "42", "company_name": "小米科技", "former_name": "北京小米"},
        persona_id="desktop_chrome_cn",
    )
    row = entity_row(result)
    assert row["entity_id"] == "42"
    assert row["name"] == "小米科技"
    assert row["former_name"] == "北京小米"
    assert row["platform"] == "aiqicha"
    assert row["query_keyword"] == "小米"
