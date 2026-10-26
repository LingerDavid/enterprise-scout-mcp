"""Batch backfill East Money F10 tabs into EnterpriseLake listed/* tables."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from enterprise_scout_mcp.integrations.listed_batch_utils import (
    merge_listed_table,
    read_identity_rows,
    run_identity_batch,
)
from enterprise_scout_mcp.output.listed_schema import to_tradecraft_symbol
from enterprise_scout_mcp.sources.eastmoney_bonus_extras import fetch_bonus_extras
from enterprise_scout_mcp.sources.eastmoney_capital import fetch_capital_structure
from enterprise_scout_mcp.sources.eastmoney_capital_history import fetch_capital_history
from enterprise_scout_mcp.sources.eastmoney_control import fetch_actual_controller
from enterprise_scout_mcp.sources.eastmoney_dividends import fetch_dividends
from enterprise_scout_mcp.sources.eastmoney_float_share_mix import fetch_float_share_mix
from enterprise_scout_mcp.sources.eastmoney_restricted_unlock import fetch_restricted_unlock
from enterprise_scout_mcp.sources.eastmoney_exec_trades import fetch_exec_holding_changes
from enterprise_scout_mcp.sources.eastmoney_fund_holdings import fetch_fund_holdings
from enterprise_scout_mcp.sources.eastmoney_executives import fetch_executives
from enterprise_scout_mcp.sources.eastmoney_float_holders import fetch_float_holders
from enterprise_scout_mcp.sources.eastmoney_holder_stats import fetch_holder_stats
from enterprise_scout_mcp.sources.eastmoney_holders import fetch_top_holders
from enterprise_scout_mcp.sources.eastmoney_institutional import fetch_institutional_holdings
from enterprise_scout_mcp.sources.eastmoney_ipo_profile import fetch_ipo_profile
from enterprise_scout_mcp.sources.eastmoney_business_narratives import fetch_business_narratives
from enterprise_scout_mcp.sources.eastmoney_company_events import fetch_company_events
from enterprise_scout_mcp.sources.eastmoney_company_profile import fetch_company_profile
from enterprise_scout_mcp.sources.eastmoney_core_conception import fetch_core_conception
from enterprise_scout_mcp.sources.eastmoney_peer_analysis import fetch_peer_analysis
from enterprise_scout_mcp.sources.eastmoney_profit_forecast import fetch_profit_forecast
from enterprise_scout_mcp.sources.eastmoney_segments import fetch_business_segments
from enterprise_scout_mcp.sources.eastmoney_workforce import fetch_workforce_metrics

DEFAULT_LISTED_F10_TABLES = (
    "company_profile",
    "segments",
    "business_scope",
    "business_review",
    "core_highlights",
    "concept_boards",
    "forecast_ratings",
    "forecast_estimates",
    "peer_compare_em",
    "company_events",
    "holders",
    "float_holders",
    "holder_stats",
    "institutional_holdings",
    "fund_holdings",
    "float_share_mix",
    "ipo_profile",
    "capital",
    "capital_history",
    "executives",
    "exec_holding_changes",
    "dividends",
    "dividend_summary",
    "seo_issues",
    "allotment_issues",
    "restricted_unlock",
    "control",
    "workforce",
)


def _fetch_table(
    table: str,
    sym: str,
    identity_row: dict[str, Any],
    collected_at: str,
    *,
    narrative_cache: dict[str, dict[str, Any]] | None = None,
    conception_cache: dict[str, dict[str, Any]] | None = None,
    bonus_cache: dict[str, dict[str, Any]] | None = None,
    forecast_cache: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    issuer_id = str(identity_row.get("issuer_id") or "").strip()
    if table == "company_profile":
        rep = fetch_company_profile(sym, collected_at=collected_at)
        return {"rows": rep.get("company_profile") or [], "skipped": rep.get("skipped") or []}
    if table == "segments":
        rep = fetch_business_segments(sym, issuer_id=issuer_id)
        return {"rows": rep.get("segments") or [], "skipped": rep.get("skipped") or []}
    if table in {"business_scope", "business_review"}:
        cache = narrative_cache if narrative_cache is not None else {}
        if sym not in cache:
            cache[sym] = fetch_business_narratives(sym, collected_at=collected_at)
        rep = cache[sym]
        key = "business_scope" if table == "business_scope" else "business_review"
        return {"rows": rep.get(key) or [], "skipped": rep.get("skipped") or []}
    if table in {"core_highlights", "concept_boards"}:
        cache = conception_cache if conception_cache is not None else {}
        if sym not in cache:
            cache[sym] = fetch_core_conception(sym, collected_at=collected_at)
        rep = cache[sym]
        key = "core_highlights" if table == "core_highlights" else "concept_boards"
        return {"rows": rep.get(key) or [], "skipped": rep.get("skipped") or []}
    if table in {"forecast_ratings", "forecast_estimates"}:
        cache = forecast_cache if forecast_cache is not None else {}
        if sym not in cache:
            cache[sym] = fetch_profit_forecast(sym, collected_at=collected_at)
        rep = cache[sym]
        key = "forecast_ratings" if table == "forecast_ratings" else "forecast_estimates"
        return {"rows": rep.get(key) or [], "skipped": rep.get("skipped") or []}
    if table == "peer_compare_em":
        rep = fetch_peer_analysis(sym, collected_at=collected_at)
        return {"rows": rep.get("peer_compare_em") or [], "skipped": rep.get("skipped") or []}
    if table == "company_events":
        rep = fetch_company_events(sym, collected_at=collected_at)
        return {"rows": rep.get("company_events") or [], "skipped": rep.get("skipped") or []}
    if table == "holders":
        rows = fetch_top_holders(sym, collected_at=collected_at)
        return {"rows": rows, "skipped": [] if rows else ["empty_sdgd"]}
    if table == "float_holders":
        rep = fetch_float_holders(sym, collected_at=collected_at)
        return {"rows": rep.get("float_holders") or [], "skipped": rep.get("skipped") or []}
    if table == "institutional_holdings":
        rep = fetch_institutional_holdings(sym, collected_at=collected_at)
        return {"rows": rep.get("institutional_holdings") or [], "skipped": rep.get("skipped") or []}
    if table == "fund_holdings":
        rep = fetch_fund_holdings(sym, collected_at=collected_at)
        return {"rows": rep.get("fund_holdings") or [], "skipped": rep.get("skipped") or []}
    if table == "float_share_mix":
        rep = fetch_float_share_mix(sym, collected_at=collected_at)
        return {"rows": rep.get("float_share_mix") or [], "skipped": rep.get("skipped") or []}
    if table == "holder_stats":
        rep = fetch_holder_stats(sym, collected_at=collected_at)
        return {"rows": rep.get("holder_stats") or [], "skipped": rep.get("skipped") or []}
    if table == "ipo_profile":
        rep = fetch_ipo_profile(sym, collected_at=collected_at)
        return {"rows": rep.get("ipo_profile") or [], "skipped": rep.get("skipped") or []}
    if table == "capital":
        rep = fetch_capital_structure(sym, collected_at=collected_at)
        return {"rows": rep.get("capital") or [], "skipped": rep.get("skipped") or []}
    if table == "capital_history":
        rep = fetch_capital_history(sym, collected_at=collected_at)
        return {"rows": rep.get("capital_history") or [], "skipped": rep.get("skipped") or []}
    if table == "executives":
        rep = fetch_executives(sym, collected_at=collected_at)
        return {"rows": rep.get("executives") or [], "skipped": rep.get("skipped") or []}
    if table == "exec_holding_changes":
        rep = fetch_exec_holding_changes(sym, collected_at=collected_at)
        return {"rows": rep.get("exec_holding_changes") or [], "skipped": rep.get("skipped") or []}
    if table == "dividends":
        rep = fetch_dividends(sym, collected_at=collected_at)
        return {"rows": rep.get("dividends") or [], "skipped": rep.get("skipped") or []}
    if table in {"dividend_summary", "seo_issues", "allotment_issues"}:
        cache = bonus_cache if bonus_cache is not None else {}
        if sym not in cache:
            cache[sym] = fetch_bonus_extras(sym, collected_at=collected_at)
        rep = cache[sym]
        return {"rows": rep.get(table) or [], "skipped": rep.get("skipped") or []}
    if table == "restricted_unlock":
        rep = fetch_restricted_unlock(sym, collected_at=collected_at)
        return {"rows": rep.get("restricted_unlock") or [], "skipped": rep.get("skipped") or []}
    if table == "control":
        rep = fetch_actual_controller(sym, issuer_id=issuer_id, collected_at=collected_at)
        return {"rows": rep.get("control") or [], "skipped": rep.get("skipped") or []}
    if table == "workforce":
        rep = fetch_workforce_metrics(sym, issuer_id=issuer_id)
        return {"rows": rep.get("workforce") or [], "skipped": rep.get("skipped") or []}
    return {"rows": [], "skipped": [f"unknown_table:{table}"]}


def backfill_listed_f10(
    warehouse_dir: Path,
    *,
    tables: tuple[str, ...] = DEFAULT_LISTED_F10_TABLES,
    workers: int = 12,
    limit: int | None = None,
    symbols: tuple[str, ...] | None = None,
    progress_path: Path | None = None,
) -> dict[str, Any]:
    """Fetch F10 data for each identity row; write listed parquet tables."""
    warehouse_dir = Path(warehouse_dir)
    collected_at = datetime.now(timezone.utc).isoformat()
    identity = read_identity_rows(warehouse_dir)
    if symbols:
        want = {str(s or "").strip().upper() for s in symbols if str(s or "").strip()}
        filtered: list[dict[str, Any]] = []
        for row in identity:
            sid = str(row.get("security_id") or "").strip().upper()
            sym = to_tradecraft_symbol(sid) or ""
            code = str(row.get("code") or "").strip()
            if sid in want or sym in want or code in want or f"{code}.SZ" in want or f"{code}.SH" in want:
                filtered.append(row)
        identity = filtered
    if limit is not None:
        identity = identity[: max(0, int(limit))]

    # identity may contain duplicate security_id rows from repeated sample-listed runs.
    seen_security: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for row in identity:
        sid = str(row.get("security_id") or "").strip()
        if sid and sid in seen_security:
            continue
        if sid:
            seen_security.add(sid)
        deduped.append(row)
    identity = deduped

    summary: dict[str, Any] = {
        "warehouse_dir": str(warehouse_dir),
        "identity_rows": len(identity),
        "workers": workers,
        "tables": list(tables),
        "started_at": collected_at,
        "results": {},
    }
    if not identity:
        summary["error"] = "no_identity_rows"
        return summary

    touched_security = {str(r.get("security_id") or "") for r in identity if r.get("security_id")}
    touched_issuer = {str(r.get("issuer_id") or "") for r in identity if r.get("issuer_id")}

    narrative_cache: dict[str, dict[str, Any]] = {}
    conception_cache: dict[str, dict[str, Any]] = {}
    bonus_cache: dict[str, dict[str, Any]] = {}
    forecast_cache: dict[str, dict[str, Any]] = {}

    for table in tables:
        dest = "listed_control" if table == "control" else table
        drop_key = "issuer_id" if table in {"segments", "control", "workforce"} else "security_id"
        drop_values = touched_issuer if drop_key == "issuer_id" else touched_security

        def fetch_one(row: dict[str, Any], *, _table: str = table) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
            sym = to_tradecraft_symbol(str(row.get("security_id") or ""))
            if not sym:
                return "", [], {"skipped": ["no_symbol"]}
            rep = _fetch_table(
                _table,
                sym,
                row,
                collected_at,
                narrative_cache=narrative_cache,
                conception_cache=conception_cache,
                bonus_cache=bonus_cache,
                forecast_cache=forecast_cache,
            )
            rows = list(rep.get("rows") or [])
            return sym, rows, {"skipped": rep.get("skipped")}

        rows, counts, skipped = run_identity_batch(identity, fetch_one, workers=workers)
        path = merge_listed_table(
            warehouse_dir,
            dest,
            rows,
            drop_key=drop_key,
            drop_values=drop_values,
        )
        summary["results"][table] = {
            "rows_written": len(rows),
            "symbols_ok": counts["ok"],
            "symbols_skipped": counts["skipped"],
            "path": path,
            "skipped_samples": skipped,
            "merge_drop_key": drop_key,
            "merge_drop_count": len(drop_values),
        }
        if progress_path is not None:
            progress_path.parent.mkdir(parents=True, exist_ok=True)
            with progress_path.open("a", encoding="utf-8") as fh:
                fh.write(
                    json.dumps(
                        {
                            "table": table,
                            "finished_at": datetime.now(timezone.utc).isoformat(),
                            **summary["results"][table],
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )

    summary["finished_at"] = datetime.now(timezone.utc).isoformat()
    if progress_path is not None:
        progress_path.parent.mkdir(parents=True, exist_ok=True)
        with progress_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(summary, ensure_ascii=False) + "\n")
    return summary
