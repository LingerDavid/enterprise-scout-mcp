"""Neo4j warehouse loader helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from enterprise_scout_mcp.warehouse.neo4j_loader import (
    company_id,
    conflict_id,
    import_warehouse,
    parse_percent,
    supplement_id,
)


def test_company_id_fallback_to_name() -> None:
    assert company_id("", "Acme Corp") == "Acme Corp"
    assert company_id("42", "Acme Corp") == "42"


def test_parse_percent() -> None:
    assert parse_percent("51%") == 51.0
    assert parse_percent("30") == 30.0
    assert parse_percent("") is None
    assert parse_percent("n/a") is None


@pytest.mark.skipif(
    importlib.util.find_spec("pyarrow") is None,
    reason="pyarrow not installed",
)
def test_import_warehouse_dry_run(tmp_path: Path) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    entities = tmp_path / "entities"
    entities.mkdir(parents=True)
    pq.write_table(
        pa.Table.from_pylist([{"entity_id": "1", "name": "Co"}]),
        entities / "part.parquet",
    )
    edges = tmp_path / "edges" / "equity"
    edges.mkdir(parents=True)
    pq.write_table(
        pa.Table.from_pylist(
            [{"src_name": "Parent", "dst_name": "Co", "relation": "holder", "ratio": "10%"}]
        ),
        edges / "part.parquet",
    )
    stats = import_warehouse(tmp_path, uri="", user="", password="", dry_run=True)
    assert stats.entities_merged == 1
    assert stats.holds_merged == 1


def test_conflict_id_stable() -> None:
    cid = conflict_id(
        {
            "query_keyword": "Acme",
            "field": "credit_code",
            "collected_at": "2026-01-01T00:00:00+00:00",
        }
    )
    assert "Acme" in cid
    assert "credit_code" in cid


def test_supplement_id_stable() -> None:
    sid = supplement_id(
        {
            "query_keyword": "Acme",
            "dimension": "judicial",
            "corpus_file": "c.jsonl",
            "collected_at": "2026-01-01T00:00:00+00:00",
        }
    )
    assert "Acme" in sid
    assert "judicial" in sid


@pytest.mark.skipif(
    importlib.util.find_spec("pyarrow") is None,
    reason="pyarrow not installed",
)
def test_import_warehouse_dry_run_includes_supplements(tmp_path: Path) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    l3 = tmp_path / "supplements" / "l3"
    l3.mkdir(parents=True)
    pq.write_table(
        pa.Table.from_pylist(
            [{"query_keyword": "Acme", "dimension": "registry", "corpus_file": "p.jsonl"}]
        ),
        l3 / "part.parquet",
    )
    conflicts = tmp_path / "conflicts"
    conflicts.mkdir(parents=True)
    pq.write_table(
        pa.Table.from_pylist(
            [{"query_keyword": "Acme", "field": "name", "l1_value": "A", "l2_value": "B"}]
        ),
        conflicts / "part.parquet",
    )
    stats = import_warehouse(tmp_path, uri="", user="", password="", dry_run=True)
    assert stats.supplements_merged == 1
    assert stats.conflicts_merged == 1
