"""EnterpriseLake warehouse/edges/equity row shape."""

from __future__ import annotations

from typing import Any

EDGE_COLUMNS = (
    "src_name",
    "dst_name",
    "relation",
    "ratio",
    "section",
    "platform",
    "source_channel",
    "query_keyword",
    "collected_at",
    "payload_json",
)


def edge_row(
    *,
    src_name: str,
    dst_name: str,
    relation: str,
    ratio: str,
    section: str,
    platform: str,
    source_channel: str,
    query_keyword: str,
    collected_at: str,
    payload_json: str,
) -> dict[str, Any]:
    return {
        "src_name": src_name,
        "dst_name": dst_name,
        "relation": relation,
        "ratio": ratio,
        "section": section,
        "platform": platform,
        "source_channel": source_channel,
        "query_keyword": query_keyword,
        "collected_at": collected_at,
        "payload_json": payload_json,
    }
