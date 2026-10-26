"""F10 capital payload → warehouse rows."""

from __future__ import annotations

from enterprise_scout_mcp.sources.eastmoney_capital import capital_from_f10_payload


def test_capital_from_f10_payload() -> None:
    payload = {
        "gbjg": [
            {
                "TOTAL_SHARES": 1000000000,
                "UNLIMITED_SHARES": 600000000,
                "END_DATE": "2024-12-31",
            }
        ]
    }
    rows = capital_from_f10_payload(payload, security_id="SZSE:002271", collected_at="t0")
    assert len(rows) == 1
    assert rows[0]["total_shares"] == "1000000000"
    assert rows[0]["float_shares"] == "600000000"
    assert rows[0]["as_of"] == "2024-12-31"
