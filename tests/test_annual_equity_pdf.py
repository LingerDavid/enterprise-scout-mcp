"""Synthetic page fixtures for annual equity extract (no real PDFs)."""

from __future__ import annotations

from pathlib import Path

import pytest

from enterprise_scout_mcp.output.listed_writer import replace_listed_rows
from enterprise_scout_mcp.sources.annual_equity_pdf import (
    PageContent,
    extract_equity_from_pages,
    period_from_annual_meta,
)

pq = pytest.importorskip("pyarrow.parquet")


def test_period_from_title_and_date() -> None:
    assert period_from_annual_meta(year=2023) == "2023"
    assert period_from_annual_meta(title="公司2024年年度报告") == "2024"
    assert period_from_annual_meta(document_date="2025-03-28") == "2024"
    assert period_from_annual_meta(document_date="2024-08-15") == "2024"


def test_extract_holders_and_subsidiaries_from_pages() -> None:
    holders_table = [
        ["股东名称", "持股数量", "持股比例", "股份性质"],
        ["甲控股集团有限公司", "1000000", "32.50%", "境内法人"],
        ["乙投资有限公司", "500000", "16.25", "境内法人"],
        ["合计", "1500000", "48.75%", ""],
    ]
    sub_table = [
        ["子公司名称", "持股比例", "主营业务"],
        ["丙药业有限公司", "100%", "药品销售"],
        ["丁商贸有限公司", "60%", "批发"],
    ]
    supplier_table = [
        ["供应商名称", "采购金额", "占年度采购总额的比例"],
        ["戊原料有限公司", "120000000", "18.50%"],
        ["己包装有限公司", "80000000", "12.30"],
        ["合计", "200000000", "30.80%"],
    ]
    invest_table = [
        ["被投资单位", "持股比例", "主营业务"],
        ["庚联营有限公司", "30%", "医药流通"],
        ["辛合营有限公司", "49%", "研发"],
    ]
    pages = [
        PageContent(
            index=10,
            text="第五节 前十名股东持股情况\n单位：股",
            tables=[holders_table],
        ),
        PageContent(
            index=40,
            text="重要子公司情况\n纳入合并范围的子公司如下",
            tables=[sub_table],
        ),
        PageContent(
            index=55,
            text="向前五名供应商合计采购金额情况\n主要供应商",
            tables=[supplier_table],
        ),
        PageContent(
            index=60,
            text="对外股权投资情况\n重要的联营企业",
            tables=[invest_table],
        ),
        PageContent(
            index=12,
            text="实际控制人情况说明：甲控股集团有限公司直接持有本公司32.50%。"
            "实际控制人为国务院国资委。",
            tables=[],
        ),
    ]
    result = extract_equity_from_pages(
        pages,
        security_id="SSE:600085",
        issuer_id="91110000DEMO",
        document_id="cninfo:demo",
        period="2024",
        as_of="2025-03-28",
        collected_at="2026-01-01T00:00:00+00:00",
        issuer_name="北京同仁堂股份有限公司",
    )
    assert len(result.holders) == 2
    assert result.holders[0]["holder_name"] == "甲控股集团有限公司"
    assert float(result.holders[0]["pct_total"]) == pytest.approx(32.5)
    assert len(result.subsidiaries) == 2
    assert result.subsidiaries[0]["consolidated"] == "true"
    assert len(result.suppliers) == 2
    assert result.suppliers[0]["name"] == "戊原料有限公司"
    assert float(result.suppliers[0]["purchase_pct"]) == pytest.approx(18.5)
    assert len(result.investments) == 2
    assert result.investments[0]["name"] == "庚联营有限公司"
    assert result.listed_control
    assert result.listed_control[0]["endpoint_type"] == "state"


def test_extract_holders_cross_page_continuation() -> None:
    """Header on page N, data rows on page N+1 (cninfo layout)."""
    header_page = PageContent(
        index=68,
        text="前十名股东持股情况（不含通过转融通出借股份）",
        tables=[
            [
                ["股东名称（全称）", "报告期内增减", "期末持股数量", "比例(%)", "股东性质"],
            ]
        ],
    )
    # Header-only table has len 1 — picker requires len>=2; use a stub second row.
    header_page.tables[0].append(["", "", "", "", ""])
    data_page = PageContent(
        index=69,
        text="有限售条件股份数量",
        tables=[
            [
                ["中国北京同仁堂(集团)有限责任公司", "0", "719308540", "52.45", "国有法人"],
                ["中国证券金融股份有限公司", "0", "41033808", "2.99", "未知"],
                ["香港中央结算有限公司", "4521522", "28484677", "2.08", "境外法人"],
            ]
        ],
    )
    result = extract_equity_from_pages(
        [header_page, data_page],
        security_id="SSE:600085",
        issuer_id="91110000DEMO",
        document_id="cninfo:demo",
        period="2024",
        as_of="2025-04-04",
    )
    assert len(result.holders) == 3
    assert result.holders[0]["holder_name"].startswith("中国北京同仁堂")
    assert float(result.holders[0]["pct_total"]) == pytest.approx(52.45)
    assert float(result.holders[2]["pct_total"]) == pytest.approx(2.08)


