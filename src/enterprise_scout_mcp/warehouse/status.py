"""Warehouse parquet inventory and Neo4j connectivity probes."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def warehouse_paths(warehouse_dir: Path) -> dict[str, Path]:
    base = warehouse_dir
    return {
        "entities": base / "entities" / "part.parquet",
        "edges_equity": base / "edges" / "equity" / "part.parquet",
        "conflicts": base / "conflicts" / "part.parquet",
        "supplements_l3": base / "supplements" / "l3" / "part.parquet",
        "supplements_judicial": base / "supplements" / "judicial" / "part.parquet",
    }


def summarize_warehouse(warehouse_dir: Path) -> dict[str, Any]:
    """File presence + dry-run import counts (no Neo4j write)."""
    paths = warehouse_paths(warehouse_dir)
    out: dict[str, Any] = {
        "dir": str(warehouse_dir),
        "files": {
            key: {"path": str(path), "exists": path.is_file()} for key, path in paths.items()
        },
    }
    try:
        from enterprise_scout_mcp.warehouse.neo4j_loader import import_warehouse

        stats = import_warehouse(warehouse_dir, uri="", user="", password="", dry_run=True)
        out["dry_run_ok"] = True
        out["counts"] = stats.to_dict()
    except ImportError as exc:
        out["dry_run_ok"] = False
        out["counts"] = None
        out["error"] = str(exc)
    except Exception as exc:  # noqa: BLE001 — surface path/read failures
        out["dry_run_ok"] = False
        out["counts"] = None
        out["error"] = str(exc)
    return out


def probe_neo4j(uri: str, user: str, password: str, *, timeout: float = 3.0) -> dict[str, Any]:
    """Lightweight bolt connectivity check."""
    try:
        from neo4j import GraphDatabase
    except ImportError:
        return {"ok": False, "reachable": False, "error": "neo4j driver not installed"}

    driver = GraphDatabase.driver(uri, auth=(user, password), connection_timeout=timeout)
    try:
        driver.verify_connectivity()
        with driver.session() as session:
            record = session.run("RETURN 1 AS n").single()
            ok = record is not None and record["n"] == 1
        return {"ok": ok, "reachable": ok, "uri": uri}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reachable": False, "uri": uri, "error": str(exc)}
    finally:
        driver.close()


def graph_driver_installed() -> bool:
    try:
        import neo4j  # noqa: F401
    except ImportError:
        return False
    return True
