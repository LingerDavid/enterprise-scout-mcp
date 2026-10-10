"""Architecture verification report."""

from __future__ import annotations

from enterprise_scout_mcp.config import AppConfig
from enterprise_scout_mcp.diagnostics.verify import build_verify_report
from enterprise_scout_mcp.scheduler import CollectorScheduler


def test_verify_report_backend_ok() -> None:
    config = AppConfig()
    scheduler = CollectorScheduler(config)
    try:
        report = build_verify_report(scheduler, config)
    finally:
        scheduler.close()
    assert report["checks"]["l1_registry"] is True
    assert report["checks"]["neo4j_warehouse_dry_run"] is True
    assert report["checks"]["neo4j_supplements"] is True
    assert report["checks"]["neo4j_conflicts"] is True
    assert report["checks"]["neo4j_model"] is True
    assert report["checks"]["fine_ui"] is True
    assert report["ok"] is True
