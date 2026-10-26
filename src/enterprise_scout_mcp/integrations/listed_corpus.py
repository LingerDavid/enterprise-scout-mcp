"""Import pre-extracted listed-company JSON/JSONL into warehouse listed tables."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from enterprise_scout_mcp.integrations.listed_equity_extract import (
    CONTROL_MATCH_KEYS,
    HOLDERS_MATCH_KEYS,
    SUBSIDIARIES_MATCH_KEYS,
)
from enterprise_scout_mcp.output.listed_schema import (
    facts_row,
    holders_row,
    identity_row,
    listed_control_row,
    segments_row,
    subsidiaries_row,
)
from enterprise_scout_mcp.output.listed_writer import append_listed_rows, replace_listed_rows


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


def _as_row_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


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
    for fact in _as_row_list(record.get("facts")):
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
    for seg in _as_row_list(record.get("segments")):
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

    holders: list[dict[str, Any]] = []
    for holder in _as_row_list(record.get("holders")):
        holder_name = str(holder.get("holder_name") or holder.get("name") or "").strip()
        as_of = str(holder.get("as_of") or "").strip()
        if not holder_name or not security_id or not as_of:
            continue
        holders.append(
            holders_row(
                security_id=security_id,
                as_of=as_of,
                rank=str(holder.get("rank") or ""),
                holder_name=holder_name,
                holder_type=str(holder.get("holder_type") or ""),
                shares=str(holder.get("shares") or ""),
                pct_total=str(holder.get("pct_total") or ""),
                share_class=str(holder.get("share_class") or ""),
                pledge_pct_of_holding=str(holder.get("pledge_pct_of_holding") or ""),
                pledge_as_of=str(holder.get("pledge_as_of") or ""),
                freeze_flag=str(holder.get("freeze_flag") or ""),
                document_id=str(holder.get("document_id") or document_id),
                collected_at=collected_at,
            )
        )

    subsidiaries: list[dict[str, Any]] = []
    for sub in _as_row_list(record.get("subsidiaries")):
        name = str(sub.get("name") or "").strip()
        if not name or not issuer_id or not period:
            continue
        subsidiaries.append(
            subsidiaries_row(
                issuer_id=issuer_id,
                period=period,
                name=name,
                direct_pct=str(sub.get("direct_pct") or ""),
                consolidated=str(sub.get("consolidated") or "true"),
                main_business=str(sub.get("main_business") or ""),
                document_id=str(sub.get("document_id") or document_id),
                collected_at=collected_at,
            )
        )

    listed_control: list[dict[str, Any]] = []
    for hop in _as_row_list(record.get("listed_control")):
        src = str(hop.get("src_name") or "").strip()
        dst = str(hop.get("dst_name") or "").strip()
        as_of = str(hop.get("as_of") or document_date or "").strip()[:10]
        if not src or not dst or not issuer_id or not as_of:
            continue
        listed_control.append(
            listed_control_row(
                issuer_id=issuer_id,
                as_of=as_of,
                hop=str(hop.get("hop") or ""),
                src_name=src,
                dst_name=dst,
                ratio=str(hop.get("ratio") or ""),
                ratio_kind=str(hop.get("ratio_kind") or "ownership"),
                is_concert_party=str(hop.get("is_concert_party") or "false"),
                endpoint_type=str(hop.get("endpoint_type") or ""),
                document_id=str(hop.get("document_id") or document_id),
                collected_at=collected_at,
            )
        )

    return {
        "identity": identity,
        "facts": facts,
        "segments": segments,
        "holders": holders,
        "subsidiaries": subsidiaries,
        "listed_control": listed_control,
    }


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
        "holders": 0,
        "subsidiaries": 0,
        "listed_control": 0,
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
    holder_n = 0
    sub_n = 0
    control_n = 0
    equity_parts: list[dict[str, list[dict[str, Any]]]] = []

    paths = sorted(corpus_dir.glob("*.json")) + sorted(corpus_dir.glob("*.jsonl"))
    report["files"] = len(paths)
    for path in paths:
        if path.name.startswith("_example"):
            continue
        for record in _iter_records(path):
            report["records"] += 1
            parts = record_to_rows(record, collected_at=collected_at)
            if (
                not parts["identity"]
                and not parts["facts"]
                and not parts["holders"]
                and not parts["subsidiaries"]
                and not parts["listed_control"]
            ):
                report["skipped"].append(f"{path.name}:no_identity_or_facts")
                continue
            identity_rows.extend(parts["identity"])
            facts_rows.extend(parts["facts"])
            segment_rows.extend(parts["segments"])
            holder_n += len(parts["holders"])
            sub_n += len(parts["subsidiaries"])
            control_n += len(parts["listed_control"])
            if parts["holders"] or parts["subsidiaries"] or parts["listed_control"]:
                equity_parts.append(parts)

    report["identity"] = len(identity_rows)
    report["facts"] = len(facts_rows)
    report["segments"] = len(segment_rows)
    report["holders"] = holder_n
    report["subsidiaries"] = sub_n
    report["listed_control"] = control_n
    if dry_run:
        return report

    if identity_rows:
        append_listed_rows(warehouse_dir, "identity", identity_rows)
    if facts_rows:
        append_listed_rows(warehouse_dir, "facts", facts_rows)
    if segment_rows:
        append_listed_rows(warehouse_dir, "segments", segment_rows)
    # Per-record replace so later corpus files overwrite the same key cleanly.
    for parts in equity_parts:
        if parts["holders"]:
            replace_listed_rows(
                warehouse_dir,
                "holders",
                parts["holders"],
                match_keys=HOLDERS_MATCH_KEYS,
            )
        if parts["subsidiaries"]:
            replace_listed_rows(
                warehouse_dir,
                "subsidiaries",
                parts["subsidiaries"],
                match_keys=SUBSIDIARIES_MATCH_KEYS,
            )
        if parts["listed_control"]:
            replace_listed_rows(
                warehouse_dir,
                "listed_control",
                parts["listed_control"],
                match_keys=CONTROL_MATCH_KEYS,
            )
    return report
