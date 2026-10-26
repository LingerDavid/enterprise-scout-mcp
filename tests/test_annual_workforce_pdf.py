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
