"""Cninfo announcement index helpers (no live network)."""

from __future__ import annotations

from enterprise_scout_mcp.sources.cninfo import (
    CninfoAnnouncement,
    pick_annual_report,
    resolve_listing,
)


def test_resolve_listing() -> None:
    assert resolve_listing("600519.SH") == ("SSE:600519", "600519", "sse")
    assert resolve_listing("SSE:600519") == ("SSE:600519", "600519", "sse")
    assert resolve_listing("000001.SZ") == ("SZSE:000001", "000001", "szse")
    assert resolve_listing("bad") is None


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
