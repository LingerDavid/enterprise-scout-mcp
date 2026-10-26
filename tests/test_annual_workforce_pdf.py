"""Annual-report workforce education parsing."""

from __future__ import annotations

from enterprise_scout_mcp.sources.annual_workforce_pdf import education_buckets_from_pages


def test_education_buckets_from_pages() -> None:
    pages = [
        "公司员工情况\n"
        "员工学历结构：硕士及以上 5.67%，本科 46.99%，专科及以下 46.20%，其他 1.14%。"
    ]
    rows = education_buckets_from_pages(
        pages,
        issuer_id="issuer-1",
        as_of="2025-12-31",
        document_id="ann-1",
        collected_at="t0",
    )
    buckets = {r["bucket"]: r["pct"] for r in rows}
    assert buckets["master_plus"] == "5.67"
    assert buckets["bachelor"] == "46.99"
    assert buckets["college_below"] == "46.20"
    assert buckets["other"] == "1.14"


def test_education_buckets_from_headcount_table() -> None:
    pages = [
        "九、公司员工情况\n"
        "1、员工数量、专业构成及教育程度\n"
        "教育程度类别 数量（人）\n"
        "硕士研究生及以上 687\n"
        "大学本科 5,431\n"
        "大学专科及以下 4,819\n"
        "合计 10,937\n"
        "2、薪酬政策\n"
    ]
    rows = education_buckets_from_pages(
        pages,
        issuer_id="issuer-1",
        as_of="2024-12-31",
        document_id="ann-2",
        collected_at="t0",
    )
    buckets = {r["bucket"]: r["pct"] for r in rows}
    assert buckets["master_plus"] == "6.28"
    assert buckets["bachelor"] == "49.66"
    assert buckets["college_below"] == "44.06"
