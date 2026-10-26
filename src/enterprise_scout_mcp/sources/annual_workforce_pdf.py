"""Extract employee education mix from annual-report page text."""

from __future__ import annotations

import re
from typing import Any

from enterprise_scout_mcp.output.listed_schema import workforce_education_row

# Common annual-report phrasing for 东方雨虹-style education donuts.
_BUCKET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("master_plus", re.compile(r"硕士(?:及|及以)?上\s*([\d.]+)\s*%")),
    ("bachelor", re.compile(r"本科\s*([\d.]+)\s*%")),
    ("college_below", re.compile(r"专科(?:及|及以)?下\s*([\d.]+)\s*%")),
    ("other", re.compile(r"其他\s*([\d.]+)\s*%")),
)

# Section gate — avoid matching random percentages elsewhere.
_SECTION_HINT = re.compile(
    r"员工(?:的)?(?:专业|学历|教育)结构|学历结构|员工情况",
    re.I,
)


def education_buckets_from_pages(pages: list[str], *, issuer_id: str, as_of: str, document_id: str, collected_at: str) -> list[dict[str, Any]]:
    """Parse education percentage buckets from annual-report text pages."""
    if not pages or not issuer_id or not as_of:
        return []
    text = "\n".join(pages)
    if not _SECTION_HINT.search(text):
        return []
    rows: list[dict[str, Any]] = []
    for bucket, pattern in _BUCKET_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        rows.append(
            workforce_education_row(
                issuer_id=issuer_id,
                as_of=as_of,
                bucket=bucket,
                pct=match.group(1),
                document_id=document_id,
                collected_at=collected_at,
            )
        )
    return rows
