"""Prospectus (招股说明书) PDF extract — fallback when annual lacks named suppliers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from enterprise_scout_mcp.integrations.listed_equity_extract import (
    PROSPECTUS_PDF_CHANNEL,
    edges_from_equity_extract,
    upsert_filing_edges_to_warehouse,
)
from enterprise_scout_mcp.sources.annual_equity_pdf import (
    extract_equity_from_pdf,
    period_from_annual_meta,
)
from enterprise_scout_mcp.sources.cninfo import (
    CATEGORY_IPO,
    CATEGORY_PROSPECTUS,
    download_pdf,
    pick_prospectus,
    query_announcements,
    resolve_listing,
)
from enterprise_scout_mcp.sources.eastmoney_company import fetch_company_profile


def _query_prospectus_anns(
    security_id: str,
    *,
    client: httpx.Client | None,
) -> list[Any]:
    """Query IPO + prospectus categories and merge."""
    seen: set[str] = set()
    out: list[Any] = []
    for cat in (CATEGORY_PROSPECTUS, CATEGORY_IPO):
        for ann in query_announcements(security_id, category=cat, client=client):
            key = ann.announcement_id or ann.title
            if key in seen:
                continue
            seen.add(key)
            out.append(ann)
    return out


def sample_prospectus_disclosure(
    symbol_or_security: str,
    *,
    corpus_dir: Path,
    warehouse_dir: Path | None = None,
    pdf_dir: Path | None = None,
    download: bool = True,
    dry_run: bool = False,
    suppliers_only: bool = True,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Download prospectus PDF and extract suppliers (default) into the lake.

    Intended as a fallback when annual reports only disclose aggregate
    前五名采购额 without named counterparties. Edges use
    ``source_channel=prospectus_pdf`` so they do not clobber annual_pdf rows.
    """
    collected_at = datetime.now(timezone.utc).isoformat()
    listing = resolve_listing(symbol_or_security)
    report: dict[str, Any] = {
        "input": symbol_or_security,
        "security_id": "",
        "issuer_id": "",
        "issuer_name": "",
        "picked": None,
        "pdf_path": None,
        "suppliers": 0,
        "investments": 0,
        "subsidiaries": 0,
        "edges": 0,
        "corpus_path": None,
        "warehouse": {},
        "dry_run": dry_run,
        "skipped": [],
        "source_channel": PROSPECTUS_PDF_CHANNEL,
    }
    if listing is None:
        report["skipped"].append("unresolved_symbol")
        return report
    security_id, code, _column = listing
    exchange = security_id.split(":", 1)[0]
    report["security_id"] = security_id

    profile = fetch_company_profile(security_id, client=client)
    credit_code = str(profile.get("credit_code") or "").strip()
    issuer_id = credit_code or security_id
    issuer_name = str(profile.get("issuer_name") or "").strip()
    report["issuer_id"] = issuer_id
    report["issuer_name"] = issuer_name
    if not issuer_name:
        report["skipped"].append("no_issuer_name")

    anns = _query_prospectus_anns(security_id, client=client)
    picked = pick_prospectus(anns)
    if picked is None:
        report["skipped"].append("no_prospectus")
        return report
    title = str(picked.title or "")
    report["picked"] = {
        "document_id": picked.document_id,
        "document_date": picked.document_date,
        "title": picked.title,
        "pdf_url": picked.pdf_url,
    }

    pdf_path: Path | None = None
    if download and not dry_run:
        dest = Path(pdf_dir) if pdf_dir else Path(corpus_dir) / "pdf"
        pdf_path = download_pdf(picked, dest, client=client)
        report["pdf_path"] = str(pdf_path) if pdf_path else None
        if pdf_path is None:
            report["skipped"].append("pdf_download_failed")
            return report
    elif dry_run:
        return report

    if pdf_path is None or not pdf_path.is_file():
        report["skipped"].append("pdf_missing")
        return report

    period = period_from_annual_meta(title=title, document_date=picked.document_date)
    as_of = (picked.document_date or "")[:10] or (f"{period}-12-31" if period else "")
    extracted = extract_equity_from_pdf(
        pdf_path,
        security_id=security_id,
        issuer_id=issuer_id,
        document_id=picked.document_id,
        period=period or as_of[:4],
        as_of=as_of,
        collected_at=collected_at,
        issuer_name=issuer_name,
    )
    report["suppliers"] = len(extracted.suppliers)
    report["investments"] = len(extracted.investments)
    report["subsidiaries"] = len(extracted.subsidiaries)
    report["skipped"].extend(extracted.skipped)
    report["page_hits"] = dict(extracted.page_hits)

    include = frozenset({"suppliers"}) if suppliers_only else frozenset(
        {"suppliers", "investments", "subsidiaries"}
    )
    # Prospectus holders are usually pre-IPO; skip by default.
    edges = edges_from_equity_extract(
        extracted,
        issuer_name=issuer_name,
        credit_code=credit_code,
        collected_at=collected_at,
        source_channel=PROSPECTUS_PDF_CHANNEL,
        include=include,
    )
    report["edges"] = len(edges)

    if dry_run:
        return report

    record = {
        "issuer_id": issuer_id,
        "issuer_name": issuer_name,
        "security_id": security_id,
        "exchange": exchange,
        "code": code,
        "period": period,
        "scope": "prospectus",
        "document_id": picked.document_id,
        "document_date": picked.document_date,
        "source": {
            "equity_feed": "prospectus_pdf",
            "cninfo": report["picked"],
            "page_hits": extracted.page_hits,
        },
        "suppliers": [
            {
                "rank": s.get("rank", ""),
                "name": s.get("name", ""),
                "purchase_pct": s.get("purchase_pct", ""),
                "purchase_amount": s.get("purchase_amount", ""),
                "document_id": s.get("document_id", picked.document_id),
            }
            for s in extracted.suppliers
        ],
        "investments": [
            {
                "name": s.get("name", ""),
                "direct_pct": s.get("direct_pct", ""),
                "main_business": s.get("main_business", ""),
                "document_id": s.get("document_id", picked.document_id),
            }
            for s in (extracted.investments if not suppliers_only else [])
        ],
        "holders": [],
        "subsidiaries": [],
        "facts": [],
        "segments": [],
    }
    # Distinct corpus name so annual {code}.{period}.json is not overwritten.
    corpus_dir = Path(corpus_dir)
    corpus_dir.mkdir(parents=True, exist_ok=True)
    path = corpus_dir / f"{code}.prospectus.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["corpus_path"] = str(path)

    if warehouse_dir is not None and issuer_name and edges:
        edge_path = upsert_filing_edges_to_warehouse(
            Path(warehouse_dir),
            issuer_name=issuer_name,
            edges=edges,
            source_channel=PROSPECTUS_PDF_CHANNEL,
        )
        report["warehouse"] = {"edges": edge_path}

    return report


def maybe_fallback_prospectus_suppliers(
    *,
    symbol_or_security: str,
    annual_suppliers: list[dict[str, Any]],
    corpus_dir: Path,
    warehouse_dir: Path | None,
    pdf_dir: Path | None,
    client: httpx.Client | None,
    enabled: bool = True,
) -> dict[str, Any] | None:
    """If annual extract has no named suppliers, try prospectus once."""
    if not enabled:
        return None
    if annual_suppliers:
        return None
    return sample_prospectus_disclosure(
        symbol_or_security,
        corpus_dir=corpus_dir,
        warehouse_dir=warehouse_dir,
        pdf_dir=pdf_dir,
        download=True,
        dry_run=False,
        suppliers_only=True,
        client=client,
    )
