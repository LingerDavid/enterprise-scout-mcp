"""Integration health checks for escout doctor / scout_doctor MCP tool."""

from __future__ import annotations

import os
from pathlib import Path

from enterprise_scout_mcp.captcha.opencv_slider import opencv_available
from enterprise_scout_mcp.config import AppConfig, resolve_project_root
from enterprise_scout_mcp.integrations.corpus_lookup import corpus_dir_stats
from enterprise_scout_mcp.sessions.registry import list_sessions
from enterprise_scout_mcp.diagnostics.sidecars import build_sidecar_report
from enterprise_scout_mcp.models import ChannelKind, Dimension
from enterprise_scout_mcp.scheduler import CollectorScheduler
from enterprise_scout_mcp.transport.camoufox_backend import camoufox_available


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
    corpus = config.integrations.corpus
    l3_dir = _resolve(root, corpus.l3_dir)
    judicial_dir = _resolve(root, corpus.judicial_dir)
    l3_stats = corpus_dir_stats(l3_dir)
    judicial_stats = corpus_dir_stats(judicial_dir)
    l3_channel = scheduler._channels[ChannelKind.ACADEMIC_L3]

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
            "l3": {
                "implemented": True,
                "channel": ChannelKind.ACADEMIC_L3.value,
                "available": l3_channel.available(),
                "corpus_dir": str(l3_dir),
                "corpus_files": l3_stats["files"],
                "note": "JSON/JSONL under integrations.corpus.l3_dir",
            },
            "equity": {
                "implemented": True,
                "channel": ChannelKind.ENSCAN_GO.value,
                "fields": ["partner", "holds", "invest", "branch"],
            },
            "credit": {
                "implemented": True,
                "channel": ChannelKind.HANDAAS_API.value
                if scheduler._channels[ChannelKind.HANDAAS_API].available()
                else ChannelKind.DEFERRED.value,
                "note": "Handaas base_info when credentials set; else deferred stub",
            },
            "judicial": {
                "implemented": True,
                "channel": ChannelKind.DEFERRED.value,
                "corpus_dir": str(judicial_dir),
                "corpus_files": judicial_stats["files"],
                "note": "local corpus JSON/JSONL or deferred stub",
            },
        },
        "corpus": {
            "enabled": corpus.enabled,
            "l3": l3_stats,
            "judicial": judicial_stats,
        },
        "gsxt": {
            "enabled": gsxt.enabled,
            "base_url": gsxt.base_url,
            "search_url": gsxt.search_url,
            "search_mode": gsxt.search_mode,
            "browser_backend": gsxt.browser_backend,
            "browser_cdp_port": gsxt.browser_cdp_port,
            "browser_headless": gsxt.browser_headless,
            "proxy_url": gsxt.proxy_url or None,
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
        "architecture": {
            "persona": {"implemented": True},
            "risk_routing": {"implemented": True},
            "behavior": {"implemented": True},
            "consistency": {
                "implemented": True,
                "checks": ["ua", "tls", "locale", "language", "geo", "timezone", "os", "sec-ch-ua"],
            },
            "disguise_egress": {
                "curl_cffi": {
                    "enabled": config.integrations.curl_cffi.enabled,
                    "impersonate": config.integrations.curl_cffi.impersonate,
                },
                "camoufox": {
                    "enabled": config.integrations.camoufox.enabled,
                    "available": camoufox_available().available,
                    "message": camoufox_available().message,
                },
            },
            "captcha_branch": {
                "strategy": config.integrations.captcha.strategy,
                "solver_provider": config.integrations.captcha.solver_provider or None,
                "solver_configured": bool(
                    config.integrations.captcha.solver_api_key
                    or os.environ.get("CAPSOLVER_API_KEY")
                ),
                "opencv_available": opencv_available(),
                "strategies": ["rotate_ip", "solver_api", "opencv_slider", "manual"],
            },
            "channels": {
                "ensan_go": True,
                "playwright": True,
                "gsxt_cdp": True,
                "handaas": True,
            },
            "phase2": {
                "credit": True,
                "judicial": True,
                "note": "credit→Handaas when creds set; judicial→local corpus or stub",
            },
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
