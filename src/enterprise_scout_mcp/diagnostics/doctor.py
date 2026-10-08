"""Integration health checks for escout doctor / scout_doctor MCP tool."""

from __future__ import annotations

from pathlib import Path

from enterprise_scout_mcp.config import AppConfig, resolve_project_root
from enterprise_scout_mcp.sessions.registry import list_sessions
from enterprise_scout_mcp.diagnostics.sidecars import build_sidecar_report
from enterprise_scout_mcp.models import ChannelKind, Dimension
from enterprise_scout_mcp.scheduler import CollectorScheduler


def _resolve(root: Path, rel: str) -> Path:
    p = Path(rel)
    return p if p.is_absolute() else root / p


def _count_json(directory: Path) -> int:
    if not directory.is_dir():
        return 0
    return sum(1 for _ in directory.glob("*.json"))


def build_doctor_report(
    scheduler: CollectorScheduler,
    config: AppConfig,
    *,
    probe_sidecars: bool = False,
) -> dict:
    root = resolve_project_root()
    pw = config.integrations.playwright
    gsxt = config.integrations.gsxt
    wh = Path(config.output.warehouse_dir)
    entities = wh / "entities" / "part.parquet"
    edges = wh / "edges" / "equity" / "part.parquet"
    session_path = _resolve(root, gsxt.session_file)
    gsxt_channel = scheduler._channels[ChannelKind.GSXT_OFFICIAL]

    report: dict = {
        "project_root": str(root),
        "routing": {
            "source_policy": config.routing.source_policy,
            "ensan_only": config.routing.ensan_only,
        },
        "tiers": {
            "l1_registry": {
                "dimension": Dimension.REGISTRY.value,
                "channel": ChannelKind.GSXT_OFFICIAL.value,
                "implemented": True,
                "available": gsxt_channel.available(),
                "session_mode": gsxt.session_mode,
                "session_file": str(session_path),
                "session_exists": session_path.is_file(),
                "shiming_url": gsxt.shiming_url,
            },
            "l2_registry": {
                "dimension": Dimension.REGISTRY.value,
                "channel": ChannelKind.ENSCAN_GO.value,
                "implemented": True,
                "available": scheduler._channels[ChannelKind.ENSCAN_GO].available(),
            },
            "l3": {"implemented": False, "note": "academic ingest stub"},
            "equity": {"implemented": False},
            "credit": {"implemented": False},
            "judicial": {"implemented": False},
        },
        "gsxt": {
            "enabled": gsxt.enabled,
            "base_url": gsxt.base_url,
            "search_url": gsxt.search_url,
            "available": gsxt_channel.available(),
        },
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
            "note": "disabled under ensan_only; kept for force_channel only",
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
            "note": "unused under ensan_only (ENScan owns egress)",
        },
        "warehouse": {
            "dir": str(wh),
            "parquet_enabled": config.output.parquet_enabled,
            "entities_part": str(entities),
            "entities_exists": entities.is_file(),
            "edges_equity_part": str(edges),
            "edges_exists": edges.is_file(),
        },
        "neo4j": {
            "enabled": config.neo4j.enabled,
            "auto_import": config.neo4j.auto_import,
            "uri": config.neo4j.uri,
            "user": config.neo4j.user,
        },
        "retry_queue": {
            "dir": str(Path(config.output.raw_dir) / "retry_queue"),
            "pending": _count_json(Path(config.output.raw_dir) / "retry_queue"),
        },
        "personas": scheduler._persona.list_ids(),
        "sessions": list_sessions(config),
    }
    if probe_sidecars:
        report["sidecars"] = build_sidecar_report(config)
    return report
