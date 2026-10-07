"""EnterpriseLake warehouse/entities row shape."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from enterprise_scout_mcp.models import CollectResult


def entity_row(result: CollectResult) -> dict[str, Any]:
    """Normalize collect result to EnterpriseLake entities/part.parquet columns."""
    data = result.data or {}
    name = str(data.get("company_name") or data.get("name") or result.task.keyword)
    former = str(data.get("former_name") or "")
    entity_id = str(
        data.get("aiqicha_id")
        or data.get("entity_id")
        or data.get("nameId")
        or ""
    )
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
    }
