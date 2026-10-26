"""East Money 公司大事 dstx."""

from __future__ import annotations

import json

from enterprise_scout_mcp.sources.eastmoney_company_events import (
    company_event_blocks_from_payload,
    company_events_from_payload,
)


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


def test_company_event_blocks_from_payload() -> None:
    payload = {
        "dzjy": [
            {
                "SECUCODE": "002271.SZ",
                "TRADE_DATE": "2026-09-16 00:00:00",
                "DEAL_PRICE": 10.86,
                "BUYER_NAME": "机构专用",
                "DEAL_AMT": 5186736,
            }
        ],
        "lhbd": [
            {
                "SECUCODE": "002271.SZ",
                "TRADE_DATE": "2023-07-25 00:00:00",
                "EXPLANATION": "日涨幅偏离值达到7%的前5只证券",
            }
        ],
    }
    rows = company_event_blocks_from_payload(payload, security_id="SZSE:002271", collected_at="t0")
    kinds = {r["block_kind"] for r in rows}
    assert "block_trade" in kinds
    assert "dragon_tiger" in kinds
    block = next(r for r in rows if r["block_kind"] == "block_trade")
    metrics = json.loads(block["metrics_json"])
    assert metrics["DEAL_PRICE"] == 10.86
