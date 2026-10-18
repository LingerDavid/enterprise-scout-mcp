"""Listed-company column contracts and ticker mapping."""

from __future__ import annotations

from enterprise_scout_mcp.output.listed_schema import (
    FACTS_COLUMNS,
    IDENTITY_COLUMNS,
    INCOME_ITEM_CODES,
    facts_row,
    identity_row,
    security_id,
    to_tradecraft_symbol,
)


def test_security_id_and_tradecraft_map() -> None:
    sid = security_id("SSE", "600519")
    assert sid == "SSE:600519"
    assert to_tradecraft_symbol(sid) == "600519.SH"
    assert to_tradecraft_symbol("SZSE:000001") == "000001.SZ"
    assert to_tradecraft_symbol("BSE:830000") == "830000.BJ"
    assert to_tradecraft_symbol("NASDAQ:AAPL") is None


def test_identity_and_facts_row_keys() -> None:
    ident = identity_row(issuer_id="91", security_id="SSE:600519", exchange="SSE", code="600519")
    assert tuple(ident.keys()) == IDENTITY_COLUMNS
    assert ident["security_id"] == "SSE:600519"
    assert ident["board"] == ""

    fact = facts_row(
        issuer_id="91",
        period="2024",
        scope="consolidated",
        statement="income",
        item_code="revenue",
        value="100",
        unit="CNY",
    )
    assert tuple(fact.keys()) == FACTS_COLUMNS
    assert fact["item_code"] == "revenue"
    assert "revenue" in INCOME_ITEM_CODES
