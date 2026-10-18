"""Listed parquet append."""

from __future__ import annotations

from pathlib import Path

import pytest

from enterprise_scout_mcp.output.listed_schema import facts_row, identity_row
from enterprise_scout_mcp.output.listed_writer import append_listed_rows, listed_part_path

pyarrow = pytest.importorskip("pyarrow")
pq = pytest.importorskip("pyarrow.parquet")


def test_append_identity_and_facts(tmp_path: Path) -> None:
    warehouse = tmp_path / "warehouse"
    ident = identity_row(
        issuer_id="91",
        issuer_name="Demo",
        security_id="SSE:600519",
        exchange="SSE",
        code="600519",
    )
    path = append_listed_rows(warehouse, "identity", [ident])
    assert path == listed_part_path(warehouse, "identity")
    assert path is not None and path.is_file()

    fact = facts_row(
        issuer_id="91",
        period="2024",
        scope="consolidated",
        statement="income",
        item_code="revenue",
        value="100",
        unit="CNY",
        document_id="ann-1",
        document_date="2025-03-31",
    )
    fpath = append_listed_rows(warehouse, "facts", [fact])
    assert fpath is not None
    table = pq.read_table(fpath)
    assert table.num_rows == 1
    assert table.column("document_date")[0].as_py() == "2025-03-31"

    append_listed_rows(warehouse, "facts", [fact])
    assert pq.read_table(fpath).num_rows == 2
