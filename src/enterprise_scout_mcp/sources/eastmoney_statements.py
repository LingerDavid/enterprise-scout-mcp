"""East Money datacenter F10 statements → canonical panel-shaped rows."""

from __future__ import annotations

from typing import Any

import httpx

from enterprise_scout_mcp.sources.eastmoney_common import F10_HEADERS

_URL = "https://datacenter.eastmoney.com/securities/api/data/v1/get"

_REPORTS: dict[str, tuple[str, dict[str, str]]] = {
    "income": (
        "RPT_F10_FINANCE_GINCOME",
        {
            "OPERATE_INCOME": "revenue",
            "OPERATE_PROFIT": "operating_profit",
            "PARENT_NETPROFIT": "net_income_attributable",
        },
    ),
    "cash_flow": (
        "RPT_F10_FINANCE_GCASHFLOW",
        {
            "NETCASH_OPERATE": "net_operating_cash_flow",
            "SALES_SERVICES": "cash_from_sales",
            "CONSTRUCT_LONG_ASSET": "capex",
            "ASSIGN_DIVIDEND_PORFIT": "dividends_paid",
            "NETCASH_INVEST": "net_investing_cash_flow",
            "NETCASH_FINANCE": "net_financing_cash_flow",
        },
    ),
    "balance_sheet": (
        "RPT_F10_FINANCE_GBALANCE",
        {
            "MONETARYFUNDS": "cash_and_equivalents",
            "ACCOUNTS_RECE": "accounts_receivable",
            "INVENTORY": "inventory",
            "GOODWILL": "goodwill",
            "TOTAL_ASSETS": "total_assets",
            "SHORT_LOAN": "short_term_borrowing",
            "LONG_LOAN": "long_term_borrowing",
            "ACCOUNTS_PAYABLE": "accounts_payable",
            "TOTAL_LIABILITIES": "total_liabilities",
            "TOTAL_PARENT_EQUITY": "equity_attributable",
            "MINORITY_EQUITY": "minority_interest",
            "TOTAL_EQUITY": "total_equity",
        },
    ),
}


def _day(value: Any) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    return digits[:8]


def rows_from_report(payload: dict[str, Any], column_map: dict[str, str]) -> list[dict[str, Any]]:
    result = payload.get("result") if isinstance(payload, dict) else None
    data = result.get("data") if isinstance(result, dict) else None
    if not isinstance(data, list):
        return []
    out: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("SECUCODE") or "").strip().upper()
        period_end = _day(item.get("REPORT_DATE"))
        if not symbol or len(period_end) < 8:
            continue
        row: dict[str, Any] = {
            "symbol": symbol,
            "period_end": period_end,
            "announce_date": _day(item.get("NOTICE_DATE")),
        }
        for src, dest in column_map.items():
            raw = item.get(src)
            if raw is None or raw == "":
                continue
            row[dest] = raw
        out.append(row)
    return out


def merge_statement_rows(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for group in groups:
        for row in group:
            key = (str(row.get("symbol") or ""), str(row.get("period_end") or ""))
            if not key[0] or not key[1]:
                continue
            slot = merged.setdefault(key, {"symbol": key[0], "period_end": key[1]})
            for field, value in row.items():
                if field in {"symbol", "period_end"}:
                    continue
                if value is None or value == "":
                    continue
                if field not in slot or slot[field] in ("", None):
                    slot[field] = value
    return list(merged.values())


def fetch_statement_rows(
    symbol: str,
    *,
    page_size: int = 12,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    """Live datacenter pull for one tradecraft symbol (``600519.SH``). Soft-fail → []."""
    code = str(symbol or "").strip().upper()
    if "." not in code:
        return []
    own = client is None
    http = client or httpx.Client(timeout=20.0, headers=F10_HEADERS, follow_redirects=True)
    groups: list[list[dict[str, Any]]] = []
    try:
        for _name, (report, column_map) in _REPORTS.items():
            columns = "SECUCODE,REPORT_DATE,NOTICE_DATE," + ",".join(column_map)
            try:
                resp = http.get(
                    _URL,
                    params={
                        "reportName": report,
                        "columns": columns,
                        "filter": f'(SECUCODE="{code}")',
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
                continue
            if isinstance(payload, dict):
                groups.append(rows_from_report(payload, column_map))
    finally:
        if own:
            http.close()
    return merge_statement_rows(*groups)
