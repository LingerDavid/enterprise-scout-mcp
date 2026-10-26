"""F10 executives payload → warehouse rows."""

from __future__ import annotations

from enterprise_scout_mcp.sources.eastmoney_executives import executives_from_f10_payload


def test_executives_from_f10_payload() -> None:
    payload = {
        "gglb": [
            {
                "PERSON_NAME": "张三",
                "POSITION": "董事长",
                "SEX": "男",
                "AGE": 52,
                "HIGH_DEGREE": "硕士",
                "SALARY": 1200000,
                "HOLD_NUM": 10000,
            }
        ]
    }
    rows = executives_from_f10_payload(payload, security_id="SZSE:002271", collected_at="t0")
    assert len(rows) == 1
    assert rows[0]["person_name"] == "张三"
    assert rows[0]["position"] == "董事长"
    assert rows[0]["salary"] == "1200000"
