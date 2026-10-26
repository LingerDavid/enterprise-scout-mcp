"""Batch backfill listed/facts from East Money datacenter (no QMT)."""

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
from enterprise_scout_mcp.integrations.listed_facts_bridge import (
    facts_from_panel_row,
    issuer_id_by_security,
    symbol_to_security_id,
)
from enterprise_scout_mcp.output.listed_schema import to_tradecraft_symbol
from enterprise_scout_mcp.sources.eastmoney_statements import fetch_statement_rows


def backfill_listed_facts_em(
    warehouse_dir: Path,
    *,
    workers: int = 12,
    limit: int | None = None,
    page_size: int = 12,
    progress_path: Path | None = None,
) -> dict[str, Any]:
    """Fetch EM statements per identity row; merge into listed/facts."""
    warehouse_dir = Path(warehouse_dir)
    collected_at = datetime.now(timezone.utc).isoformat()
    identity = read_identity_rows(warehouse_dir)
    if limit is not None:
        identity = identity[: max(0, int(limit))]
    issuer_map = issuer_id_by_security(warehouse_dir)

    summary: dict[str, Any] = {
        "warehouse_dir": str(warehouse_dir),
        "identity_rows": len(identity),
        "workers": workers,
        "page_size": page_size,
        "started_at": collected_at,
    }
    if not identity:
        summary["error"] = "no_identity_rows"
        return summary

    touched_issuer: set[str] = set()
    all_facts: list[dict[str, Any]] = []

    def fetch_one(row: dict[str, Any]) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
        sym = to_tradecraft_symbol(str(row.get("security_id") or ""))
        if not sym:
            return "", [], {"skipped": ["no_symbol"]}
        security_id = symbol_to_security_id(sym) or ""
        issuer_id = str(issuer_map.get(security_id) or row.get("issuer_id") or security_id)
        panel_rows = fetch_statement_rows(sym, page_size=page_size)
        facts: list[dict[str, Any]] = []
        for panel in panel_rows:
            for fact in facts_from_panel_row(panel, issuer_id=issuer_id):
                fact["collected_at"] = collected_at
                fact["document_id"] = fact.get("document_id") or f"eastmoney:datacenter:{issuer_id}:{fact.get('period')}"
                facts.append(fact)
        if issuer_id:
            touched_issuer.add(issuer_id)
        return sym, facts, {"skipped": [] if facts else ["empty_statements"]}

    facts_rows, counts, skipped = run_identity_batch(identity, fetch_one, workers=workers)
    all_facts.extend(facts_rows)
    path = merge_listed_table(
        warehouse_dir,
        "facts",
        all_facts,
        drop_key="issuer_id",
        drop_values=touched_issuer,
    )
    summary.update(
        {
            "facts_written": len(all_facts),
            "symbols_ok": counts["ok"],
            "symbols_skipped": counts["skipped"],
            "path": path,
            "skipped_samples": skipped,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    if progress_path is not None:
        progress_path.parent.mkdir(parents=True, exist_ok=True)
        with progress_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(summary, ensure_ascii=False) + "\n")
    return summary
