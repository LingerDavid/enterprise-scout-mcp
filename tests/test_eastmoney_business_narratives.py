"""East Money 经营分析 narrative blocks."""

from __future__ import annotations

from enterprise_scout_mcp.sources.eastmoney_business_narratives import (
    business_review_from_payload,
    business_scope_from_payload,
)


def test_business_scope_from_payload() -> None:
    payload = {
        "zyfw": [{"SECUCODE": "002271.SZ", "BUSINESS_SCOPE": "防水材料制造与销售"}],
    }
    rows = business_scope_from_payload(payload, security_id="SZSE:002271", collected_at="t0")
    assert len(rows) == 1
    assert rows[0]["business_scope"] == "防水材料制造与销售"


def test_business_review_picks_latest_report() -> None:
    payload = {
        "jyps": [
            {
                "REPORT_DATE": "2024-12-31 00:00:00",
                "BUSINESS_REVIEW": "旧评述",
            },
            {
                "REPORT_DATE": "2025-06-30 00:00:00",
                "BUSINESS_REVIEW": "最新评述",
            },
        ],
    }
    rows = business_review_from_payload(payload, security_id="SZSE:002271", collected_at="t0")
    assert len(rows) == 1
    assert rows[0]["as_of"] == "2025-06-30"
    assert rows[0]["content"] == "最新评述"
