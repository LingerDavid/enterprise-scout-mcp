"""F10 structure probe and new tab collectors."""

from __future__ import annotations

from enterprise_scout_mcp.sources.eastmoney_exec_trades import exec_trades_from_f10_payload
from enterprise_scout_mcp.sources.eastmoney_fund_holdings import fund_holdings_from_f10_payload
from enterprise_scout_mcp.sources.eastmoney_f10_probe import summarize_page_ajax_payload
from enterprise_scout_mcp.sources.eastmoney_float_holders import float_holders_from_f10_payload
from enterprise_scout_mcp.sources.eastmoney_holder_stats import holder_stats_from_f10_payload
from enterprise_scout_mcp.sources.eastmoney_institutional import institutional_from_f10_payload
from enterprise_scout_mcp.sources.eastmoney_ipo_profile import ipo_profile_from_f10_payload


def test_summarize_page_ajax_payload() -> None:
    summary = summarize_page_ajax_payload(
        {
            "sdgd": [{"HOLDER_NAME": "A", "HOLD_NUM": 1}],
            "sjkzr": {"HOLDER_NAME": "B"},
            "sdgd_date": [],
        }
    )
    assert summary["top_level_keys"] == ["sdgd", "sdgd_date", "sjkzr"]
    assert summary["blocks"]["sdgd"]["count"] == 1
    assert "HOLDER_NAME" in summary["blocks"]["sdgd"]["samples"][0]["fields"]


def test_holder_stats_from_gdrs() -> None:
    rows = holder_stats_from_f10_payload(
        {
            "gdrs": [
                {
                    "END_DATE": "2025-12-31",
                    "HOLDER_TOTAL_NUM": 120000,
                    "TOTAL_NUM_RATIO": 1.5,
                    "AVG_FREE_SHARES": 1000,
                    "AVG_HOLD_AMT": 50000,
                }
            ]
        },
        security_id="SZSE:002271",
        collected_at="t0",
    )
    assert len(rows) == 1
    assert rows[0]["holder_count"] == "120000"
    assert rows[0]["as_of"] == "2025-12-31"


def test_float_holders_from_sdltgd() -> None:
    rows = float_holders_from_f10_payload(
        {
            "sdltgd": [
                {
                    "END_DATE": "2025-12-31",
                    "HOLDER_RANK": 1,
                    "HOLDER_NAME": "香港中央结算",
                    "HOLDER_TYPE": "其它",
                    "HOLD_NUM": 1000,
                    "FREE_HOLDNUM_RATIO": 5.5,
                }
            ]
        },
        security_id="SZSE:002271",
        collected_at="t0",
    )
    assert rows[0]["holder_name"] == "香港中央结算"
    assert rows[0]["pct_float"] == "5.5"


def test_institutional_from_jgcc() -> None:
    rows = institutional_from_f10_payload(
        {
            "jgcc": [
                {
                    "REPORT_DATE": "2025-12-31",
                    "ORG_TYPE": "基金",
                    "TOTAL_ORG_NUM": 120,
                    "TOTAL_FREE_SHARES": 50000000,
                    "TOTAL_SHARES_RATIO": 10.2,
                    "ALL_SHARES_RATIO": 8.1,
                }
            ]
        },
        security_id="SZSE:002271",
        collected_at="t0",
    )
    assert rows[0]["org_type"] == "基金"
    assert rows[0]["org_count"] == "120"


def test_fund_holdings_from_jjcq() -> None:
    rows = fund_holdings_from_f10_payload(
        {
            "jjcg": [
                {
                    "REPORT_DATE": "2025-12-31",
                    "HOLDER_NAME": "易方达蓝筹",
                    "FUND_CODE": "005827",
                    "ORG_TYPE": "01",
                    "TOTAL_SHARES": 1000000,
                    "HOLD_VALUE": 25000000,
                    "TOTALSHARES_RATIO": 0.42,
                    "FREESHARES_RATIO": 0.51,
                    "NETVALUE_RATIO": 1.2,
                }
            ]
        },
        security_id="SZSE:002271",
        collected_at="t0",
    )
    assert rows[0]["fund_name"] == "易方达蓝筹"
    assert rows[0]["fund_code"] == "005827"


def test_exec_trades_from_cgbd() -> None:
    rows = exec_trades_from_f10_payload(
        {
            "cgbd": [
                {
                    "END_DATE": "2025-06-01",
                    "EXECUTIVE_NAME": "张三",
                    "POSITION": "董事长",
                    "CHANGE_NUM": 10000,
                    "AVERAGE_PRICE": 12.5,
                    "CHANGE_AFTER_HOLDNUM": 50000,
                    "TRADE_WAY": "竞价交易",
                    "HOLDER_NAME": "张三",
                }
            ]
        },
        security_id="SZSE:002271",
        collected_at="t0",
    )
    assert rows[0]["person_name"] == "张三"
    assert rows[0]["change_shares"] == "10000.0"


def test_ipo_profile_from_fxxg() -> None:
    rows = ipo_profile_from_f10_payload(
        {
            "fxxg": [
                {
                    "FOUND_DATE": "1998-01-01",
                    "LISTING_DATE": "2008-09-10",
                    "ISSUE_PRICE": 17.33,
                    "TOTAL_ISSUE_NUM": 132000000,
                    "PAR_VALUE": 1,
                    "ISSUE_WAY": "网下询价",
                }
            ]
        },
        security_id="SZSE:002271",
        collected_at="t0",
    )
    assert len(rows) == 1
    assert rows[0]["listing_date"] == "2008-09-10"
    assert rows[0]["issue_price"] == "17.33"
