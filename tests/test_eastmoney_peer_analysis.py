"""East Money 同行比较 IndustryAnalysis."""

from __future__ import annotations

import json

from enterprise_scout_mcp.sources.eastmoney_peer_analysis import peer_compare_rows_from_payload


def test_peer_compare_rows_from_payload() -> None:
    payload = {
        "czxbj": [
            {
                "SECUCODE": "002271.SZ",
                "CORRE_SECURITY_NAME": "东方雨虹",
                "YYSRTB": -1.7,
                "REPORT_DATE": "2026-06-30 00:00:00",
            }
        ],
        "scbx": [
            {
                "SECUCODE": "002271.SZ",
                "SECURITY_NAME_ABBR": "东方雨虹",
                "CHANGERATE": 4.93,
                "TRADE_DATE": "2026-10-26 00:00:00",
            }
        ],
    }
    rows = peer_compare_rows_from_payload(payload, security_id="SZSE:002271", collected_at="t0")
    kinds = {r["compare_kind"] for r in rows}
    assert "growth" in kinds
    assert "market" in kinds
    growth = next(r for r in rows if r["compare_kind"] == "growth")
    metrics = json.loads(growth["metrics_json"])
    assert metrics["YYSRTB"] == -1.7
