"""F10 backfill orchestrator."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from enterprise_scout_mcp.integrations.listed_f10_backfill import (
    DEFAULT_LISTED_F10_TABLES,
    backfill_listed_f10,
)
from enterprise_scout_mcp.output.listed_schema import identity_row


def test_default_tables_include_workforce() -> None:
    assert "workforce" in DEFAULT_LISTED_F10_TABLES
    assert "float_holders" in DEFAULT_LISTED_F10_TABLES


def test_backfill_symbol_filter(tmp_path: Path) -> None:
    wh = tmp_path / "warehouse"
    ident_path = wh / "listed" / "identity"
    ident_path.mkdir(parents=True)
    pq.write_table(
        pa.Table.from_pylist(
            [
                identity_row(
                    issuer_id="a",
                    issuer_name="A",
                    security_id="SZSE:002271",
                    exchange="SZSE",
                    code="002271",
                ),
                identity_row(
                    issuer_id="b",
                    issuer_name="B",
                    security_id="SSE:600519",
                    exchange="SSE",
                    code="600519",
                ),
            ]
        ),
        ident_path / "part.parquet",
    )
    summary = backfill_listed_f10(
        wh,
        tables=("segments",),
        workers=1,
        symbols=("002271.SZ",),
    )
    assert summary["identity_rows"] == 1
