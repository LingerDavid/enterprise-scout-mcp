"""Local equity tree BFS + expand (aqc-only)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from enterprise_scout_mcp.models import (
    ChannelKind,
    CollectResult,
    CollectTask,
    Platform,
    ResultGrade,
)
from enterprise_scout_mcp.output.edge_writer import append_edges
from enterprise_scout_mcp.warehouse.equity_expand import assert_aqc_platform, expand_equity_tree
from enterprise_scout_mcp.warehouse.equity_tree import (
    build_equity_tree,
    looks_like_corporation,
    normalize_name,
    resolve_center_name,
)

pa = pytest.importorskip("pyarrow")
pq = pytest.importorskip("pyarrow.parquet")


def _seed(wh: Path, keyword: str, data: dict) -> None:
    task = CollectTask(keyword=keyword, platform=Platform.AIQICHA)
    result = CollectResult(
        task=task,
        channel=ChannelKind.ENSCAN_GO,
        grade=ResultGrade.OK,
        data=data,
        persona_id="t",
    )
    assert append_edges(result, wh) is not None


def test_looks_like_corporation() -> None:
    assert looks_like_corporation("贵州茅台酒股份有限公司")
    assert not looks_like_corporation("张三")


def test_build_equity_tree_bidirectional(tmp_path: Path) -> None:
    wh = tmp_path
    _seed(
        wh,
        "RootCo",
        {
            "partner": [{"name": "母公司控股有限公司", "scale": "40%"}],
            "invest": [{"name": "SubCo有限公司", "持股比例": "51%"}],
            "branch": [{"name": "RootCo北京分公司"}],
        },
    )
    tree = build_equity_tree(wh, "RootCo", max_depth=2, min_ratio=0)
    assert tree["resolved_name"] == "RootCo"
    names = {n["name"] for n in tree["nodes"]}
    assert "母公司控股有限公司" in names
    assert "SubCo有限公司" in names
    assert "RootCo北京分公司" in names
    # branch not in missing; SubCo is missing (never collected as keyword)
    assert "SubCo有限公司" in tree["missing_neighbors"]
    assert "RootCo北京分公司" not in tree["missing_neighbors"]


def test_min_ratio_filters_invest(tmp_path: Path) -> None:
    wh = tmp_path
    _seed(
        wh,
        "RootCo",
        {
            "invest": [
                {"name": "BigSub有限公司", "持股比例": "51%"},
                {"name": "TinySub有限公司", "持股比例": "5%"},
            ],
        },
    )
    tree = build_equity_tree(wh, "RootCo", max_depth=1, min_ratio=20)
    names = {n["name"] for n in tree["nodes"]}
    assert "BigSub有限公司" in names
    assert "TinySub有限公司" not in names


def test_resolve_center_prefers_query_keyword(tmp_path: Path) -> None:
    wh = tmp_path
    _seed(wh, "贵州茅台酒股份有限公司", {"invest": [{"name": "销售公司有限公司", "ratio": "100%"}]})
    rows = pq.read_table(wh / "edges" / "equity" / "part.parquet").to_pylist()
    resolved = resolve_center_name(rows, "贵州茅台酒股份有限公司")
    assert resolved == "贵州茅台酒股份有限公司"
    assert normalize_name(resolved) == normalize_name("贵州茅台酒股份有限公司")


def test_dedupe_on_append(tmp_path: Path) -> None:
    wh = tmp_path
    _seed(wh, "RootCo", {"invest": [{"name": "Sub有限公司", "ratio": "10%"}]})
    _seed(wh, "RootCo", {"invest": [{"name": "Sub有限公司", "ratio": "12%"}]})
    rows = pq.read_table(wh / "edges" / "equity" / "part.parquet").to_pylist()
    invest = [r for r in rows if r["relation"] == "invest" and r["dst_name"] == "Sub有限公司"]
    assert len(invest) == 1
    assert invest[0]["ratio"] == "12%"


def test_expand_refuses_tyc() -> None:
    with pytest.raises(ValueError, match="tianyancha"):
        assert_aqc_platform("tianyancha")
    with pytest.raises(ValueError, match="tianyancha"):
        assert_aqc_platform("tyc")
    assert assert_aqc_platform("aiqicha") is Platform.AIQICHA


def test_expand_collects_missing(tmp_path: Path) -> None:
    wh = tmp_path
    _seed(
        wh,
        "RootCo",
        {"invest": [{"name": "ChildCo有限公司", "持股比例": "60%"}]},
    )

    calls: list[str] = []

    def fake_collect(task: CollectTask) -> CollectResult:
        calls.append(task.keyword)
        assert task.platform is Platform.AIQICHA
        assert task.depth == 1
        # child collect adds another investee so tree grows
        return CollectResult(
            task=task,
            channel=ChannelKind.ENSCAN_GO,
            grade=ResultGrade.OK,
            data={"invest": [{"name": "GrandCo有限公司", "持股比例": "80%"}]},
            persona_id="t",
        )

    # wrap to also append edges like real pipeline
    from enterprise_scout_mcp.output.edge_writer import append_edges as _ae

    def collect_and_write(task: CollectTask) -> CollectResult:
        result = fake_collect(task)
        _ae(result, wh)
        return result

    out = expand_equity_tree(
        wh,
        "RootCo",
        collect_fn=collect_and_write,
        max_depth=2,
        min_ratio=20,
        max_collects=5,
    )
    assert out["ok"] is True
    assert "ChildCo有限公司" in out["collected"]
    assert calls
    names = {n["name"] for n in out["tree"]["nodes"]}
    assert "GrandCo有限公司" in names or "ChildCo有限公司" in names


def test_expand_skips_natural_person(tmp_path: Path) -> None:
    wh = tmp_path
    _seed(
        wh,
        "RootCo",
        {"partner": [{"name": "李四", "scale": "30%"}]},
    )
    calls: list[str] = []

    def fake(task: CollectTask) -> CollectResult:
        calls.append(task.keyword)
        return CollectResult(
            task=task,
            channel=ChannelKind.ENSCAN_GO,
            grade=ResultGrade.OK,
            data={},
            persona_id="t",
        )

    out = expand_equity_tree(
        wh,
        "RootCo",
        collect_fn=fake,
        max_depth=2,
        min_ratio=0,
        max_collects=5,
    )
    assert out["collected"] == []
    assert calls == []
    assert "李四" not in out["tree"]["missing_neighbors"]


def test_supplier_edge_optional(tmp_path: Path) -> None:
    wh = tmp_path
    _seed(
        wh,
        "RootCo",
        {"supplier": [{"name": "供应有限公司", "ratio": ""}]},
    )
    bare = build_equity_tree(wh, "RootCo", include_supply=False)
    assert not any(n["role"] == "supplier" for n in bare["nodes"])
    with_s = build_equity_tree(wh, "RootCo", include_supply=True)
    assert any(n.get("role") == "supplier" for n in with_s["nodes"])
