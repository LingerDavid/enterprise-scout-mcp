"""Listed corpus JSONL → warehouse import."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from enterprise_scout_mcp.integrations.listed_corpus import import_listed_corpus, record_to_rows

pq = pytest.importorskip("pyarrow.parquet")


def test_record_to_rows_builds_identity_facts_segments() -> None:
    record = {
        "issuer_id": "91",
        "issuer_name": "Demo",
        "security_id": "SSE:600519",
        "period": "2024",
        "document_id": "ann-1",
        "document_date": "2025-03-31",
        "facts": [
            {"item_code": "revenue", "statement": "income", "value": "100"},
            {"item_code": "cfo", "statement": "cashflow", "value": "20"},
        ],
        "segments": [{"kind": "product", "name": "A", "revenue": "70", "cost": "40"}],
    }
    parts = record_to_rows(record, collected_at="2026-01-01T00:00:00+00:00")
    assert len(parts["identity"]) == 1
    assert parts["identity"][0]["security_id"] == "SSE:600519"
    assert len(parts["facts"]) == 2
    assert parts["facts"][0]["document_date"] == "2025-03-31"
    assert len(parts["segments"]) == 1


def test_import_listed_corpus_writes_parquet(tmp_path: Path) -> None:
    corpus = tmp_path / "listed"
    corpus.mkdir()
    warehouse = tmp_path / "warehouse"
    row = {
        "issuer_id": "91",
        "security_id": "SSE:600519",
        "exchange": "SSE",
        "code": "600519",
        "period": "2024",
        "document_id": "ann-1",
        "document_date": "2025-03-31",
        "facts": [
            {"item_code": "net_profit_parent", "statement": "income", "value": "50"},
            {"item_code": "cfo", "statement": "cashflow", "value": "100"},
            {"item_code": "capex_cash", "statement": "cashflow", "value": "40"},
            {"item_code": "cash_from_sales", "statement": "cashflow", "value": "120"},
        ],
    }
    (corpus / "demo.jsonl").write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    (corpus / "_example.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")

    dry = import_listed_corpus(corpus, warehouse, dry_run=True)
    assert dry["records"] == 1
    assert dry["facts"] == 4
    assert not (warehouse / "listed" / "facts" / "part.parquet").exists()

    report = import_listed_corpus(corpus, warehouse, dry_run=False)
    assert report["identity"] == 1
    assert report["facts"] == 4
    facts_path = warehouse / "listed" / "facts" / "part.parquet"
    assert facts_path.is_file()
    assert pq.read_table(facts_path).num_rows == 4
