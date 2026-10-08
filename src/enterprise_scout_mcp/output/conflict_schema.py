"""Registry field conflicts between L1 official and L2 commercial snapshots."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from enterprise_scout_mcp.models import CollectResult, ResultGrade
from enterprise_scout_mcp.output.entity_schema import _CREDIT_KEYS, _NAME_KEYS, _first_info, _pick

CONFLICT_COLUMNS = (
    "query_keyword",
    "field",
    "l1_value",
    "l2_value",
    "l1_grade",
    "l2_grade",
    "l1_channel",
    "l2_channel",
    "platform",
    "collected_at",
    "message",
)

_COMPARE_FIELDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("credit_code", _CREDIT_KEYS),
    ("name", _NAME_KEYS),
)


def _identity(data: dict[str, Any]) -> dict[str, str]:
    nested = _first_info(data) if isinstance(data, dict) else {}
    sources = [data, nested] if isinstance(data, dict) else [nested]
    out: dict[str, str] = {}
    for field, keys in _COMPARE_FIELDS:
        val = _pick(sources, keys)
        if val:
            out[field] = val
    return out


def detect_registry_conflicts(l1: CollectResult, l2: CollectResult) -> list[dict[str, Any]]:
    """Return conflict rows when both tiers have values for the same field but they differ."""
    id1 = _identity(l1.data or {})
    id2 = _identity(l2.data or {})
    if not id1 or not id2:
        return []

    ts = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    for field, _keys in _COMPARE_FIELDS:
        v1 = id1.get(field, "")
        v2 = id2.get(field, "")
        if not v1 or not v2:
            continue
        if v1.strip() == v2.strip():
            continue
        rows.append(
            {
                "query_keyword": l2.task.keyword,
                "field": field,
                "l1_value": v1,
                "l2_value": v2,
                "l1_grade": l1.grade.value,
                "l2_grade": l2.grade.value,
                "l1_channel": l1.channel.value,
                "l2_channel": l2.channel.value,
                "platform": l2.task.platform.value,
                "collected_at": ts,
                "message": f"L1/L2 mismatch on {field}",
            }
        )
    return rows
