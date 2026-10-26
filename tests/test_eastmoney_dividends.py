"""F10 dividend payload → warehouse rows."""

from __future__ import annotations

from enterprise_scout_mcp.sources.eastmoney_dividends import dividends_from_f10_payload


def test_dividends_from_f10_payload() -> None:
    payload = {
        "fhyx": [
            {
                "NOTICE_DATE": "2024-04-20 00:00:00",
                "EX_DIVIDEND_DATE": "2024-04-25 00:00:00",
                "PAY_CASH_DATE": "2024-04-25 00:00:00",
                "EQUITY_RECORD_DATE": "2024-04-24 00:00:00",
                "ASSIGN_PROGRESS": "实施",
                "IMPL_PLAN_PROFILE": "10派5元",
            }
        ]
    }
    rows = dividends_from_f10_payload(payload, security_id="SZSE:002271", collected_at="t0")
    assert len(rows) == 1
    assert rows[0]["notice_date"] == "2024-04-20"
    assert rows[0]["impl_plan"] == "10派5元"
