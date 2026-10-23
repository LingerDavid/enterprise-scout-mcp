"""Sample listed disclosure: cninfo PDF + equity extract (F10 holders fallback).

Facts (P&L / BS / CF) stay on the tradecraft financials path.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import httpx

from enterprise_scout_mcp.integrations.listed_equity_extract import (
    edges_from_equity_extract,
    upsert_annual_edges_to_warehouse,
    upsert_equity_to_warehouse,
    write_equity_corpus_record,
)
from enterprise_scout_mcp.output.listed_schema import identity_row
from enterprise_scout_mcp.output.listed_writer import append_listed_rows
from enterprise_scout_mcp.sources.annual_equity_pdf import (
    extract_equity_from_pdf,
    period_from_annual_meta,
)
from enterprise_scout_mcp.sources.cninfo import (
    CATEGORY_ANNUAL,
    download_pdf,
    pick_annual_report,
    query_announcements,
    resolve_listing,
)
from enterprise_scout_mcp.sources.eastmoney_company import fetch_company_profile
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
    prospectus_fallback: bool = True,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Index annual report + PDF equity extract; F10 holders if PDF extract misses.

    When annual PDF has no named suppliers, optionally fall back to 招股说明书.
    """
    collected_at = datetime.now(timezone.utc).isoformat()
    listing = resolve_listing(symbol_or_security)
    report: dict[str, Any] = {
        "input": symbol_or_security,
        "security_id": "",
        "announcements": 0,
        "picked": None,
        "pdf_path": None,
        "holders": 0,
        "subsidiaries": 0,
        "listed_control": 0,
        "suppliers": 0,
        "investments": 0,
        "edges": 0,
        "issuer_id": "",
        "issuer_name": "",
        "period": "",
        "corpus_path": None,
        "equity_extract": None,
        "prospectus_fallback": None,
        "dry_run": dry_run,
        "skipped": [],
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
    if not credit_code:
        report["skipped"].append("no_credit_code")

    anns = query_announcements(
        security_id,
        category=CATEGORY_ANNUAL,
        client=client,
    )
    report["announcements"] = len(anns)
    picked = pick_annual_report(anns, year=year)
    title = ""
    if picked is None:
        report["skipped"].append("no_annual_report")
    else:
        title = str(picked.title or "")
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
    period = period_from_annual_meta(title=title, document_date=document_date, year=year)
    report["period"] = period

    holders: list[dict[str, Any]] = []
    subsidiaries: list[dict[str, Any]] = []
    listed_control: list[dict[str, Any]] = []
    suppliers: list[dict[str, Any]] = []
    investments: list[dict[str, Any]] = []
    annual_edges: list[dict[str, Any]] = []
    holders_feed = "eastmoney_f10"

    pdf_path = Path(report["pdf_path"]) if report.get("pdf_path") else None
    if pdf_path is not None and pdf_path.is_file():
        as_of = (document_date or "")[:10] or (f"{period}-12-31" if period else "")
        extracted = extract_equity_from_pdf(
            pdf_path,
            security_id=security_id,
            issuer_id=issuer_id,
            document_id=document_id,
            period=period,
            as_of=as_of,
            collected_at=collected_at,
            issuer_name=issuer_name,
        )
        report["equity_extract"] = {
            "holders": len(extracted.holders),
            "subsidiaries": len(extracted.subsidiaries),
            "listed_control": len(extracted.listed_control),
            "suppliers": len(extracted.suppliers),
            "investments": len(extracted.investments),
            "skipped": list(extracted.skipped),
            "page_hits": dict(extracted.page_hits),
        }
        report["skipped"].extend(extracted.skipped)
        if extracted.holders:
            holders = extracted.holders
            holders_feed = "annual_pdf"
        subsidiaries = extracted.subsidiaries
        listed_control = extracted.listed_control
        suppliers = extracted.suppliers
        investments = extracted.investments
        annual_edges = edges_from_equity_extract(
            extracted,
            issuer_name=issuer_name,
            credit_code=credit_code,
            collected_at=collected_at,
        )
        report["subsidiaries"] = len(subsidiaries)
        report["listed_control"] = len(listed_control)
        report["suppliers"] = len(suppliers)
        report["investments"] = len(investments)
        report["edges"] = len(annual_edges)

    if not holders:
        # Do not stamp cninfo document_id onto F10 rows.
        holders = fetch_top_holders(
            security_id,
            document_id="",
            collected_at=collected_at,
            client=client,
        )
        holders_feed = "eastmoney_f10"
    report["holders"] = len(holders)
    if not holders:
        report["skipped"].append("no_holders")

    record: dict[str, Any] = {
        "issuer_id": issuer_id,
        "issuer_name": issuer_name,
        "security_id": security_id,
        "exchange": exchange,
        "code": code,
        "csrc_industry_l1": str(profile.get("csrc_industry_l1") or ""),
        "csrc_industry_l2": str(profile.get("csrc_industry_l2") or ""),
        "period": period,
        "scope": "consolidated",
        "document_id": document_id,
        "document_date": document_date,
        "source": {
            "cninfo": report["picked"],
            "holders_feed": holders_feed,
            "equity_feed": "annual_pdf" if holders_feed == "annual_pdf" else "",
            "identity_feed": "eastmoney_company_survey",
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
                "document_id": h.get("document_id", ""),
            }
            for h in holders
        ],
        "subsidiaries": [
            {
                "name": s.get("name", ""),
                "direct_pct": s.get("direct_pct", ""),
                "consolidated": s.get("consolidated", ""),
                "main_business": s.get("main_business", ""),
                "document_id": s.get("document_id", document_id),
            }
            for s in subsidiaries
        ],
        "suppliers": [
            {
                "rank": s.get("rank", ""),
                "name": s.get("name", ""),
                "purchase_pct": s.get("purchase_pct", ""),
                "purchase_amount": s.get("purchase_amount", ""),
                "document_id": s.get("document_id", document_id),
            }
            for s in suppliers
        ],
        "investments": [
            {
                "name": s.get("name", ""),
                "direct_pct": s.get("direct_pct", ""),
                "main_business": s.get("main_business", ""),
                "document_id": s.get("document_id", document_id),
            }
            for s in investments
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
            for c in listed_control
        ],
    }

    if dry_run:
        return report

    corpus_dir = Path(corpus_dir)
    if (
        period
        or subsidiaries
        or listed_control
        or suppliers
        or investments
        or holders_feed == "annual_pdf"
    ):
        report["corpus_path"] = str(write_equity_corpus_record(corpus_dir, record))
    else:
        corpus_dir.mkdir(parents=True, exist_ok=True)
        corpus_path = corpus_dir / f"{code}.jsonl"
        with corpus_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        report["corpus_path"] = str(corpus_path)

    if warehouse_dir is not None:
        identity = [
            identity_row(
                issuer_id=issuer_id,
                issuer_name=issuer_name,
                security_id=security_id,
                exchange=exchange,
                code=code,
                csrc_industry_l1=str(profile.get("csrc_industry_l1") or ""),
                csrc_industry_l2=str(profile.get("csrc_industry_l2") or ""),
                document_id=document_id,
                collected_at=collected_at,
                is_primary_listing="true",
            )
        ]
        append_listed_rows(Path(warehouse_dir), "identity", identity)
        upsert_equity_to_warehouse(
            Path(warehouse_dir),
            holders=holders,
            subsidiaries=subsidiaries,
            listed_control=listed_control,
        )
        if issuer_name and annual_edges:
            upsert_annual_edges_to_warehouse(
                Path(warehouse_dir),
                issuer_name=issuer_name,
                edges=annual_edges,
            )

    if (
        prospectus_fallback
        and not dry_run
        and not suppliers
        and download
    ):
        from enterprise_scout_mcp.integrations.listed_prospectus import (
            maybe_fallback_prospectus_suppliers,
        )

        fb = maybe_fallback_prospectus_suppliers(
            symbol_or_security=symbol_or_security,
            annual_suppliers=suppliers,
            corpus_dir=Path(corpus_dir),
            warehouse_dir=warehouse_dir,
            pdf_dir=pdf_dir,
            client=client,
            enabled=True,
        )
        if fb is not None:
            report["prospectus_fallback"] = {
                "suppliers": fb.get("suppliers", 0),
                "edges": fb.get("edges", 0),
                "document_id": (fb.get("picked") or {}).get("document_id"),
                "skipped": fb.get("skipped") or [],
                "corpus_path": fb.get("corpus_path"),
            }
            if fb.get("suppliers"):
                report["suppliers"] = int(fb.get("suppliers") or 0)

    return report


