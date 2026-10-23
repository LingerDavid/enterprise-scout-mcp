"""Prospectus fallback helpers (no live network)."""

from __future__ import annotations

from pathlib import Path

import pytest

from enterprise_scout_mcp.integrations.listed_equity_extract import (
    PROSPECTUS_PDF_CHANNEL,
    edges_from_equity_extract,
    upsert_filing_edges_to_warehouse,
)
from enterprise_scout_mcp.sources.annual_equity_pdf import EquityExtractResult

pq = pytest.importorskip("pyarrow.parquet")


def test_prospectus_edges_use_separate_channel(tmp_path: Path) -> None:
    result = EquityExtractResult(
        suppliers=[{"name": "原料甲有限公司", "purchase_pct": "22.5"}],
        investments=[{"name": "参股乙有限公司", "direct_pct": "30"}],
    )
    edges = edges_from_equity_extract(
        result,
        issuer_name="新上市公司",
        source_channel=PROSPECTUS_PDF_CHANNEL,
        include=frozenset({"suppliers"}),
        collected_at="t1",
    )
    assert len(edges) == 1
    assert edges[0]["relation"] == "supply"
    assert edges[0]["source_channel"] == "prospectus_pdf"
    assert edges[0]["dst_name"] == "原料甲有限公司"

    path = upsert_filing_edges_to_warehouse(
        tmp_path,
        issuer_name="新上市公司",
        edges=edges,
        source_channel=PROSPECTUS_PDF_CHANNEL,
    )
    assert path is not None
    rows = pq.read_table(path).to_pylist()
    assert len(rows) == 1
    assert rows[0]["source_channel"] == "prospectus_pdf"
