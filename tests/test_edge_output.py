"""Edge extraction and parquet append."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from enterprise_scout_mcp.models import ChannelKind, CollectResult, CollectTask, Platform, ResultGrade
from enterprise_scout_mcp.output.edge_extractor import extract_edges
from enterprise_scout_mcp.output.edge_writer import append_edges


def test_extract_edges_enscan_partner() -> None:
    task = CollectTask(keyword="苏州挚途", platform=Platform.AIQICHA)
    result = CollectResult(
        task=task,
        channel=ChannelKind.ENSCAN_GO,
        grade=ResultGrade.OK,
        data={
            "partner": [
                {"name": "一汽解放汽车有限公司", "scale": "25.29572%"},
                {"name": "苏州智加科技有限公司", "scale": "15.80983%"},
            ],
        },
        persona_id="p1",
    )
    edges = extract_edges(result)
    assert len(edges) == 2
    assert all(e["relation"] == "holder" for e in edges)
    assert edges[0]["src_name"] == "一汽解放汽车有限公司"
    assert edges[0]["dst_name"] == "苏州挚途"
    assert edges[0]["ratio"] == "25.29572%"


def test_extract_edges_holds() -> None:
    task = CollectTask(keyword="RootCo", platform=Platform.AIQICHA)
    result = CollectResult(
        task=task,
        channel=ChannelKind.ENSCAN_GO,
        grade=ResultGrade.OK,
        data={"holds": [{"name": "SubHoldCo", "scale": "80%"}]},
        persona_id="p1",
    )
    edges = extract_edges(result)
    assert len(edges) == 1
    assert edges[0]["relation"] == "invest"
    assert edges[0]["src_name"] == "RootCo"
    assert edges[0]["dst_name"] == "SubHoldCo"
    assert edges[0]["section"] == "holds"
    assert edges[0]["ratio"] == "80%"


def test_extract_edges_invest_and_holder() -> None:
    task = CollectTask(keyword="Acme Corp", platform=Platform.AIQICHA)
    result = CollectResult(
        task=task,
        channel=ChannelKind.ENSCAN_GO,
        grade=ResultGrade.OK,
        data={
            "invest": [{"企业名称": "SubCo", "持股比例": "51%"}],
            "stockholder": [{"股东名称": "BigFund", "投资比例": "30%"}],
        },
        persona_id="p1",
    )
    edges = extract_edges(result)
    assert len(edges) == 2
    invest = next(e for e in edges if e["relation"] == "invest")
    holder = next(e for e in edges if e["relation"] == "holder")
    assert invest["src_name"] == "Acme Corp"
    assert invest["dst_name"] == "SubCo"
    assert invest["ratio"] == "51%"
    assert holder["src_name"] == "BigFund"
    assert holder["dst_name"] == "Acme Corp"


@pytest.mark.skipif(
    importlib.util.find_spec("pyarrow") is None,
    reason="pyarrow not installed",
)
def test_append_edges_parquet(tmp_path: Path) -> None:
    task = CollectTask(keyword="RootCo", platform=Platform.AIQICHA)
    result = CollectResult(
        task=task,
        channel=ChannelKind.ENSCAN_GO,
        grade=ResultGrade.OK,
        data={"invest": [{"name": "ChildCo", "ratio": "10%"}]},
        persona_id="p1",
    )
    path = append_edges(result, tmp_path)
    assert path is not None
    assert path.is_file()
    assert path.parent.name == "equity"