def symbols_from_instruments_parquet(path: Path) -> list[str]:
    """Read tradecraft-style instruments parquet → ``600519.SH`` list."""
    import pyarrow.parquet as pq

    table = pq.read_table(Path(path))
    names = set(table.column_names)
    if "symbol" not in names:
        return []
    symbols = [str(s).strip().upper() for s in table.column("symbol").to_pylist() if s]
    if "type" in names:
        types = table.column("type").to_pylist()
        symbols = [
            sym
            for sym, typ in zip(symbols, types)
            if str(typ or "").strip().lower() in {"", "stock"}
        ]
    # Keep A-share suffixes only.
    out: list[str] = []
    seen: set[str] = set()
    for sym in symbols:
        if not (sym.endswith(".SH") or sym.endswith(".SZ") or sym.endswith(".BJ")):
            continue
        if sym in seen:
            continue
        seen.add(sym)
        out.append(sym)
    return out


def symbols_from_text_file(path: Path) -> list[str]:
    """One symbol or security_id per non-empty, non-# line."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key = line.upper() if "." in line else line
        if key in seen:
            continue
        seen.add(key)
        out.append(line)
    return out


def load_progress_ok_symbols(progress_path: Path) -> set[str]:
    """Symbols marked ok=true in a JSONL progress file (last write wins)."""
    path = Path(progress_path)
    if not path.is_file():
        return set()
    ok: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        sym = str(row.get("symbol") or "").strip().upper()
        if not sym:
            continue
        if row.get("ok") is True:
            ok.add(sym)
        elif row.get("ok") is False:
            ok.discard(sym)
    return ok


def corpus_has_annual_pdf(corpus_dir: Path, symbol_or_security: str) -> bool:
    """True when corpus JSONL already points at an on-disk cninfo annual PDF."""
    listing = resolve_listing(symbol_or_security)
    if listing is None:
        return False
    _security_id, code, _column = listing
    corpus_path = Path(corpus_dir) / f"{code}.jsonl"
    if not corpus_path.is_file():
        return False
    pdf_root = Path(corpus_dir) / "pdf"
    try:
        lines = corpus_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        doc = str(rec.get("document_id") or "")
        if not doc.startswith("cninfo:"):
            continue
        ann_id = doc.split(":", 1)[1].strip()
        if not ann_id:
            continue
        pdf = pdf_root / f"{ann_id}.pdf"
        if pdf.is_file() and pdf.stat().st_size > 0:
            return True
    return False


def _sample_ok(report: dict[str, Any], *, download: bool) -> bool:
    if report.get("dry_run"):
        return bool(report.get("picked"))
    if download:
        return bool(report.get("pdf_path"))
    return bool(report.get("picked"))


def batch_sample_listed_disclosure(
    symbols: Iterable[str],
    *,
    corpus_dir: Path,
    warehouse_dir: Path | None = None,
    pdf_dir: Path | None = None,
    progress_path: Path,
    year: str | int | None = None,
    download: bool = True,
    delay_seconds: float = 1.5,
    limit: int = 0,
    skip_existing_corpus: bool = True,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Download missing annual PDFs + holders for many listings; resume via progress JSONL."""
    corpus_dir = Path(corpus_dir)
    progress_path = Path(progress_path)
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    already_ok = load_progress_ok_symbols(progress_path)

    pending: list[str] = []
    skipped_existing = 0
    for raw in symbols:
        sym = str(raw or "").strip()
        if not sym:
            continue
        key = sym.upper() if "." in sym else sym
        if key in already_ok or sym.upper() in already_ok:
            continue
        if skip_existing_corpus and corpus_has_annual_pdf(corpus_dir, sym):
            skipped_existing += 1
            with progress_path.open("a", encoding="utf-8") as fh:
                fh.write(
                    json.dumps(
                        {
                            "symbol": key if "." in sym else sym,
                            "ok": True,
                            "skipped": ["already_in_corpus"],
                            "ts": datetime.now(timezone.utc).isoformat(),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
            continue
        pending.append(sym)

    if limit > 0:
        pending = pending[:limit]

    summary: dict[str, Any] = {
        "universe_pending": len(pending),
        "already_ok": len(already_ok),
        "skipped_existing_corpus": skipped_existing,
        "ok": 0,
        "failed": 0,
        "limit": limit,
        "delay_seconds": delay_seconds,
        "year": year,
        "progress_path": str(progress_path),
    }

    own = client is None
    http = client or httpx.Client(timeout=60.0, headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True)
    try:
        for idx, sym in enumerate(pending, start=1):
            try:
                report = sample_listed_disclosure(
                    sym,
                    corpus_dir=corpus_dir,
                    warehouse_dir=warehouse_dir,
                    pdf_dir=pdf_dir,
                    year=year,
                    download=download,
                    dry_run=False,
                    client=http,
                )
            except Exception as exc:  # noqa: BLE001 — batch must continue
                report = {
                    "input": sym,
                    "skipped": [f"exception:{type(exc).__name__}:{exc}"],
                    "pdf_path": None,
                    "picked": None,
                    "holders": 0,
                }
            ok = _sample_ok(report, download=download)
            row = {
                "symbol": str(sym).strip().upper() if "." in str(sym) else str(sym).strip(),
                "ok": ok,
                "security_id": report.get("security_id"),
                "document_id": (report.get("picked") or {}).get("document_id")
                if isinstance(report.get("picked"), dict)
                else None,
                "pdf_path": report.get("pdf_path"),
                "holders": report.get("holders", 0),
                "skipped": report.get("skipped") or [],
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            with progress_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            if ok:
                summary["ok"] += 1
            else:
                summary["failed"] += 1
            if idx < len(pending) and delay_seconds > 0:
                time.sleep(delay_seconds)
    finally:
        if own:
            http.close()

    summary["finished"] = True
    return summary
