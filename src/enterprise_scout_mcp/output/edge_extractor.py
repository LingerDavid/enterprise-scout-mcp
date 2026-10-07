"""Extract equity/invest edges from ENScan-style payload maps."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from enterprise_scout_mcp.models import CollectResult
from enterprise_scout_mcp.output.edge_schema import edge_row

NAME_KEYS = (
    "企业名称",
    "名称",
    "name",
    "被投资企业",
    "股东名称",
    "投资人",
    "投资机构",
    "子公司",
)
RATIO_KEYS = ("持股比例", "投资比例", "ratio", "比例", "占股比例", "scale")

SECTION_RELATION = {
    "invest": "invest",
    "partner": "holder",
    "stockholder": "holder",
    "holder": "holder",
    "股东": "holder",
    "branch": "branch",
}


def _pick(row: dict[str, Any], keys: tuple[str, ...]) -> str:
    for k in keys:
        if k in row and row[k]:
            return str(row[k]).strip()
    for k, v in row.items():
        if any(n in str(k) for n in keys):
            return str(v).strip()
    return ""


def extract_edges(result: CollectResult) -> list[dict[str, Any]]:
    data = result.data
    if not isinstance(data, dict):
        return []

    root = result.task.keyword
    ts = datetime.now(timezone.utc).isoformat()
    edges: list[dict[str, Any]] = []

    for section, rows in data.items():
        relation = SECTION_RELATION.get(str(section).lower())
        if not relation or not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = _pick(row, NAME_KEYS)
            if not name:
                continue
            ratio = _pick(row, RATIO_KEYS)
            if relation == "invest":
                src, dst = root, name
            elif relation == "holder":
                src, dst = name, root
            else:
                src, dst = root, name
            edges.append(
                edge_row(
                    src_name=src,
                    dst_name=dst,
                    relation=relation,
                    ratio=ratio,
                    section=str(section),
                    platform=result.task.platform.value,
                    source_channel=result.channel.value,
                    query_keyword=root,
                    collected_at=ts,
                    payload_json=json.dumps(row, ensure_ascii=False),
                )
            )
    return edges
