"""Warehouse supplements for L3 / judicial corpus hits."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from enterprise_scout_mcp.models import CollectResult, Dimension

SUPPLEMENT_COLUMNS = (
    "query_keyword",
    "dimension",
    "source_tier",
    "source_channel",
    "corpus_file",
    "grade",
    "persona_id",
    "collected_at",
    "payload_json",
    "message",
)


def _corpus_payload(result: CollectResult) -> tuple[str, dict[str, Any]] | None:
    data = result.data or {}
    if not isinstance(data, dict):
        return None
    if isinstance(data.get("academic"), dict):
        return "l3", data["academic"]
    if isinstance(data.get("judicial"), dict):
        return "judicial", data["judicial"]
    return None


def supplement_row(result: CollectResult) -> dict[str, Any] | None:
    hit = _corpus_payload(result)
    if hit is None:
        return None
    bucket, record = hit
    corpus_meta = (result.data or {}).get("corpus") if isinstance(result.data, dict) else {}
    corpus_file = ""
    if isinstance(corpus_meta, dict):
        corpus_file = str(corpus_meta.get("source_file") or "")
    dim = result.dimension.value if result.dimension else bucket
    tier = result.source_tier.value if result.source_tier else ""
    return {
        "query_keyword": result.task.keyword,
        "dimension": dim,
        "source_tier": tier or ("l3" if bucket == "l3" else "l2"),
        "source_channel": result.channel.value,
        "corpus_file": corpus_file,
        "grade": result.grade.value,
        "persona_id": result.persona_id,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "payload_json": json.dumps(record, ensure_ascii=False),
        "message": result.message or "",
    }
