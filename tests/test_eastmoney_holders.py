"""F10 holders payload → warehouse rows."""

from __future__ import annotations

from enterprise_scout_mcp.sources.eastmoney_holders import holders_from_f10_payload


def test_holders_from_f10_payload() -> None:
    payload = {
        "sdgd": [
            {
                "HOLDER_RANK": 1,
                "HOLDER_NAME": "控股股东",
                "HOLDER_TYPE": "其它",
                "HOLD_NUM": 500000000,
                "HOLD_NUM_RATIO": 54.0,
                "SHARES_TYPE": "流通A股",
                "END_DATE": "2024-12-31",
            },
            {
                "HOLDER_RANK": 2,
                "HOLDER_NAME": "",
                "HOLD_NUM": 1,
                "END_DATE": "2024-12-31",
            },
        ]
    }
    rows = holders_from_f10_payload(
        payload,
        security_id="SSE:600519",
        collected_at="t0",
    )
    assert len(rows) == 1
    assert rows[0]["holder_name"] == "控股股东"
    assert rows[0]["pct_total"] == "54.0"
    assert rows[0]["as_of"] == "2024-12-31"
    assert rows[0]["rank"] == "1"
