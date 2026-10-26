"""Run annual-report equity extract and upsert into corpus + warehouse."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from enterprise_scout_mcp.output.edge_schema import edge_row
from enterprise_scout_mcp.output.edge_writer import replace_edges_for_source
from enterprise_scout_mcp.output.listed_writer import replace_listed_rows
from enterprise_scout_mcp.sources.annual_equity_pdf import (
    EquityExtractResult,
    extract_equity_from_pdf,
    period_from_annual_meta,
)

HOLDERS_MATCH_KEYS = ("security_id", "as_of")
SUBSIDIARIES_MATCH_KEYS = ("issuer_id", "period", "document_id")
CONTROL_MATCH_KEYS = ("issuer_id", "as_of", "document_id")

ANNUAL_PDF_CHANNEL = "annual_pdf"
PROSPECTUS_PDF_CHANNEL = "prospectus_pdf"
ANNUAL_PDF_PLATFORM = "cninfo"


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
    workforce_education: list[dict[str, Any]] | None = None,
) -> dict[str, str | None]:
    """Idempotent replace into listed parquet tables."""
    wh = Path(warehouse_dir)
    paths: dict[str, str | None] = {
        "holders": None,
        "subsidiaries": None,
        "listed_control": None,
        "workforce_education": None,
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
    if workforce_education:
        p = replace_listed_rows(
            wh,
            "workforce_education",
            workforce_education,
            match_keys=("issuer_id", "as_of", "bucket"),
        )
        paths["workforce_education"] = str(p) if p else None
    return paths


def edges_from_equity_extract(
    result: EquityExtractResult,
    *,
    issuer_name: str,
    credit_code: str = "",
    collected_at: str = "",
    source_channel: str = ANNUAL_PDF_CHANNEL,
    include: frozenset[str] | None = None,
) -> list[dict[str, Any]]:
    """Map PDF extract rows → ``edges/equity`` shape for the lake graph.

    Directions match ENScan extract: holder→issuer, issuer→investee/supplier.
    ``include`` limits sections: ``holders`` / ``subsidiaries`` / ``investments`` /
    ``suppliers`` (default: all present).
    """
    root = str(issuer_name or "").strip()
    if not root:
        return []
    want = include or frozenset({"holders", "subsidiaries", "investments", "suppliers"})
    channel = str(source_channel or ANNUAL_PDF_CHANNEL).strip() or ANNUAL_PDF_CHANNEL
    ts = collected_at or datetime.now(timezone.utc).isoformat()
    code = str(credit_code or "").strip()
    edges: list[dict[str, Any]] = []

    if "holders" in want:
        for h in result.holders:
            name = str(h.get("holder_name") or "").strip()
            if not name:
                continue
            pct = str(h.get("pct_total") or "").strip()
            ratio = f"{pct}%" if pct and "%" not in pct else pct
            edges.append(
                edge_row(
                    src_name=name,
                    dst_name=root,
                    relation="holder",
                    ratio=ratio,
                    section="holders",
                    platform=ANNUAL_PDF_PLATFORM,
                    source_channel=channel,
                    query_keyword=root,
                    collected_at=ts,
                    credit_code=code,
                    payload_json=json.dumps(h, ensure_ascii=False),
                )
            )

    if "subsidiaries" in want:
        for s in result.subsidiaries:
            name = str(s.get("name") or "").strip()
            if not name:
                continue
            pct = str(s.get("direct_pct") or "").strip()
            ratio = f"{pct}%" if pct and "%" not in pct else pct
            edges.append(
                edge_row(
                    src_name=root,
                    dst_name=name,
                    relation="invest",
                    ratio=ratio,
                    section="subsidiaries",
                    platform=ANNUAL_PDF_PLATFORM,
                    source_channel=channel,
                    query_keyword=root,
                    collected_at=ts,
                    credit_code=code,
                    payload_json=json.dumps(s, ensure_ascii=False),
                )
            )

    if "investments" in want:
        for inv in result.investments:
            name = str(inv.get("name") or "").strip()
            if not name:
                continue
            pct = str(inv.get("direct_pct") or "").strip()
            ratio = f"{pct}%" if pct and "%" not in pct else pct
            edges.append(
                edge_row(
                    src_name=root,
                    dst_name=name,
                    relation="invest",
                    ratio=ratio,
                    section="investments",
                    platform=ANNUAL_PDF_PLATFORM,
                    source_channel=channel,
                    query_keyword=root,
                    collected_at=ts,
                    credit_code=code,
                    payload_json=json.dumps(inv, ensure_ascii=False),
                )
            )

    if "suppliers" in want:
        for sup in result.suppliers:
            name = str(sup.get("name") or "").strip()
            if not name:
                continue
            pct = str(sup.get("purchase_pct") or "").strip()
            ratio = f"{pct}%" if pct and "%" not in pct else pct
            edges.append(
                edge_row(
                    src_name=root,
                    dst_name=name,
                    relation="supply",
                    ratio=ratio,
                    section="suppliers",
                    platform=ANNUAL_PDF_PLATFORM,
                    source_channel=channel,
                    query_keyword=root,
                    collected_at=ts,
                    credit_code=code,
                    payload_json=json.dumps(sup, ensure_ascii=False),
                )
            )

    return edges


def upsert_filing_edges_to_warehouse(
    warehouse_dir: Path,
    *,
    issuer_name: str,
    edges: list[dict[str, Any]],
    source_channel: str = ANNUAL_PDF_CHANNEL,
) -> str | None:
    """Replace prior edges for (issuer, source_channel), then write ``edges``."""
    root = str(issuer_name or "").strip()
    channel = str(source_channel or "").strip()
    if not root or not channel:
        return None
    path = replace_edges_for_source(
        Path(warehouse_dir),
        edges,
        query_keyword=root,
        source_channel=channel,
    )
    return str(path) if path else None


def upsert_annual_edges_to_warehouse(
    warehouse_dir: Path,
    *,
    issuer_name: str,
    edges: list[dict[str, Any]],
) -> str | None:
    """Replace prior annual_pdf edges for this issuer, then write ``edges``."""
    return upsert_filing_edges_to_warehouse(
        warehouse_dir,
        issuer_name=issuer_name,
        edges=edges,
        source_channel=ANNUAL_PDF_CHANNEL,
    )


def _pdf_for_corpus_record(corpus_dir: Path, record: dict[str, Any]) -> Path | None:
    doc = str(record.get("document_id") or "").strip()
    if not doc.startswith("cninfo:"):
        return None
    ann_id = doc.split(":", 1)[1].strip()
    if not ann_id:
        return None
    pdf = Path(corpus_dir) / "pdf" / f"{ann_id}.pdf"
    if pdf.is_file() and pdf.stat().st_size > 0:
        return pdf
    return None


def _load_jsonl_records(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return out
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def iter_listed_equity_corpus_records(corpus_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    """Load equity corpus: ``{code}.{period}.json`` plus latest row per ``{code}.jsonl``.

    For JSONL, keep the last row that has a ``cninfo:`` document_id (else last row).
    """
    root = Path(corpus_dir)
    if not root.is_dir():
        return []
    out: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(root.glob("*.json")):
        if path.name.startswith("_"):
            continue
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(rec, dict):
            continue
        if not (rec.get("security_id") or rec.get("code")):
            continue
        out.append((path, rec))

    for path in sorted(root.glob("*.jsonl")):
        if path.name.startswith("_"):
            continue
        rows = _load_jsonl_records(path)
        if not rows:
            continue
        picked: dict[str, Any] | None = None
        for rec in rows:
            doc = str(rec.get("document_id") or "")
            if doc.startswith("cninfo:"):
                picked = rec
        if picked is None:
            picked = rows[-1]
        if not (picked.get("security_id") or picked.get("code")):
            continue
        out.append((path, picked))
    return out


def batch_reextract_listed_equity(
    corpus_dir: Path,
    *,
    warehouse_dir: Path | None = None,
    progress_path: Path,
    limit: int = 0,
    skip_ok: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Re-extract suppliers/invest/holders from on-disk annual PDFs into the lake."""
    corpus_dir = Path(corpus_dir)
    progress_path = Path(progress_path)
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    already = set()
    if skip_ok and progress_path.is_file():
        for raw in progress_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = str(row.get("document_id") or row.get("code") or "").strip()
            if key and row.get("ok") is True:
                already.add(key)

    pending: list[tuple[Path, dict[str, Any], Path]] = []
    skipped_no_pdf = 0
    for _json_path, rec in iter_listed_equity_corpus_records(corpus_dir):
        doc_id = str(rec.get("document_id") or "").strip()
        code = str(rec.get("code") or "").strip()
        key = doc_id or code
        if key and key in already:
            continue
        pdf = _pdf_for_corpus_record(corpus_dir, rec)
        if pdf is None:
            skipped_no_pdf += 1
            continue
        pending.append((_json_path, rec, pdf))

    if limit > 0:
        pending = pending[:limit]

    summary: dict[str, Any] = {
        "pending": len(pending),
        "already_ok": len(already),
        "skipped_no_pdf": skipped_no_pdf,
        "ok": 0,
        "failed": 0,
        "suppliers": 0,
        "investments": 0,
        "edges": 0,
        "limit": limit,
        "dry_run": dry_run,
        "progress_path": str(progress_path),
    }

    for _json_path, rec, pdf in pending:
        security_id = str(rec.get("security_id") or "").strip()
        code = str(rec.get("code") or "").strip()
        if not security_id and code:
            # Best-effort: prefer SSE for 6xxxxx, SZSE for 0/3.
            if code.startswith("6"):
                security_id = f"SSE:{code}"
            elif code.startswith(("0", "3")):
                security_id = f"SZSE:{code}"
            else:
                security_id = f"BSE:{code}"
        report = extract_and_store_equity(
            pdf,
            security_id=security_id,
            issuer_id=str(rec.get("issuer_id") or security_id),
            issuer_name=str(rec.get("issuer_name") or ""),
            exchange=str(rec.get("exchange") or ""),
            code=code,
            document_id=str(rec.get("document_id") or f"local:{pdf.name}"),
            document_date=str(rec.get("document_date") or ""),
            title=str((rec.get("source") or {}).get("title") or "")
            if isinstance(rec.get("source"), dict)
            else "",
            year=str(rec.get("period") or "") or None,
            corpus_dir=None if dry_run else corpus_dir,
            warehouse_dir=None if dry_run else warehouse_dir,
            dry_run=dry_run,
        )
        ok = bool(
            report.get("holders")
            or report.get("subsidiaries")
            or report.get("suppliers")
            or report.get("investments")
            or report.get("edges")
        )
        row = {
            "code": code,
            "security_id": security_id,
            "document_id": report.get("document_id"),
            "ok": ok,
            "holders": report.get("holders", 0),
            "subsidiaries": report.get("subsidiaries", 0),
            "suppliers": report.get("suppliers", 0),
            "investments": report.get("investments", 0),
            "edges": report.get("edges", 0),
            "skipped": report.get("skipped") or [],
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        with progress_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        if ok:
            summary["ok"] += 1
            summary["suppliers"] += int(report.get("suppliers") or 0)
            summary["investments"] += int(report.get("investments") or 0)
            summary["edges"] += int(report.get("edges") or 0)
        else:
            summary["failed"] += 1

    summary["finished"] = True
    return summary


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
        "issuer_name": issuer_name,
        "period": period,
        "as_of": as_of,
        "document_id": document_id,
        "holders": 0,
        "subsidiaries": 0,
        "listed_control": 0,
        "suppliers": 0,
        "investments": 0,
        "edges": 0,
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
    report["suppliers"] = len(result.suppliers)
    report["investments"] = len(result.investments)
    report["skipped"] = list(result.skipped)
    report["page_hits"] = dict(result.page_hits)

    edges = edges_from_equity_extract(
        result,
        issuer_name=issuer_name,
        credit_code=issuer_id if issuer_id and not issuer_id.startswith(("SSE:", "SZSE:", "BSE:")) else "",
        collected_at=collected_at,
    )
    report["edges"] = len(edges)
    if not issuer_name and (
        result.suppliers or result.investments or result.subsidiaries or result.holders
    ):
        report["skipped"].append("no_issuer_name_for_edges")

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
        "suppliers": [
            {
                "rank": s.get("rank", ""),
                "name": s.get("name", ""),
                "purchase_pct": s.get("purchase_pct", ""),
                "purchase_amount": s.get("purchase_amount", ""),
                "document_id": s.get("document_id", document_id),
            }
            for s in result.suppliers
        ],
        "investments": [
            {
                "name": s.get("name", ""),
                "direct_pct": s.get("direct_pct", ""),
                "main_business": s.get("main_business", ""),
                "document_id": s.get("document_id", document_id),
            }
            for s in result.investments
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
        wh_paths = upsert_equity_to_warehouse(
            Path(warehouse_dir),
            holders=result.holders,
            subsidiaries=result.subsidiaries,
            listed_control=result.listed_control,
            workforce_education=result.workforce_education,
        )
        edge_path = upsert_annual_edges_to_warehouse(
            Path(warehouse_dir),
            issuer_name=issuer_name,
            edges=edges,
        )
        wh_paths["edges"] = edge_path
        report["warehouse"] = wh_paths
    return report
