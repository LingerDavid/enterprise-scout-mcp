"""Doctor report shape."""

from __future__ import annotations

from enterprise_scout_mcp.config import AppConfig
from enterprise_scout_mcp.diagnostics.doctor import build_doctor_report
from enterprise_scout_mcp.scheduler import CollectorScheduler


def test_doctor_report_keys() -> None:
    config = AppConfig()
    scheduler = CollectorScheduler(config)
    try:
        report = build_doctor_report(scheduler, config)
    finally:
        scheduler.close()

    assert "ensan_go" in report
    assert "nodriver" in report
    assert "warehouse" in report
    assert "script_exists" in report["nodriver"]
    assert "entities_exists" in report["warehouse"]
