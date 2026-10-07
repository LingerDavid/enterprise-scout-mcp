"""Integration health checks for escout doctor / scout_doctor MCP tool."""

from __future__ import annotations

from pathlib import Path

from enterprise_scout_mcp.config import AppConfig, resolve_project_root
from enterprise_scout_mcp.diagnostics.sidecars import build_sidecar_report
from enterprise_scout_mcp.models import ChannelKind
from enterprise_scout_mcp.scheduler import CollectorScheduler


def _resolve(root: Path, rel: str) -> Path:
    p = Path(rel)
    return p if p.is_absolute() else root / p


def build_doctor_report(
    scheduler: CollectorScheduler,
    config: AppConfig,
    *,
    probe_sidecars: bool = False,
) -> dict:
    root = resolve_project_root()
    pw = config.integrations.playwright
    wh = Path(config.output.warehouse_dir)
    entities = wh / "entities" / "part.parquet"
    edges = wh / "edges" / "equity" / "part.parquet"

    return {
        "project_root": str(root),
        "ensan_go": {
            "available": scheduler._channels[ChannelKind.ENSCAN_GO].available(),
            "base_url": config.integrations.ensan_go.base_url,
            "enabled": config.integrations.ensan_go.enabled,
        },
        "playwright": {
            "available": scheduler._channels[ChannelKind.PLAYWRIGHT].available(),
            "enabled": pw.enabled,
            "companies_db": str(_resolve(root, pw.companies_db)),
            "db_exists": _resolve(root, pw.companies_db).is_file(),
            "fetch_on_miss": pw.fetch_on_miss,
        },
        "nodriver": {
            "on_captcha": pw.nodriver_on_captcha,
            "script": str(_resolve(root, pw.nodriver_script)),
            "script_exists": _resolve(root, pw.nodriver_script).is_file(),
        },
        "handaas": {
            "available": scheduler._channels[ChannelKind.HANDAAS_API].available(),
            "enabled": config.integrations.handaas.enabled,
        },
        "proxy_pool": {
            "enabled": config.integrations.proxy_pool.enabled,
            "base_url": config.integrations.proxy_pool.base_url,
        },
        "warehouse": {
            "dir": str(wh),
            "parquet_enabled": config.output.parquet_enabled,
            "entities_part": str(entities),
            "entities_exists": entities.is_file(),
            "edges_equity_part": str(edges),
            "edges_exists": edges.is_file(),
        },
        "personas": scheduler._persona.list_ids(),
    }
    if probe_sidecars:
        report["sidecars"] = build_sidecar_report(config)
    return report
