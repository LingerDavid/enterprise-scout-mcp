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
from enterprise_scout_mcp.sources.eastmoney_exec_trades import fetch_exec_holding_changes
from enterprise_scout_mcp.sources.eastmoney_fund_holdings import fetch_fund_holdings
from enterprise_scout_mcp.sources.eastmoney_executives import fetch_executives
from enterprise_scout_mcp.sources.eastmoney_float_holders import fetch_float_holders
from enterprise_scout_mcp.sources.eastmoney_holder_stats import fetch_holder_stats
from enterprise_scout_mcp.sources.eastmoney_holders import fetch_top_holders
from enterprise_scout_mcp.sources.eastmoney_institutional import fetch_institutional_holdings
from enterprise_scout_mcp.sources.eastmoney_ipo_profile import fetch_ipo_profile
from enterprise_scout_mcp.sources.eastmoney_segments import fetch_business_segments
from enterprise_scout_mcp.sources.eastmoney_workforce import fetch_workforce_metrics

_DEFAULT_TABLES = (
    "segments",
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
    "control",
    "workforce",
)


def _fetch_table(table: str, sym: str, identity_row: dict[str, Any], collected_at: str) -> dict[str, Any]:
    issuer_id = str(identity_row.get("issuer_id") or "").strip()
    if table == "segments":
        rep = fetch_business_segments(sym, issuer_id=issuer_id)
        return {"rows": rep.get("segments") or [], "skipped": rep.get("skipped") or []}
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
    if table == "dividend_summary":
        rep = fetch_bonus_extras(sym, collected_at=collected_at)
        return {"rows": rep.get("dividend_summary") or [], "skipped": rep.get("skipped") or []}
    if table == "seo_issues":
        rep = fetch_bonus_extras(sym, collected_at=collected_at)
        return {"rows": rep.get("seo_issues") or [], "skipped": rep.get("skipped") or []}
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
    tables: tuple[str, ...] = _DEFAULT_TABLES,
    workers: int = 12,
    limit: int | None = None,
    progress_path: Path | None = None,
) -> dict[str, Any]:
    """Fetch F10 data for each identity row; write listed parquet tables."""
    warehouse_dir = Path(warehouse_dir)
    collected_at = datetime.now(timezone.utc).isoformat()
    identity = read_identity_rows(warehouse_dir)
    if limit is not None:
        identity = identity[: max(0, int(limit))]

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

    for table in tables:
        dest = "listed_control" if table == "control" else table
        drop_key = "issuer_id" if table in {"segments", "control", "workforce"} else "security_id"
        drop_values = touched_issuer if drop_key == "issuer_id" else touched_security

        def fetch_one(row: dict[str, Any], *, _table: str = table) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
            sym = to_tradecraft_symbol(str(row.get("security_id") or ""))
            if not sym:
                return "", [], {"skipped": ["no_symbol"]}
            rep = _fetch_table(_table, sym, row, collected_at)
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

    summary["finished_at"] = datetime.now(timezone.utc).isoformat()
    if progress_path is not None:
        progress_path.parent.mkdir(parents=True, exist_ok=True)
        with progress_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(summary, ensure_ascii=False) + "\n")
    return summary
