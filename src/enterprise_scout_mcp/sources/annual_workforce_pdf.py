"""Extract employee education mix from annual-report page text."""

from __future__ import annotations

import re
from typing import Any

from enterprise_scout_mcp.output.listed_schema import workforce_education_row

# Percentage phrasing (East Money F10 donut / some annual reports).
_PCT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("master_plus", re.compile(r"硕士(?:研究生)?(?:及|及以)?上\s*([\d.]+)\s*%")),
    ("bachelor", re.compile(r"(?:大学)?本科\s*([\d.]+)\s*%")),
    ("college_below", re.compile(r"(?:大学)?专科(?:及|及以)?下\s*([\d.]+)\s*%")),
    ("other", re.compile(r"其他\s*([\d.]+)\s*%")),
)

# Headcount table (common in cninfo annual PDFs, e.g. 东方雨虹 2024).
_COUNT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("master_plus", re.compile(r"硕士(?:研究生)?(?:及以)?上[^\d\n]{0,40}([\d,]+)")),
    ("bachelor", re.compile(r"(?:大学)?本科[^\d\n]{0,40}([\d,]+)")),
    ("college_below", re.compile(r"(?:大学)?专科(?:及以)?下[^\d\n]{0,40}([\d,]+)")),
    ("other", re.compile(r"其他[^\d\n]{0,40}([\d,]+)")),
)

_SECTION_HINT = re.compile(
    r"员工(?:的)?(?:专业|学历|教育)结构|学历结构|教育程度类别|员工情况",
    re.I,
)

_CORE_BUCKETS = frozenset({"master_plus", "bachelor", "college_below"})


def _parse_count(raw: str) -> int:
    return int(str(raw or "").replace(",", "").strip() or "0")


def _pct_from_count(count: int, total: int) -> str:
    if total <= 0 or count < 0:
        return ""
    return f"{100.0 * count / total:.2f}"


def _page_has_education_table(page: str) -> bool:
    if "教育程度类别" in page:
        return True
    if "学历结构" in page and "%" in page:
        return True
    if "硕士研究生" in page and "大学本科" in page and "专科" in page:
        return True
    return False


def _rows_from_pct(section: str, *, issuer_id: str, as_of: str, document_id: str, collected_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bucket, pattern in _PCT_PATTERNS:
        match = pattern.search(section)
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


def _rows_from_counts(section: str, *, issuer_id: str, as_of: str, document_id: str, collected_at: str) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for bucket, pattern in _COUNT_PATTERNS:
        match = pattern.search(section)
        if match:
            counts[bucket] = _parse_count(match.group(1))
    if len(counts) < 2:
        return []
    total_match = re.search(r"合计[^\d\n]{0,40}([\d,]+)", section)
    total = _parse_count(total_match.group(1)) if total_match else sum(counts.values())
    if total <= 0:
        return []
    rows: list[dict[str, Any]] = []
    for bucket, count in counts.items():
        pct = _pct_from_count(count, total)
        if not pct:
            continue
        rows.append(
            workforce_education_row(
                issuer_id=issuer_id,
                as_of=as_of,
                bucket=bucket,
                pct=pct,
                document_id=document_id,
                collected_at=collected_at,
            )
        )
    return rows


def _parse_section(section: str, *, issuer_id: str, as_of: str, document_id: str, collected_at: str) -> list[dict[str, Any]]:
    rows = _rows_from_pct(section, issuer_id=issuer_id, as_of=as_of, document_id=document_id, collected_at=collected_at)
    if _CORE_BUCKETS.issubset({r["bucket"] for r in rows}):
        return rows
    count_rows = _rows_from_counts(
        section, issuer_id=issuer_id, as_of=as_of, document_id=document_id, collected_at=collected_at
    )
    if len(count_rows) >= 2:
        return count_rows
    return rows


def education_buckets_from_pages(
    pages: list[str],
    *,
    issuer_id: str,
    as_of: str,
    document_id: str,
    collected_at: str,
) -> list[dict[str, Any]]:
    """Parse education percentage buckets from annual-report text pages."""
    if not pages or not issuer_id or not as_of:
        return []
    text = "\n".join(pages)
    if not _SECTION_HINT.search(text):
        return []

    # cninfo PDFs usually keep the education table on a single page — parse per page first.
    for page in pages:
        if not page or not _page_has_education_table(page):
            continue
        rows = _parse_section(
            page, issuer_id=issuer_id, as_of=as_of, document_id=document_id, collected_at=collected_at
        )
        if len(rows) >= 2:
            return rows

    return _parse_section(
        text, issuer_id=issuer_id, as_of=as_of, document_id=document_id, collected_at=collected_at
    )
