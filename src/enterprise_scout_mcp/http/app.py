"""FastAPI REST surface for escout Fine UI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from enterprise_scout_mcp.config import AppConfig, load_config, resolve_project_root
from enterprise_scout_mcp.defaults import DEFAULT_REGISTRY_FIELDS
from enterprise_scout_mcp.diagnostics.doctor import build_doctor_report
from enterprise_scout_mcp.diagnostics.verify import build_verify_report
from enterprise_scout_mcp.models import CollectTask, Dimension, Platform, SourceTier
from enterprise_scout_mcp.scheduler import CollectorScheduler
from enterprise_scout_mcp.sessions.registry import list_sessions
from enterprise_scout_mcp.warehouse.neo4j_loader import import_warehouse
from enterprise_scout_mcp.warehouse.status import graph_driver_installed, probe_neo4j, summarize_warehouse


def _parse_fields(fields: str) -> tuple[str, ...]:
    if not fields or not fields.strip():
        return DEFAULT_REGISTRY_FIELDS
    parts = tuple(p.strip() for p in fields.split(",") if p.strip())
    return parts or DEFAULT_REGISTRY_FIELDS


def _parse_dims(text: str) -> tuple[Dimension, ...]:
    if not text.strip():
        return (Dimension.REGISTRY,)
    return tuple(Dimension(p.strip()) for p in text.split(",") if p.strip())


def create_app(config_path: str | None = None) -> Any:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel, Field

    config = load_config(config_path)
    root = resolve_project_root()
    ui_dist = root / "ui" / "dist"

    app = FastAPI(title="Enterprise Scout UI", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5179",
            "http://localhost:5179",
            "http://127.0.0.1:8790",
            "http://localhost:8790",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    class CollectBody(BaseModel):
        keyword: str = Field(..., min_length=1)
        platform: str = "aiqicha"
        depth: int = 1
        fields: str = ""
        dims: str = "registry"
        prefer_tier: str = ""
        persona_id: str = ""

    class Neo4jImportBody(BaseModel):
        dry_run: bool = True

    def _scheduler() -> CollectorScheduler:
        return CollectorScheduler(load_config(config_path))

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "service": "enterprise-scout-ui"}

    @app.get("/api/doctor")
    def doctor(probe: bool = False) -> dict[str, Any]:
        scheduler = _scheduler()
        try:
            return build_doctor_report(scheduler, load_config(config_path), probe_sidecars=probe)
        finally:
            scheduler.close()

    @app.get("/api/verify")
    def verify() -> dict[str, Any]:
        scheduler = _scheduler()
        try:
            report = build_verify_report(scheduler, load_config(config_path))
            return {
                "ok": report["ok"],
                "checks": report["checks"],
                "failed": report["failed"],
                "warehouse_counts": report.get("warehouse_counts"),
                "note": report.get("note"),
            }
        finally:
            scheduler.close()

    @app.get("/api/warehouse")
    def warehouse() -> dict[str, Any]:
        cfg = load_config(config_path)
        return summarize_warehouse(Path(cfg.output.warehouse_dir))

    @app.get("/api/sessions")
    def sessions() -> dict[str, Any]:
        return {"sessions": list_sessions(load_config(config_path))}

    @app.get("/api/neo4j/probe")
    def neo4j_probe() -> dict[str, Any]:
        cfg = load_config(config_path)
        if not graph_driver_installed():
            return {"ok": False, "error": "neo4j driver not installed"}
        return probe_neo4j(cfg.neo4j.uri, cfg.neo4j.user, cfg.neo4j.password)

    @app.post("/api/collect")
    def collect(body: CollectBody) -> dict[str, Any]:
        cfg = load_config(config_path)
        scheduler = CollectorScheduler(cfg)
        try:
            tier = SourceTier(body.prefer_tier.lower()) if body.prefer_tier else None
            plat = body.platform
            if tier == SourceTier.L1 and plat == "aiqicha":
                plat = "gsxt"
            task = CollectTask(
                keyword=body.keyword.strip(),
                platform=Platform(plat),
                depth=body.depth,
                fields=_parse_fields(body.fields),
                dimensions=_parse_dims(body.dims),
                prefer_tier=tier,
            )
            result = scheduler.run(task, persona_id=body.persona_id or None)
            return {
                "ok": result.grade.value in ("ok", "partial"),
                "grade": result.grade.value,
                "channel": result.channel.value,
                "source_tier": result.source_tier.value if result.source_tier else "",
                "dimension": result.dimension.value if result.dimension else "",
                "message": result.message,
                "persona_id": result.persona_id,
                "data": result.data,
            }
        except Exception as exc:  # noqa: BLE001 — surface to UI
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        finally:
            scheduler.close()

    @app.post("/api/import-neo4j")
    def import_neo4j(body: Neo4jImportBody) -> dict[str, Any]:
        cfg = load_config(config_path)
        wh = Path(cfg.output.warehouse_dir)
        neo = cfg.neo4j
        try:
            stats = import_warehouse(
                wh,
                uri=neo.uri,
                user=neo.user,
                password=neo.password,
                dry_run=body.dry_run,
            )
        except ImportError as exc:
            return {"ok": False, "error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "warehouse_dir": str(wh), "dry_run": body.dry_run, **stats.to_dict()}

    if ui_dist.is_dir():
        app.mount("/", StaticFiles(directory=str(ui_dist), html=True), name="ui")

    return app
