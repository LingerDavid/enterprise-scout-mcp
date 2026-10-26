"""East Money 主营构成 → segments rows."""

from __future__ import annotations

from enterprise_scout_mcp.sources.eastmoney_segments import (
    _pick_latest_period,
    zygcfx_to_segment_rows,
)


def test_zygcfx_to_segment_rows_maps_kind_and_amounts() -> None:
    payload = [
        {
            "REPORT_DATE": "2024-12-31 00:00:00",
            "MAINOP_TYPE": "2",
            "ITEM_NAME": "茅台酒",
            "MAIN_BUSINESS_INCOME": 1000,
            "MAIN_BUSINESS_COST": 400,
        },
        {
            "REPORT_DATE": "2023-12-31 00:00:00",
            "MAINOP_TYPE": "2",
            "ITEM_NAME": "旧期",
            "MAIN_BUSINESS_INCOME": 1,
            "MAIN_BUSINESS_COST": 1,
        },
    ]
    rows = zygcfx_to_segment_rows(
        payload,
        issuer_id="91",
        period="2024",
        document_id="doc1",
        collected_at="2026-01-01T00:00:00+00:00",
    )
    assert len(rows) == 1
    assert rows[0]["kind"] == "product"
    assert rows[0]["name"] == "茅台酒"
    assert rows[0]["revenue"] == "1000"


def test_pick_latest_period_prefers_annual() -> None:
    rows = [
        {"REPORT_DATE": "2025-06-30 00:00:00"},
        {"REPORT_DATE": "2024-12-31 00:00:00"},
    ]
    assert _pick_latest_period(rows) == "2024"
