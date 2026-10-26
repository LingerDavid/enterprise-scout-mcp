"""East Money datacenter statement parsing."""

from __future__ import annotations

from enterprise_scout_mcp.sources.eastmoney_statements import merge_statement_rows, rows_from_report


def test_rows_from_report_income() -> None:
    payload = {
        "result": {
            "data": [
                {
                    "SECUCODE": "600519.SH",
                    "REPORT_DATE": "2024-12-31 00:00:00",
                    "NOTICE_DATE": "2025-04-01",
                    "OPERATE_INCOME": 1000000,
                    "PARENT_NETPROFIT": 500000,
                }
            ]
        }
    }
    column_map = {"OPERATE_INCOME": "revenue", "PARENT_NETPROFIT": "net_income_attributable"}
    rows = rows_from_report(payload, column_map)
    assert len(rows) == 1
    assert rows[0]["symbol"] == "600519.SH"
    assert rows[0]["revenue"] == 1000000


def test_merge_statement_rows() -> None:
    merged = merge_statement_rows(
        [{"symbol": "600519.SH", "period_end": "20241231", "revenue": 1}],
        [{"symbol": "600519.SH", "period_end": "20241231", "total_assets": 9}],
    )
    assert len(merged) == 1
    assert merged[0]["revenue"] == 1
    assert merged[0]["total_assets"] == 9
