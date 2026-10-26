"""East Money F10 主营构成 → listed segments rows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from enterprise_scout_mcp.output.listed_schema import segments_row
from enterprise_scout_mcp.sources.eastmoney_company import _em_code

_URL = "https://emweb.securities.eastmoney.com/PC_HSF10/BusinessAnalysis/PageAjax"
_HEADERS = {
    "Accept": "application/json",
    "Referer": "https://emweb.securities.eastmoney.com/",
    "User-Agent": "Mozilla/5.0",
}

_KIND_MAP = {
    "1": "industry",
    "2": "product",
    "3": "region",
    1: "industry",
    2: "product",
    3: "region",
}


def _period_from_report_date(raw: Any) -> str:
    text = str(raw or "").strip()
    if len(text) >= 4 and text[:4].isdigit():
        return text[:4]
    return ""


def _pick_latest_period(rows: list[dict[str, Any]]) -> str:
    """Prefer latest annual (12-31); else lexicographic max YYYY-MM-DD."""
    if not rows:
        return ""
    annual = sorted(
        {
            _period_from_report_date(r.get("REPORT_DATE"))
            for r in rows
            if str(r.get("REPORT_DATE") or "").strip()[5:10] in ("12-31", "12-30", "12-29")
        }
    )
    if annual:
        return annual[-1]
    periods = sorted({_period_from_report_date(r.get("REPORT_DATE")) for r in rows if _period_from_report_date(r.get("REPORT_DATE"))})
    return periods[-1] if periods else ""


def zygcfx_to_segment_rows(
    payload_rows: list[dict[str, Any]],
    *,
    issuer_id: str,
    period: str,
    document_id: str,
    collected_at: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in payload_rows:
        if _period_from_report_date(raw.get("REPORT_DATE")) != period:
            continue
        kind = _KIND_MAP.get(raw.get("MAINOP_TYPE")) or _KIND_MAP.get(str(raw.get("MAINOP_TYPE") or "").strip())
        name = str(raw.get("ITEM_NAME") or "").strip()
        if not kind or not name:
            continue
        income = raw.get("MAIN_BUSINESS_INCOME")
        cost = raw.get("MAIN_BUSINESS_COST")
        segment_id = f"{issuer_id}:{kind}:{name}"
        out.append(
            segments_row(
                issuer_id=issuer_id,
                period=period,
                kind=kind,
                segment_id=segment_id,
                parent_segment_id="",
                name=name,
                revenue="" if income is None else str(income),
                cost="" if cost is None else str(cost),
                comparable_flag="true",
                document_id=document_id,
                collected_at=collected_at,
            )
        )
    return out


def fetch_business_segments(
    symbol_or_security: str,
    *,
    issuer_id: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Pull latest-period product/industry/region segments for one listing."""
    em_code = _em_code(symbol_or_security)
    report: dict[str, Any] = {
        "input": symbol_or_security,
        "em_code": em_code,
        "issuer_id": issuer_id or "",
        "period": "",
        "segments": [],
        "skipped": [],
    }
    if not em_code:
        report["skipped"].append("unresolved_symbol")
        return report
    listing = None
    try:
        from enterprise_scout_mcp.sources.cninfo import resolve_listing

        listing = resolve_listing(symbol_or_security)
    except Exception:
        listing = None
    if listing is not None:
        security_id, _code, _col = listing
        if not report["issuer_id"]:
            report["issuer_id"] = issuer_id or security_id
    if not report["issuer_id"]:
        report["skipped"].append("no_issuer_id")
        return report

    own = client is None
    http = client or httpx.Client(timeout=25.0, headers=_HEADERS)
    try:
        resp = http.get(_URL, params={"code": em_code})
        resp.raise_for_status()
        payload = resp.json()
    except Exception:
        report["skipped"].append("http_failed")
        return report
    finally:
        if own:
            http.close()

    zygc = payload.get("zygcfx") if isinstance(payload, dict) else None
    if not isinstance(zygc, list) or not zygc:
        report["skipped"].append("empty_zygcfx")
        return report

    period = _pick_latest_period(zygc)
    if not period:
        report["skipped"].append("no_period")
        return report
    collected_at = datetime.now(timezone.utc).isoformat()
    document_id = f"eastmoney:f10:zygcfx:{em_code}:{period}"
    rows = zygcfx_to_segment_rows(
        zygc,
        issuer_id=str(report["issuer_id"]),
        period=period,
        document_id=document_id,
        collected_at=collected_at,
    )
    report["period"] = period
    report["segments"] = rows
    if not rows:
        report["skipped"].append("no_rows_for_period")
    return report
