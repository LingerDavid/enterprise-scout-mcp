"""F10 structure probe and new tab collectors."""

from __future__ import annotations

from enterprise_scout_mcp.sources.eastmoney_f10_probe import summarize_page_ajax_payload
from enterprise_scout_mcp.sources.eastmoney_holder_stats import holder_stats_from_f10_payload
from enterprise_scout_mcp.sources.eastmoney_ipo_profile import ipo_profile_from_f10_payload


def test_summarize_page_ajax_payload() -> None:
    summary = summarize_page_ajax_payload(
        {
            "sdgd": [{"HOLDER_NAME": "A", "HOLD_NUM": 1}],
            "sjkzr": {"HOLDER_NAME": "B"},
            "sdgd_date": [],
        }
    )
    assert summary["top_level_keys"] == ["sdgd", "sdgd_date", "sjkzr"]
    assert summary["blocks"]["sdgd"]["count"] == 1
    assert "HOLDER_NAME" in summary["blocks"]["sdgd"]["samples"][0]["fields"]


def test_holder_stats_from_gdrs() -> None:
    rows = holder_stats_from_f10_payload(
        {
            "gdrs": [
                {
                    "END_DATE": "2025-12-31",
                    "HOLDER_TOTAL_NUM": 120000,
                    "TOTAL_NUM_RATIO": 1.5,
                    "AVG_FREE_SHARES": 1000,
                    "AVG_HOLD_AMT": 50000,
                }
            ]
        },
        security_id="SZSE:002271",
        collected_at="t0",
    )
    assert len(rows) == 1
    assert rows[0]["holder_count"] == "120000"
    assert rows[0]["as_of"] == "2025-12-31"


def test_ipo_profile_from_fxxg() -> None:
    rows = ipo_profile_from_f10_payload(
        {
            "fxxg": [
                {
                    "FOUND_DATE": "1998-01-01",
                    "LISTING_DATE": "2008-09-10",
                    "ISSUE_PRICE": 17.33,
                    "TOTAL_ISSUE_NUM": 132000000,
                    "PAR_VALUE": 1,
                    "ISSUE_WAY": "网下询价",
                }
            ]
        },
        security_id="SZSE:002271",
        collected_at="t0",
    )
    assert len(rows) == 1
    assert rows[0]["listing_date"] == "2008-09-10"
    assert rows[0]["issue_price"] == "17.33"
