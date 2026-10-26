"""East Money workforce metrics mapping."""

from __future__ import annotations

from enterprise_scout_mcp.sources.eastmoney_workforce import mainfina_to_workforce_rows


def test_mainfina_to_workforce_rows_computes_avg_salary() -> None:
    main_rows = [
        {
            "REPORT_DATE": "2025-12-31 00:00:00",
            "REPORT_TYPE": "年报",
            "STAFF_NUM": 10318,
            "AVG_TOI": 2672868.07,
            "AVG_NET_PROFIT": 10977.62,
            "RDPERSONNEL": 568,
            "PRATIO": 5.51,
            "RDEXPEND": 503462763.49,
        },
        {
            "REPORT_DATE": "2025-06-30 00:00:00",
            "REPORT_TYPE": "中报",
            "STAFF_NUM": None,
        },
    ]
    cash_by_day = {"20251231": {"PAY_STAFF_CASH": 2838453117.03}}
    balance_by_day = {
        "20251231": {"STAFF_SALARY_PAYABLE": 154167383.37},
        "20241231": {"STAFF_SALARY_PAYABLE": 134003073.8},
    }
    rows = mainfina_to_workforce_rows(
        main_rows,
        issuer_id="issuer-1",
        cash_by_day=cash_by_day,
        balance_by_day=balance_by_day,
        document_id_prefix="eastmoney:datacenter:workforce:002271.SZ",
        collected_at="2026-10-26T00:00:00+00:00",
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["issuer_id"] == "issuer-1"
    assert row["period"] == "2025"
    assert row["staff_num"] == "10318"
    assert float(row["avg_revenue"]) == 2672868.07
    assert float(row["avg_net_profit"]) == 10977.62
    salary = float(row["avg_salary"])
    assert 27.6 <= salary / 10000 <= 27.8
