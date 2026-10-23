"""Run annual-report equity extract and upsert into corpus + warehouse."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from enterprise_scout_mcp.output.listed_writer import replace_listed_rows
from enterprise_scout_mcp.sources.annual_equity_pdf import (
    EquityExtractResult,
    extract_equity_from_pdf,
    period_from_annual_meta,
)

HOLDERS_MATCH_KEYS = ("security_id", "as_of")
SUBSIDIARIES_MATCH_KEYS = ("issuer_id", "period", "document_id")
CONTROL_MATCH_KEYS = ("issuer_id", "as_of", "document_id")


def write_equity_corpus_record(
    corpus_dir: Path,
    record: dict[str, Any],
) -> Path:
    """Write ``{code}.{period}.json`` (whole-file replace). Falls back to code-only."""
    code = str(record.get("code") or "").strip() or "unknown"
    period = str(record.get("period") or "").strip()
    name = f"{code}.{period}.json" if period else f"{code}.equity.json"
    corpus_dir = Path(corpus_dir)
    corpus_dir.mkdir(parents=True, exist_ok=True)
    path = corpus_dir / name
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def upsert_equity_to_warehouse(
    warehouse_dir: Path,
    *,
    holders: list[dict[str, Any]],
    subsidiaries: list[dict[str, Any]],
    listed_control: list[dict[str, Any]],
) -> dict[str, str | None]:
    """Idempotent replace into listed parquet tables."""
    wh = Path(warehouse_dir)
    paths: dict[str, str | None] = {
        "holders": None,
        "subsidiaries": None,
        "listed_control": None,
    }
    if holders:
        p = replace_listed_rows(wh, "holders", holders, match_keys=HOLDERS_MATCH_KEYS)
        paths["holders"] = str(p) if p else None
    if subsidiaries:
        p = replace_listed_rows(
            wh, "subsidiaries", subsidiaries, match_keys=SUBSIDIARIES_MATCH_KEYS
        )
        paths["subsidiaries"] = str(p) if p else None
    if listed_control:
        p = replace_listed_rows(
            wh, "listed_control", listed_control, match_keys=CONTROL_MATCH_KEYS
        )
        paths["listed_control"] = str(p) if p else None
    return paths


def extract_and_store_equity(
    pdf_path: Path,
    *,
    security_id: str,
    issuer_id: str,
    issuer_name: str = "",
    exchange: str = "",
    code: str = "",
    document_id: str = "",
    document_date: str = "",
    title: str = "",
    year: str | int | None = None,
    corpus_dir: Path | None = None,
    warehouse_dir: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Extract from one annual PDF and optionally write corpus + warehouse."""
    collected_at = datetime.now(timezone.utc).isoformat()
    period = period_from_annual_meta(title=title, document_date=document_date, year=year)
    as_of = str(document_date or "").strip()[:10]
    if not as_of and period:
        as_of = f"{period}-12-31"

    report: dict[str, Any] = {
        "pdf_path": str(pdf_path),
        "security_id": security_id,
        "issuer_id": issuer_id,
        "period": period,
        "as_of": as_of,
        "document_id": document_id,
        "holders": 0,
        "subsidiaries": 0,
        "listed_control": 0,
        "skipped": [],
        "page_hits": {},
        "corpus_path": None,
        "warehouse": {},
        "dry_run": dry_run,
    }
    if not Path(pdf_path).is_file():
        report["skipped"].append("pdf_missing")
        return report

    result: EquityExtractResult = extract_equity_from_pdf(
        Path(pdf_path),
        security_id=security_id,
        issuer_id=issuer_id,
        document_id=document_id,
        period=period,
        as_of=as_of,
        collected_at=collected_at,
        issuer_name=issuer_name,
    )
    report["holders"] = len(result.holders)
    report["subsidiaries"] = len(result.subsidiaries)
    report["listed_control"] = len(result.listed_control)
    report["skipped"] = list(result.skipped)
    report["page_hits"] = dict(result.page_hits)

    if dry_run:
        return report

    record = {
        "issuer_id": issuer_id,
        "issuer_name": issuer_name,
        "security_id": security_id,
        "exchange": exchange or (security_id.split(":", 1)[0] if ":" in security_id else ""),
        "code": code or (security_id.split(":", 1)[-1] if ":" in security_id else ""),
        "period": period,
        "scope": "consolidated",
        "document_id": document_id,
        "document_date": document_date,
        "source": {
            "equity_feed": "annual_pdf",
            "title": title,
            "page_hits": result.page_hits,
        },
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
            for h in result.holders
        ],
        "subsidiaries": [
            {
                "name": s.get("name", ""),
                "direct_pct": s.get("direct_pct", ""),
                "consolidated": s.get("consolidated", ""),
                "main_business": s.get("main_business", ""),
                "document_id": s.get("document_id", document_id),
            }
            for s in result.subsidiaries
        ],
        "listed_control": [
            {
                "as_of": c.get("as_of", ""),
                "hop": c.get("hop", ""),
                "src_name": c.get("src_name", ""),
                "dst_name": c.get("dst_name", ""),
                "ratio": c.get("ratio", ""),
                "ratio_kind": c.get("ratio_kind", ""),
                "is_concert_party": c.get("is_concert_party", ""),
                "endpoint_type": c.get("endpoint_type", ""),
                "document_id": c.get("document_id", document_id),
            }
            for c in result.listed_control
        ],
        "facts": [],
        "segments": [],
    }
    if corpus_dir is not None:
        report["corpus_path"] = str(write_equity_corpus_record(Path(corpus_dir), record))
    if warehouse_dir is not None:
        report["warehouse"] = upsert_equity_to_warehouse(
            Path(warehouse_dir),
            holders=result.holders,
            subsidiaries=result.subsidiaries,
            listed_control=result.listed_control,
        )
    return report
