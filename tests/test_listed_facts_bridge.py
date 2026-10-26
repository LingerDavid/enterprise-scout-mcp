"""Panel financials → listed/facts bridge."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from enterprise_scout_mcp.integrations.listed_facts_bridge import sync_panel_to_listed_facts
from enterprise_scout_mcp.output.listed_schema import identity_row


def test_sync_panel_to_listed_facts(tmp_path: Path) -> None:
    panel = tmp_path / "panel"
    wh = tmp_path / "warehouse"
    iid = "91110000123456789X"
    (wh / "listed" / "identity").mkdir(parents=True)
    pq.write_table(
        pa.Table.from_pylist(
            [
                identity_row(
                    issuer_id=iid,
                    issuer_name="Test",
                    security_id="SSE:600519",
                    exchange="SSE",
                    code="600519",
                    board="主板",
                    document_id="t",
                    collected_at="t0",
                )
            ]
        ),
        wh / "listed" / "identity" / "part.parquet",
    )
    fin = panel / "financials" / "income"
    fin.mkdir(parents=True)
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "symbol": "600519.SH",
                    "period_end": "2024-12-31",
                    "revenue": 1000000.0,
                    "net_income_attributable": 500000.0,
                }
            ]
        ),
        fin / "part.parquet",
    )

    report = sync_panel_to_listed_facts(panel, wh, dry_run=False)
    assert report["ok"] is True
    assert report["facts"] >= 2
    facts = pq.read_table(wh / "listed" / "facts" / "part.parquet").to_pylist()
    codes = {r["item_code"] for r in facts}
    assert "revenue" in codes
    assert "net_profit_parent" in codes
