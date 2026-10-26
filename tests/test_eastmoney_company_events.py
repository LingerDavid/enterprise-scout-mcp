"""East Money 公司大事 dstx."""

from __future__ import annotations

from enterprise_scout_mcp.sources.eastmoney_company_events import company_events_from_payload


def test_company_events_from_dstx() -> None:
    payload = {
        "dstx": {
            "success": True,
            "data": [
                [
                    {
                        "EVENT_TYPE": "业绩披露",
                        "SPECIFIC_EVENTTYPE": "季报披露",
                        "NOTICE_DATE": "2026-10-26",
                        "LEVEL1_CONTENT": "净利润6.576亿元",
                        "INFO_CODE": "AN123",
                    }
                ]
            ],
        },
    }
    rows = company_events_from_payload(payload, security_id="SZSE:002271", collected_at="t0")
    assert len(rows) == 1
    assert rows[0]["event_type"] == "业绩披露"
    assert rows[0]["info_code"] == "AN123"
