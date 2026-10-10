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
    assert "gsxt" in report
    assert "tiers" in report
    assert report["tiers"]["l1_registry"]["implemented"] is True
    assert "routing" in report
    assert report["routing"]["ensan_only"] is True
    assert "nodriver" in report
    assert "warehouse" in report
    assert "script_exists" in report["nodriver"]
    assert "entities_exists" in report["warehouse"]
    assert "sidecars" not in report
    arch = report["architecture"]
    assert arch["persona"]["implemented"] is True
    assert arch["consistency"]["implemented"] is True
    assert "timezone" in arch["consistency"]["checks"]
    assert "camoufox" in arch["disguise_egress"]
    assert arch["captcha_branch"]["strategy"] == "rotate_ip"
    assert report["tiers"]["equity"]["implemented"] is True
    assert report["tiers"]["l3"]["implemented"] is True
    assert "corpus" in report
    assert "l3" in report["corpus"]
    assert arch["phase2"]["credit"] is True


def test_doctor_probe_sidecars_attached() -> None:
    config = AppConfig()
    scheduler = CollectorScheduler(config)
    try:
        report = build_doctor_report(scheduler, config, probe_sidecars=True)
    finally:
        scheduler.close()

    assert "sidecars" in report
    assert "ensan_go" in report["sidecars"]
