"""Import pre-extracted listed-company JSON/JSONL into warehouse listed tables."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from enterprise_scout_mcp.output.listed_schema import (
    facts_row,
    identity_row,
    segments_row,
)
from enterprise_scout_mcp.output.listed_writer import append_listed_rows


def _iter_records(path: Path) -> Iterator[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                yield row
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if isinstance(data, list):
        for row in data:
            if isinstance(row, dict):
                yield row
    elif isinstance(data, dict):
        rows = data.get("records") or data.get("items")
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    yield row
        else:
            yield data


def record_to_rows(record: dict[str, Any], *, collected_at: str) -> dict[str, list[dict[str, Any]]]:
    """Split one corpus record into identity / facts / segments rows."""
    issuer_id = str(record.get("issuer_id") or record.get("credit_code") or "").strip()
    security_id = str(record.get("security_id") or "").strip()
    exchange = str(record.get("exchange") or "").strip().upper()
    code = str(record.get("code") or "").strip()
    if not security_id and exchange and code:
        security_id = f"{exchange}:{code}"
    if ":" in security_id and (not exchange or not code):
        exchange, code = security_id.split(":", 1)

    document_id = str(record.get("document_id") or "").strip()
    document_date = str(record.get("document_date") or "").strip()
    period = str(record.get("period") or "").strip()
    scope = str(record.get("scope") or "consolidated").strip() or "consolidated"

    identity: list[dict[str, Any]] = []
    if issuer_id and security_id:
        identity.append(
            identity_row(
                issuer_id=issuer_id,
                issuer_name=str(record.get("issuer_name") or record.get("name") or ""),
                security_id=security_id,
                exchange=exchange,
                code=code,
                board=str(record.get("board") or ""),
                csrc_industry_l1=str(record.get("csrc_industry_l1") or ""),
                csrc_industry_l2=str(record.get("csrc_industry_l2") or ""),
                list_date=str(record.get("list_date") or ""),
                is_primary_listing=str(record.get("is_primary_listing") or "true"),
                document_id=document_id,
                collected_at=collected_at,
            )
        )

    facts: list[dict[str, Any]] = []
    for fact in record.get("facts") or []:
        if not isinstance(fact, dict):
            continue
        item_code = str(fact.get("item_code") or "").strip()
        if not item_code or not issuer_id or not period:
            continue
        facts.append(
            facts_row(
                issuer_id=issuer_id,
                period=period,
                scope=str(fact.get("scope") or scope),
                statement=str(fact.get("statement") or "income"),
                item_code=item_code,
                label=str(fact.get("label") or ""),
                value=str(fact.get("value") or ""),
                unit=str(fact.get("unit") or "CNY"),
                currency=str(fact.get("currency") or "CNY"),
                scale_in_source=str(fact.get("scale_in_source") or ""),
                derived=str(fact.get("derived") or "false"),
                document_id=str(fact.get("document_id") or document_id),
                document_date=str(fact.get("document_date") or document_date),
                audit_opinion=str(fact.get("audit_opinion") or ""),
                collected_at=collected_at,
                supersedes_ref=str(fact.get("supersedes_ref") or ""),
            )
        )

    segments: list[dict[str, Any]] = []
    for seg in record.get("segments") or []:
        if not isinstance(seg, dict):
            continue
        name = str(seg.get("name") or "").strip()
        kind = str(seg.get("kind") or "").strip()
        if not name or not kind or not issuer_id or not period:
            continue
        segment_id = str(seg.get("segment_id") or f"{issuer_id}:{kind}:{name}")
        segments.append(
            segments_row(
                issuer_id=issuer_id,
                period=period,
                kind=kind,
                segment_id=segment_id,
                parent_segment_id=str(seg.get("parent_segment_id") or ""),
                name=name,
                revenue=str(seg.get("revenue") or ""),
                cost=str(seg.get("cost") or ""),
                comparable_flag=str(seg.get("comparable_flag") or "unknown"),
                document_id=str(seg.get("document_id") or document_id),
                collected_at=collected_at,
            )
        )

    return {"identity": identity, "facts": facts, "segments": segments}


def import_listed_corpus(
    corpus_dir: Path,
    warehouse_dir: Path,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Import all *.json / *.jsonl under corpus_dir into warehouse listed tables."""
    report: dict[str, Any] = {
        "corpus_dir": str(corpus_dir),
        "warehouse_dir": str(warehouse_dir),
        "files": 0,
        "records": 0,
        "identity": 0,
        "facts": 0,
        "segments": 0,
        "dry_run": dry_run,
        "skipped": [],
    }
    if not corpus_dir.is_dir():
        report["skipped"].append("corpus_dir_missing")
        return report

    collected_at = datetime.now(timezone.utc).isoformat()
    identity_rows: list[dict[str, Any]] = []
    facts_rows: list[dict[str, Any]] = []
    segment_rows: list[dict[str, Any]] = []

    paths = sorted(corpus_dir.glob("*.json")) + sorted(corpus_dir.glob("*.jsonl"))
    report["files"] = len(paths)
    for path in paths:
        if path.name.startswith("_example"):
            continue
        for record in _iter_records(path):
            report["records"] += 1
            parts = record_to_rows(record, collected_at=collected_at)
            if not parts["identity"] and not parts["facts"]:
                report["skipped"].append(f"{path.name}:no_identity_or_facts")
                continue
            identity_rows.extend(parts["identity"])
            facts_rows.extend(parts["facts"])
            segment_rows.extend(parts["segments"])

    report["identity"] = len(identity_rows)
    report["facts"] = len(facts_rows)
    report["segments"] = len(segment_rows)
    if dry_run:
        return report

    if identity_rows:
        append_listed_rows(warehouse_dir, "identity", identity_rows)
    if facts_rows:
        append_listed_rows(warehouse_dir, "facts", facts_rows)
    if segment_rows:
        append_listed_rows(warehouse_dir, "segments", segment_rows)
    return report
