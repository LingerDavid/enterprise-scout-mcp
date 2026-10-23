"""Cninfo announcement index helpers (no live network)."""

from __future__ import annotations

from enterprise_scout_mcp.sources.cninfo import (
    CninfoAnnouncement,
    announcement_query_form,
    org_id_from_catalog,
    pick_annual_report,
    pick_prospectus,
    resolve_listing,
)


def test_resolve_listing() -> None:
    assert resolve_listing("600519.SH") == ("SSE:600519", "600519", "sse")
    assert resolve_listing("SSE:600519") == ("SSE:600519", "600519", "sse")
    assert resolve_listing("000001.SZ") == ("SZSE:000001", "000001", "szse")
    assert resolve_listing("bad") is None


def test_org_id_and_query_stock_field() -> None:
    org = org_id_from_catalog(
        {"stockList": [{"code": "600519", "orgId": "gssh0600519"}]},
        "600519",
    )
    assert org == "gssh0600519"
    form = announcement_query_form(
        code="600519",
        org_id=org,
        column="sse",
        category="category_ndbg_szsh",
        page_num=1,
        page_size=10,
        se_date="",
    )
    assert form["stock"] == "600519,gssh0600519"
    assert form["category"].endswith(";")


def test_pick_annual_skips_english_and_abstract() -> None:
    anns = [
        CninfoAnnouncement(
            announcement_id="en",
            title="2025年年度报告（英文版）",
            adjunct_url="en.pdf",
            announce_time_ms=300,
            security_id="SSE:600519",
            code="600519",
        ),
        CninfoAnnouncement(
            announcement_id="zh",
            title="贵州茅台2025年年度报告",
            adjunct_url="zh.pdf",
            announce_time_ms=200,
            security_id="SSE:600519",
            code="600519",
        ),
    ]
    picked = pick_annual_report(anns, year=2025)
    assert picked is not None
    assert picked.announcement_id == "zh"


def test_pick_annual_prefers_full_report() -> None:
    anns = [
        CninfoAnnouncement(
            announcement_id="1",
            title="2024年年度报告摘要",
            adjunct_url="a.pdf",
            announce_time_ms=100,
            security_id="SSE:600519",
            code="600519",
        ),
        CninfoAnnouncement(
            announcement_id="2",
            title="2024年年度报告",
            adjunct_url="b.pdf",
            announce_time_ms=200,
            security_id="SSE:600519",
            code="600519",
        ),
    ]
    picked = pick_annual_report(anns, year=2024)
    assert picked is not None
    assert picked.announcement_id == "2"
    assert picked.document_id == "cninfo:2"
    assert picked.pdf_url.endswith("b.pdf")


def test_pick_prospectus_skips_abstract_and_opinion() -> None:
    anns = [
        CninfoAnnouncement(
            announcement_id="abs",
            title="首次公开发行股票招股说明书摘要",
            adjunct_url="a.pdf",
            announce_time_ms=300,
            security_id="SZSE:301000",
            code="301000",
        ),
        CninfoAnnouncement(
            announcement_id="op",
            title="招股说明书的确认意见",
            adjunct_url="b.pdf",
            announce_time_ms=200,
            security_id="SZSE:301000",
            code="301000",
        ),
        CninfoAnnouncement(
            announcement_id="draft",
            title="首次公开发行股票并在创业板上市招股说明书注册稿",
            adjunct_url="d.pdf",
            announce_time_ms=250,
            security_id="SZSE:301000",
            code="301000",
        ),
        CninfoAnnouncement(
            announcement_id="full",
            title="首次公开发行股票并在创业板上市招股说明书",
            adjunct_url="c.pdf",
            announce_time_ms=100,
            security_id="SZSE:301000",
            code="301000",
        ),
    ]
    picked = pick_prospectus(anns)
    assert picked is not None
    assert picked.announcement_id == "full"
