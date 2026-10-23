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
    assert result.listed_control
    assert result.listed_control[0]["endpoint_type"] == "state"


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
