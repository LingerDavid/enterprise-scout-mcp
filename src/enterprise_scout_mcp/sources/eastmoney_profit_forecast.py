"""East Money F10 盈利预测 (ProfitForecast PageAjax)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from enterprise_scout_mcp.output.listed_schema import forecast_estimate_row, forecast_rating_row
from enterprise_scout_mcp.sources.eastmoney_common import date_str, em_code, fetch_f10_page


def _str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _finite(value: Any) -> str:
    if value is None or value == "":
        return ""
    try:
        return str(float(value))
    except (TypeError, ValueError):
        return _str(value)


def forecast_ratings_from_payload(
    payload: dict[str, Any],
    *,
    security_id: str,
    document_id: str = "",
    collected_at: str = "",
) -> list[dict[str, Any]]:
    items = payload.get("pjtj") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        window = _str(raw.get("DATE_TYPE_CODE"))
        if not window:
            continue
        out.append(
            forecast_rating_row(
                security_id=security_id,
                window_code=window,
                window_label=_str(raw.get("DATE_TYPE")),
                compre_rating=_str(raw.get("COMPRE_RATING")),
                compre_rating_num=_finite(raw.get("COMPRE_RATING_NUM")),
                rating_org_num=_finite(raw.get("RATING_ORG_NUM")),
                rating_buy=_finite(raw.get("RATING_BUY_NUM")),
                rating_add=_finite(raw.get("RATING_ADD_NUM")),
                rating_neutral=_finite(raw.get("RATING_NEUTRAL_NUM")),
                rating_reduce=_finite(raw.get("RATING_REDUCE_NUM")),
                rating_sale=_finite(raw.get("RATING_SALE_NUM")),
                document_id=document_id or f"eastmoney:f10:pjtj:{security_id}:{window}",
                collected_at=collected_at,
            )
        )
    return out


def _estimate_rows_from_block(
    raw: dict[str, Any],
    *,
    security_id: str,
    document_id: str,
    collected_at: str,
    source_key: str,
) -> list[dict[str, Any]]:
    org = _str(raw.get("ORG_NAME_ABBR"))
    publish = date_str(raw.get("PUBLISH_DATE"))
    rating = _str(raw.get("RATING"))
    researcher = _str(raw.get("RESEARCHER"))
    rows: list[dict[str, Any]] = []
    for idx in range(1, 5):
        year = raw.get(f"YEAR{idx}")
        if year is None or year == "":
            continue
        eps = raw.get(f"EPS{idx}")
        pe = raw.get(f"PE{idx}")
        profit = raw.get(f"PARENT_NETPROFIT{idx}")
        mark = _str(raw.get(f"YEAR_MARK{idx}"))
        rows.append(
            forecast_estimate_row(
                security_id=security_id,
                org_name=org,
                publish_date=publish,
                year=str(int(year)) if str(year).replace(".", "", 1).isdigit() else _str(year),
                year_mark=mark,
                eps=_finite(eps),
                pe=_finite(pe),
                parent_net_profit=_finite(profit),
                rating=rating,
                researcher=researcher,
                document_id=document_id or f"eastmoney:f10:{source_key}:{security_id}:{org}:{idx}",
                collected_at=collected_at,
            )
        )
    return rows


def forecast_estimates_from_payload(
    payload: dict[str, Any],
    *,
    security_id: str,
    document_id: str = "",
    collected_at: str = "",
) -> list[dict[str, Any]]:
    """Prefer ycmx (per-report); fall back to jgyc aggregate averages."""
    out: list[dict[str, Any]] = []
    ycmx = payload.get("ycmx") if isinstance(payload, dict) else None
    if isinstance(ycmx, list):
        for raw in ycmx:
            if isinstance(raw, dict):
                out.extend(
                    _estimate_rows_from_block(
                        raw,
                        security_id=security_id,
                        document_id=document_id,
                        collected_at=collected_at,
                        source_key="ycmx",
                    )
                )
    if out:
        return out
    jgyc = payload.get("jgyc") if isinstance(payload, dict) else None
    if isinstance(jgyc, list):
        for raw in jgyc:
            if isinstance(raw, dict):
                out.extend(
                    _estimate_rows_from_block(
                        raw,
                        security_id=security_id,
                        document_id=document_id,
                        collected_at=collected_at,
                        source_key="jgyc",
                    )
                )
    return out


def fetch_profit_forecast(
    symbol_or_security: str,
    *,
    document_id: str = "",
    collected_at: str = "",
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    parsed = em_code(symbol_or_security)
    if parsed is None:
        return {"forecast_ratings": [], "forecast_estimates": [], "skipped": ["unresolved_symbol"]}
    _em, security_id = parsed
    if not collected_at:
        collected_at = datetime.now(timezone.utc).isoformat()
    payload = fetch_f10_page("ProfitForecast", symbol_or_security, client=client)
    ratings = forecast_ratings_from_payload(
        payload, security_id=security_id, document_id=document_id, collected_at=collected_at
    )
    estimates = forecast_estimates_from_payload(
        payload, security_id=security_id, document_id=document_id, collected_at=collected_at
    )
    skipped: list[str] = []
    if not ratings:
        skipped.append("empty_pjtj")
    if not estimates:
        skipped.append("empty_ycmx_jgyc")
    return {
        "security_id": security_id,
        "forecast_ratings": ratings,
        "forecast_estimates": estimates,
        "skipped": skipped,
    }
