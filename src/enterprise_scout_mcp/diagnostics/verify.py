"""Architecture verification — doctor + module checklist (no live sidecars)."""

from __future__ import annotations

from pathlib import Path

from enterprise_scout_mcp.config import AppConfig
from enterprise_scout_mcp.diagnostics.doctor import build_doctor_report
from enterprise_scout_mcp.scheduler import CollectorScheduler
from enterprise_scout_mcp.warehouse.status import summarize_warehouse


def build_verify_report(scheduler: CollectorScheduler, config: AppConfig) -> dict:
    doctor = build_doctor_report(scheduler, config, probe_sidecars=False)
    arch = doctor.get("architecture", {})
    tiers = doctor.get("tiers", {})
    warehouse = summarize_warehouse(Path(config.output.warehouse_dir))
    counts = warehouse.get("counts") or {}
    checks = {
        "persona_engine": arch.get("persona", {}).get("implemented") is True,
        "risk_routing": arch.get("risk_routing", {}).get("implemented") is True,
        "behavior": arch.get("behavior", {}).get("implemented") is True,
        "consistency": arch.get("consistency", {}).get("implemented") is True,
        "disguise_egress": "curl_cffi" in arch.get("disguise_egress", {}),
        "captcha_branch": "solver_api" in (arch.get("captcha_branch", {}).get("strategies") or []),
        "l1_registry": tiers.get("l1_registry", {}).get("implemented") is True,
        "l2_registry": tiers.get("l2_registry", {}).get("implemented") is True,
        "l3_corpus": tiers.get("l3", {}).get("implemented") is True,
        "equity_dimension": tiers.get("equity", {}).get("implemented") is True,
        "neo4j_warehouse_dry_run": warehouse.get("dry_run_ok") is True,
        "neo4j_supplements": "supplements_merged" in counts,
        "neo4j_conflicts": "conflicts_merged" in counts,
        "neo4j_model": "Conflict" in (doctor.get("neo4j", {}).get("model") or []),
        "fine_ui": False,
    }
    required_failed = [k for k, ok in checks.items() if not ok and k != "fine_ui"]
    return {
        "ok": len(required_failed) == 0,
        "checks": checks,
        "failed": required_failed,
        "warehouse_counts": counts,
        "note": "fine_ui intentionally false — last phase",
        "doctor": doctor,
    }
