"""East Money 盈利预测."""

from __future__ import annotations

from enterprise_scout_mcp.sources.eastmoney_profit_forecast import (
    forecast_estimates_from_payload,
    forecast_ratings_from_payload,
)


def test_forecast_ratings_from_payload() -> None:
    payload = {
        "pjtj": [
            {
                "DATE_TYPE_CODE": 1,
                "DATE_TYPE": "1个月",
                "COMPRE_RATING": "增持",
                "COMPRE_RATING_NUM": 4.33,
                "RATING_ORG_NUM": 3,
                "RATING_BUY_NUM": 1,
                "RATING_ADD_NUM": 2,
            }
        ],
    }
    rows = forecast_ratings_from_payload(payload, security_id="SZSE:002271", collected_at="t0")
    assert len(rows) == 1
    assert rows[0]["window_label"] == "1个月"
    assert rows[0]["compre_rating"] == "增持"


def test_forecast_estimates_from_ycmx() -> None:
    payload = {
        "ycmx": [
            {
                "ORG_NAME_ABBR": "中金公司",
                "PUBLISH_DATE": "2026-10-26 00:00:00",
                "RATING": "买入",
                "YEAR1": 2025,
                "YEAR_MARK1": "A",
                "EPS1": 0.05,
                "PE1": 200,
                "PARENT_NETPROFIT1": 1000000,
            }
        ],
    }
    rows = forecast_estimates_from_payload(payload, security_id="SZSE:002271", collected_at="t0")
    assert len(rows) == 1
    assert rows[0]["org_name"] == "中金公司"
    assert rows[0]["year"] == "2025"
    assert rows[0]["rating"] == "买入"
