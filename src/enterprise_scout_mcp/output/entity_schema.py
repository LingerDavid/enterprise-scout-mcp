"""EnterpriseLake warehouse/entities row shape."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from enterprise_scout_mcp.models import CollectResult

ENTITY_COLUMNS = (
    "entity_id",
    "name",
    "former_name",
    "platform",
    "source_channel",
    "query_keyword",
    "grade",
    "persona_id",
    "collected_at",
    "payload_json",
    "message",
)

# ENScan ENSMapLN + legacy / Playwright keys.
_NAME_KEYS = (
    "company_name",
    "name",
    "entName",
    "企业名称",
)
_ID_KEYS = (
    "aiqicha_id",
    "entity_id",
    "nameId",
    "pid",
    "PID",
)
_FORMER_KEYS = ("former_name", "曾用名")


def _first_info(data: dict[str, Any]) -> dict[str, Any]:
    """Flatten ENScan nested enterprise_info[0] into a lookup dict."""
    info = data.get("enterprise_info")
    if isinstance(info, list) and info and isinstance(info[0], dict):
        return info[0]
    if isinstance(info, dict):
        return info
    return {}


def _pick(sources: list[dict[str, Any]], keys: tuple[str, ...]) -> str:
    for src in sources:
        for k in keys:
            if k in src and src[k]:
                return str(src[k]).strip()
    return ""


def entity_row(result: CollectResult) -> dict[str, Any]:
    """Normalize collect result to EnterpriseLake entities/part.parquet columns."""
    data = result.data or {}
    nested = _first_info(data) if isinstance(data, dict) else {}
    sources = [data, nested] if isinstance(data, dict) else [nested]

    name = _pick(sources, _NAME_KEYS) or result.task.keyword
    former = _pick(sources, _FORMER_KEYS)
    entity_id = _pick(sources, _ID_KEYS)

    return {
        "entity_id": entity_id,
        "name": name,
        "former_name": former,
        "platform": result.task.platform.value,
        "source_channel": result.channel.value,
        "query_keyword": result.task.keyword,
        "grade": result.grade.value,
        "persona_id": result.persona_id,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "payload_json": json.dumps(data, ensure_ascii=False),
        "message": result.message or "",
    }
