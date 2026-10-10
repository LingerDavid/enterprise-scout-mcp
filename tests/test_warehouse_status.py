"""Warehouse summary and Neo4j probe helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from enterprise_scout_mcp.warehouse.status import (
    graph_driver_installed,
    summarize_warehouse,
    warehouse_paths,
)


def test_warehouse_paths_keys() -> None:
    paths = warehouse_paths(Path("/tmp/wh"))
    assert "entities" in paths
    assert "conflicts" in paths
    assert "supplements_l3" in paths


@pytest.mark.skipif(
    importlib.util.find_spec("pyarrow") is None,
    reason="pyarrow not installed",
)
def test_summarize_warehouse_empty_dir(tmp_path: Path) -> None:
    summary = summarize_warehouse(tmp_path)
    assert summary["dry_run_ok"] is True
    assert summary["counts"]["entities_merged"] == 0
    assert summary["counts"]["conflicts_merged"] == 0
    assert summary["counts"]["supplements_merged"] == 0


def test_graph_driver_installed_returns_bool() -> None:
    assert isinstance(graph_driver_installed(), bool)
