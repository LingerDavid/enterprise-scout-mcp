"""Sample listed disclosure for one security: cninfo PDF index + F10 holders.

Facts (P&L / BS / CF) stay on the QMT path in tradecraft. This sampler only
fills what QMT does not: announcement document ids / PDF files, and a
temporary top-10 holders feed from Eastmoney until PDF extraction exists.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from enterprise_scout_mcp.output.listed_schema import identity_row
from enterprise_scout_mcp.output.listed_writer import append_listed_rows
from enterprise_scout_mcp.sources.cninfo import (
    CATEGORY_ANNUAL,
    download_pdf,
    pick_annual_report,
    query_announcements,
    resolve_listing,
)
from enterprise_scout_mcp.sources.eastmoney_holders import fetch_top_holders


def sample_listed_disclosure(
    symbol_or_security: str,
    *,
    corpus_dir: Path,
    warehouse_dir: Path | None = None,
    pdf_dir: Path | None = None,
    year: str | int | None = None,
    download: bool = True,
    dry_run: bool = False,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Index annual report + optional PDF + top-10 holders for one listing."""
    collected_at = datetime.now(timezone.utc).isoformat()
    listing = resolve_listing(symbol_or_security)
    report: dict[str, Any] = {
        "input": symbol_or_security,
        "security_id": "",
        "announcements": 0,
        "picked": None,
        "pdf_path": None,
        "holders": 0,
        "corpus_path": None,
        "dry_run": dry_run,
        "skipped": [],
    }
    if listing is None:
        report["skipped"].append("unresolved_symbol")
        return report
    security_id, code, _column = listing
    exchange = security_id.split(":", 1)[0]
    report["security_id"] = security_id

    anns = query_announcements(
        security_id,
        category=CATEGORY_ANNUAL,
        client=client,
    )
    report["announcements"] = len(anns)
    picked = pick_annual_report(anns, year=year)
    if picked is None:
        report["skipped"].append("no_annual_report")
    else:
        report["picked"] = {
            "document_id": picked.document_id,
            "document_date": picked.document_date,
            "title": picked.title,
            "pdf_url": picked.pdf_url,
        }
        if download and not dry_run:
            dest = Path(pdf_dir) if pdf_dir else Path(corpus_dir) / "pdf"
            path = download_pdf(picked, dest, client=client)
            report["pdf_path"] = str(path) if path else None
            if path is None:
                report["skipped"].append("pdf_download_failed")

    document_id = (picked.document_id if picked else "") or f"sample:{security_id}"
    document_date = picked.document_date if picked else ""

    holders = fetch_top_holders(
        security_id,
        document_id=document_id,
        collected_at=collected_at,
        client=client,
    )
    report["holders"] = len(holders)
    if not holders:
        report["skipped"].append("no_holders")

    record: dict[str, Any] = {
        "issuer_id": security_id,
        "issuer_name": "",
        "security_id": security_id,
        "exchange": exchange,
        "code": code,
        "period": str(year) if year is not None else "",
        "scope": "consolidated",
        "document_id": document_id,
        "document_date": document_date,
        "source": {
            "cninfo": report["picked"],
            "holders_feed": "eastmoney_f10",
        },
        "facts": [],
        "segments": [],
        "holders": [
            {
                "as_of": h.get("as_of", ""),
                "rank": h.get("rank", ""),
                "holder_name": h.get("holder_name", ""),
                "holder_type": h.get("holder_type", ""),
                "shares": h.get("shares", ""),
                "pct_total": h.get("pct_total", ""),
                "share_class": h.get("share_class", ""),
                "document_id": h.get("document_id", document_id),
            }
            for h in holders
        ],
    }

    if dry_run:
        return report

    corpus_dir = Path(corpus_dir)
    corpus_dir.mkdir(parents=True, exist_ok=True)
    corpus_path = corpus_dir / f"{code}.jsonl"
    with corpus_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    report["corpus_path"] = str(corpus_path)

    if warehouse_dir is not None:
        identity = [
            identity_row(
                issuer_id=security_id,
                issuer_name="",
                security_id=security_id,
                exchange=exchange,
                code=code,
                document_id=document_id,
                collected_at=collected_at,
                is_primary_listing="true",
            )
        ]
        append_listed_rows(Path(warehouse_dir), "identity", identity)
        if holders:
            append_listed_rows(Path(warehouse_dir), "holders", holders)

    return report
