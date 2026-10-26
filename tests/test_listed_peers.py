"""In-warehouse peer comparison."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from enterprise_scout_mcp.integrations.listed_peers import peer_compare
from enterprise_scout_mcp.output.listed_schema import facts_row, identity_row


def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), path)


def test_peer_compare_percentiles(tmp_path: Path) -> None:
    wh = tmp_path / "warehouse"
    industry = "化学原料和化学制品制造业"
    issuers = [f"issuer-{i}" for i in range(10)]
    identity = [
        identity_row(
            issuer_id=iid,
            issuer_name=f"Co{i}",
            security_id=f"SZSE:00000{i}",
            exchange="SZSE",
            code=f"00000{i}",
            board="主板",
            csrc_industry_l2=industry,
            document_id="t",
            collected_at="t0",
        )
        for i, iid in enumerate(issuers)
    ]
    facts = []
    for i, iid in enumerate(issuers):
        facts.append(
            facts_row(
                issuer_id=iid,
                period="2024",
                scope="consolidated",
                statement="income",
                item_code="revenue",
                label="revenue",
                value=str(100 + i * 10),
                unit="CNY",
                currency="CNY",
                document_id="t",
                collected_at="t0",
            )
        )
        facts.append(
            facts_row(
                issuer_id=iid,
                period="2024",
                scope="consolidated",
                statement="income",
                item_code="net_profit_parent",
                label="np",
                value=str(10 + i),
                unit="CNY",
                currency="CNY",
                document_id="t",
                collected_at="t0",
            )
        )
    _write(wh / "listed" / "identity" / "part.parquet", identity)
    _write(wh / "listed" / "facts" / "part.parquet", facts)

    report = peer_compare(wh, "000009.SZ")
    assert report["ok"] is True
    assert report["sample_sufficient"] is True
    assert "revenue" in report["metrics"]
    assert report["metrics"]["revenue"]["percentile"] is not None