def test_replace_holders_is_idempotent(tmp_path: Path) -> None:
    warehouse = tmp_path / "warehouse"
    rows = [
        {
            "security_id": "SSE:600085",
            "as_of": "2024-12-31",
            "rank": "1",
            "holder_name": "甲",
            "pct_total": "30",
            "document_id": "cninfo:1",
            "collected_at": "t1",
        },
        {
            "security_id": "SSE:600085",
            "as_of": "2024-12-31",
            "rank": "2",
            "holder_name": "乙",
            "pct_total": "10",
            "document_id": "cninfo:1",
            "collected_at": "t1",
        },
    ]
    replace_listed_rows(warehouse, "holders", rows, match_keys=("security_id", "as_of"))
    replace_listed_rows(warehouse, "holders", rows, match_keys=("security_id", "as_of"))
    path = warehouse / "listed" / "holders" / "part.parquet"
    assert pq.read_table(path).num_rows == 2


def test_extract_invest_from_investee_header() -> None:
    """长期股权投资 note: 被投资单位 column, section labels ignored."""
    invest_table = [
        ["被投资单位", "期初余额", "期末余额"],
        ["一、合营企业", "", ""],
        ["耀达企业管理有限公司", "7686110.07", "6091424.06"],
        ["二、联营企业", "", ""],
        ["同仁堂科技发展股份有限公司", "2134500.00", "2134500.00"],
    ]
    named_stake = [
        ["公司名称", "主要业务", "投资比例"],
        ["庚联营医药有限公司", "医药流通", "30%"],
    ]
    pages = [
        PageContent(
            index=150,
            text="17、长期股权投资\n(1).长期股权投资情况",
            tables=[invest_table],
        ),
        PageContent(
            index=28,
            text="对外股权投资情况\n重要的联营企业",
            tables=[named_stake],
        ),
    ]
    result = extract_equity_from_pages(
        pages,
        security_id="SSE:600085",
        issuer_id="91110000DEMO",
        document_id="cninfo:demo",
        period="2024",
        as_of="2025-03-28",
    )
    names = {r["name"] for r in result.investments}
    assert "耀达企业管理有限公司" in names
    assert "同仁堂科技发展股份有限公司" in names
    assert "庚联营医药有限公司" in names
    assert "一、合营企业" not in names


def test_edges_from_suppliers_and_invest() -> None:
    from enterprise_scout_mcp.integrations.listed_equity_extract import (
        edges_from_equity_extract,
    )
    from enterprise_scout_mcp.sources.annual_equity_pdf import EquityExtractResult

    result = EquityExtractResult(
        holders=[{"holder_name": "甲控股", "pct_total": "40"}],
        subsidiaries=[{"name": "子A", "direct_pct": "100"}],
        investments=[{"name": "参股B", "direct_pct": "30"}],
        suppliers=[{"name": "供C", "purchase_pct": "15"}],
    )
    edges = edges_from_equity_extract(
        result,
        issuer_name="上市母公司",
        credit_code="91110000DEMO",
        collected_at="2026-01-01T00:00:00+00:00",
    )
    by_rel = {e["relation"]: [] for e in edges}
    for e in edges:
        by_rel[e["relation"]].append(e)
    assert len(by_rel["holder"]) == 1
    assert by_rel["holder"][0]["src_name"] == "甲控股"
    assert by_rel["holder"][0]["dst_name"] == "上市母公司"
    invest_dst = {e["dst_name"] for e in by_rel["invest"]}
    assert invest_dst == {"子A", "参股B"}
    assert len(by_rel["supply"]) == 1
    assert by_rel["supply"][0]["dst_name"] == "供C"
    assert by_rel["supply"][0]["src_name"] == "上市母公司"
    assert all(e["source_channel"] == "annual_pdf" for e in edges)


def test_replace_annual_edges_is_idempotent(tmp_path: Path) -> None:
    from enterprise_scout_mcp.integrations.listed_equity_extract import (
        upsert_annual_edges_to_warehouse,
    )
    from enterprise_scout_mcp.output.edge_schema import edge_row

    warehouse = tmp_path / "warehouse"
    edges = [
        edge_row(
            src_name="上市母公司",
            dst_name="供C",
            relation="supply",
            ratio="15%",
            section="suppliers",
            platform="cninfo",
            source_channel="annual_pdf",
            query_keyword="上市母公司",
            collected_at="t1",
            payload_json="{}",
        ),
        edge_row(
            src_name="上市母公司",
            dst_name="参股B",
            relation="invest",
            ratio="30%",
            section="investments",
            platform="cninfo",
            source_channel="annual_pdf",
            query_keyword="上市母公司",
            collected_at="t1",
            payload_json="{}",
        ),
    ]
    upsert_annual_edges_to_warehouse(warehouse, issuer_name="上市母公司", edges=edges)
    upsert_annual_edges_to_warehouse(warehouse, issuer_name="上市母公司", edges=edges)
    path = warehouse / "edges" / "equity" / "part.parquet"
    assert pq.read_table(path).num_rows == 2
    # Other issuer / channel must survive replace.
    other = [
        edge_row(
            src_name="OtherCo",
            dst_name="Child",
            relation="invest",
            ratio="10%",
            section="invest",
            platform="aiqicha",
            source_channel="enscan_go",
            query_keyword="OtherCo",
            collected_at="t0",
            payload_json="{}",
        )
    ]
    from enterprise_scout_mcp.output.edge_writer import merge_edge_rows

    merge_edge_rows(warehouse, other)
    upsert_annual_edges_to_warehouse(
        warehouse,
        issuer_name="上市母公司",
        edges=edges[:1],
    )
    rows = pq.read_table(path).to_pylist()
    assert any(r["query_keyword"] == "OtherCo" for r in rows)
    annual = [r for r in rows if r.get("source_channel") == "annual_pdf"]
    assert len(annual) == 1
    assert annual[0]["dst_name"] == "供C"
