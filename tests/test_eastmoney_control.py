"""F10 actual controller payload → listed_control rows."""

from __future__ import annotations

from enterprise_scout_mcp.sources.eastmoney_control import control_from_f10_payload


def test_control_from_f10_payload() -> None:
    payload = {
        "sjkzr": [
            {
                "HOLDER_NAME": "李卫国",
                "HOLD_RATIO": 27.5,
            }
        ]
    }
    rows = control_from_f10_payload(payload, issuer_id="91110000123456789X", collected_at="2026-01-01T00:00:00Z")
    assert len(rows) == 1
    assert rows[0]["src_name"] == "李卫国"
    assert rows[0]["ratio"] == "27.5"
    assert rows[0]["hop"] == "0"
