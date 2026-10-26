"""East Money datacenter F10 workforce metrics → listed/workforce rows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from enterprise_scout_mcp.output.listed_schema import workforce_row
from enterprise_scout_mcp.sources.eastmoney_common import F10_HEADERS

_URL = "https://datacenter.eastmoney.com/securities/api/data/v1/get"

_MAINFINA_COLUMNS = (
    "SECUCODE,REPORT_DATE,REPORT_TYPE,STAFF_NUM,AVG_TOI,AVG_NET_PROFIT,"
    "RDPERSONNEL,PRATIO,RDEXPEND,TOTALOPERATEREVE,PARENTNETPROFIT"
)
_CASH_COLUMNS = "SECUCODE,REPORT_DATE,PAY_STAFF_CASH"
_BALANCE_COLUMNS = "SECUCODE,REPORT_DATE,STAFF_SALARY_PAYABLE"


def _day(value: Any) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    return digits[:8]


def _period_year(report_date: str) -> str:
    day = _day(report_date)
    return day[:4] if len(day) >= 4 else ""


def _is_annual(report_date: str, report_type: str = "") -> bool:
    day = _day(report_date)
    if len(day) >= 8 and day[4:8] in ("1231", "1230", "1229"):
        return True
    return "年报" in str(report_type or "")


def _fetch_report(
    symbol: str,
    report_name: str,
    columns: str,
    *,
    page_size: int,
    client: httpx.Client,
) -> list[dict[str, Any]]:
    try:
        resp = client.get(
            _URL,
            params={
                "reportName": report_name,
                "columns": columns,
                "filter": f'(SECUCODE="{symbol.strip().upper()}")',
                "pageNumber": "1",
                "pageSize": str(page_size),
                "sortTypes": "-1",
                "sortColumns": "REPORT_DATE",
                "source": "HSF10",
                "client": "PC",
            },
        )
        resp.raise_for_status()
        payload = resp.json()
    except Exception:
        return []
    result = payload.get("result") if isinstance(payload, dict) else None
    data = result.get("data") if isinstance(result, dict) else None
    return data if isinstance(data, list) else []


def _index_by_period(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        day = _day(row.get("REPORT_DATE"))
        if len(day) >= 8:
            out[day] = row
    return out


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _compute_avg_salary(
    pay_cash: float | None,
    payable_end: float | None,
    payable_prev: float | None,
    staff_num: float | None,
) -> float | None:
    if pay_cash is None or payable_end is None or payable_prev is None or not staff_num:
        return None
    expense = pay_cash + payable_end - payable_prev
    if expense <= 0 or staff_num <= 0:
        return None
    return expense / staff_num


def mainfina_to_workforce_rows(
    main_rows: list[dict[str, Any]],
    *,
    issuer_id: str,
    cash_by_day: dict[str, dict[str, Any]],
    balance_by_day: dict[str, dict[str, Any]],
    document_id_prefix: str,
    collected_at: str,
    max_years: int = 10,
) -> list[dict[str, Any]]:
    """Map annual MAINFINADATA + cash/balance into workforce rows."""
    annual = [
        r
        for r in main_rows
        if isinstance(r, dict)
        and _is_annual(str(r.get("REPORT_DATE") or ""), str(r.get("REPORT_TYPE") or ""))
        and _float_or_none(r.get("STAFF_NUM")) is not None
    ]
    annual.sort(key=lambda r: _day(r.get("REPORT_DATE")), reverse=True)
    annual = annual[: max(1, max_years)]

    out: list[dict[str, Any]] = []
    for row in annual:
        day = _day(row.get("REPORT_DATE"))
        period = _period_year(day)
        if not period:
            continue
        staff_num = _float_or_none(row.get("STAFF_NUM"))
        avg_toi = _float_or_none(row.get("AVG_TOI"))
        avg_net_profit = _float_or_none(row.get("AVG_NET_PROFIT"))
        rd_personnel = _float_or_none(row.get("RDPERSONNEL"))
        rd_ratio = _float_or_none(row.get("PRATIO"))
        rd_expend = _float_or_none(row.get("RDEXPEND"))

        cash_row = cash_by_day.get(day) or {}
        bal_row = balance_by_day.get(day) or {}
        pay_cash = _float_or_none(cash_row.get("PAY_STAFF_CASH"))
        payable_end = _float_or_none(bal_row.get("STAFF_SALARY_PAYABLE"))

        prev_year = f"{int(period) - 1}1231"
        payable_prev = _float_or_none((balance_by_day.get(prev_year) or {}).get("STAFF_SALARY_PAYABLE"))
        avg_salary = _compute_avg_salary(pay_cash, payable_end, payable_prev, staff_num)

        out.append(
            workforce_row(
                issuer_id=issuer_id,
                period=period,
                staff_num="" if staff_num is None else str(int(staff_num)),
                avg_salary="" if avg_salary is None else str(round(avg_salary, 4)),
                avg_revenue="" if avg_toi is None else str(round(avg_toi, 4)),
                avg_net_profit="" if avg_net_profit is None else str(round(avg_net_profit, 4)),
                rd_personnel="" if rd_personnel is None else str(int(rd_personnel)),
                rd_ratio="" if rd_ratio is None else str(round(rd_ratio, 4)),
                rd_expend="" if rd_expend is None else str(round(rd_expend, 4)),
                pay_staff_cash="" if pay_cash is None else str(round(pay_cash, 4)),
                staff_salary_payable="" if payable_end is None else str(round(payable_end, 4)),
                document_id=f"{document_id_prefix}:{period}",
                collected_at=collected_at,
            )
        )
    return out


def fetch_workforce_metrics(
    symbol_or_security: str,
    *,
    issuer_id: str | None = None,
    page_size: int = 20,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Live datacenter pull for workforce competitiveness (annual series)."""
    from enterprise_scout_mcp.sources.cninfo import resolve_listing

    listing = resolve_listing(symbol_or_security)
    report: dict[str, Any] = {
        "input": symbol_or_security,
        "issuer_id": issuer_id or "",
        "workforce": [],
        "skipped": [],
    }
    if listing is None:
        report["skipped"].append("unresolved_symbol")
        return report
    security_id, _code, _col = listing
    if not report["issuer_id"]:
        report["issuer_id"] = issuer_id or security_id

    sym = symbol_or_security.strip().upper()
    if "." not in sym and ":" in security_id:
        from enterprise_scout_mcp.output.listed_schema import to_tradecraft_symbol

        sym = to_tradecraft_symbol(security_id) or sym
    if "." not in sym:
        report["skipped"].append("no_symbol")
        return report

    own = client is None
    http = client or httpx.Client(timeout=25.0, headers=F10_HEADERS, follow_redirects=True)
    try:
        main_rows = _fetch_report(sym, "RPT_F10_FINANCE_MAINFINADATA", _MAINFINA_COLUMNS, page_size=page_size, client=http)
        cash_rows = _fetch_report(sym, "RPT_F10_FINANCE_GCASHFLOW", _CASH_COLUMNS, page_size=page_size, client=http)
        balance_rows = _fetch_report(sym, "RPT_F10_FINANCE_GBALANCE", _BALANCE_COLUMNS, page_size=page_size, client=http)
    finally:
        if own:
            http.close()

    if not main_rows:
        report["skipped"].append("empty_mainfina")
        return report

    collected_at = datetime.now(timezone.utc).isoformat()
    document_id_prefix = f"eastmoney:datacenter:workforce:{sym}"
    rows = mainfina_to_workforce_rows(
        main_rows,
        issuer_id=str(report["issuer_id"]),
        cash_by_day=_index_by_period(cash_rows),
        balance_by_day=_index_by_period(balance_rows),
        document_id_prefix=document_id_prefix,
        collected_at=collected_at,
    )
    report["workforce"] = rows
    if not rows:
        report["skipped"].append("no_annual_workforce")
    return report
