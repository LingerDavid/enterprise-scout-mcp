"""MCP server - primary product surface for enterprise intelligence."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from enterprise_scout_mcp.batch import parse_keywords, run_batch
from enterprise_scout_mcp.config import load_config
from enterprise_scout_mcp.defaults import DEFAULT_REGISTRY_FIELDS
from enterprise_scout_mcp.diagnostics.doctor import build_doctor_report
from enterprise_scout_mcp.diagnostics.sidecars import build_sidecar_report
from enterprise_scout_mcp.integrations.enscan_cookies import sync_aiqicha_to_enscan
from enterprise_scout_mcp.models import CollectTask, Platform
from enterprise_scout_mcp.scheduler import CollectorScheduler
from enterprise_scout_mcp.retry import drain_retry_queue
from enterprise_scout_mcp.warehouse.neo4j_loader import import_warehouse


def _parse_fields(fields: str) -> tuple[str, ...]:
    if not fields or not fields.strip():
        return DEFAULT_REGISTRY_FIELDS
    parts = tuple(p.strip() for p in fields.split(",") if p.strip())
    return parts or DEFAULT_REGISTRY_FIELDS


def create_mcp_server():
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP(
        "enterprise-scout-mcp",
        instructions=(
            "Enterprise registry intelligence via ENScan_GO (ensan_only). "
            "Optional Handaas API for paid complement. "
            "Writes entities/edges to EnterpriseLake. "
            "Default fields include partner/holds/invest/branch for equity edges."
        ),
    )

    @mcp.tool()
    def enterprise_collect(
        keyword: str,
        platform: str = "aiqicha",
        depth: int = 1,
        fields: str = "",
        persona_id: str = "",
    ) -> str:
        """Collect enterprise info (default fields: enterprise_info,partner,holds,invest,branch)."""
        config = load_config()
        scheduler = CollectorScheduler(config)
        try:
            task = CollectTask(
                keyword=keyword,
                platform=Platform(platform),
                depth=depth,
                fields=_parse_fields(fields),
            )
            result = scheduler.run(task, persona_id=persona_id or None)
            return json.dumps(
                {
                    "grade": result.grade.value,
                    "channel": result.channel.value,
                    "message": result.message,
                    "persona_id": result.persona_id,
                    "data": result.data,
                },
                ensure_ascii=False,
            )
        finally:
            scheduler.close()

    @mcp.tool()
    def enterprise_collect_batch(
        keywords: str,
        platform: str = "aiqicha",
        depth: int = 1,
        fields: str = "",
        persona_id: str = "",
        stop_on_blocked: bool = False,
        checkpoint_path: str = "",
    ) -> str:
        """Collect multiple company keywords (comma or newline separated)."""
        config = load_config()
        scheduler = CollectorScheduler(config)
        try:
            summary = run_batch(
                scheduler,
                parse_keywords(keywords),
                platform=Platform(platform),
                depth=depth,
                fields=_parse_fields(fields),
                persona_id=persona_id or None,
                stop_on_blocked=stop_on_blocked,
                checkpoint_path=checkpoint_path or None,
            )
            return json.dumps(summary.to_dict(), ensure_ascii=False)
        finally:
            scheduler.close()

    @mcp.tool()
    def enterprise_search(keyword: str, platform: str = "aiqicha", fields: str = "") -> str:
        """Lightweight search — collect with depth=0 (same default equity fields)."""
        return enterprise_collect(
            keyword=keyword, platform=platform, depth=0, fields=fields
        )

    @mcp.tool()
    def sync_enscan_cookies(cookie_file: str = "") -> str:
        """Push aiqicha cookie from local file into ENScan_GO config.yaml."""
        config = load_config()
        src = Path(cookie_file or config.integrations.playwright.cookie_file)
        enscan = Path(config.integrations.ensan_go.config_path)
        preview = sync_aiqicha_to_enscan(cookie_source=src, enscan_config=enscan)
        return json.dumps({"ok": True, "enscan_config": str(enscan), "cookie_preview": preview})

    @mcp.tool()
    def scout_doctor(probe_sidecars: bool = False) -> str:
        """Report availability of ENScan_GO, Handaas, personas; optional live sidecar probe."""
        config = load_config()
        scheduler = CollectorScheduler(config)
        try:
            return json.dumps(
                build_doctor_report(scheduler, config, probe_sidecars=probe_sidecars),
                ensure_ascii=False,
                indent=2,
            )
        finally:
            scheduler.close()

    @mcp.tool()
    def scout_sidecars() -> str:
        """Live-probe ENScan_GO and proxy_pool sidecars."""
        config = load_config()
        return json.dumps(build_sidecar_report(config), ensure_ascii=False, indent=2)

    @mcp.tool()
    def scout_import_neo4j(dry_run: bool = True) -> str:
        """Import warehouse parquet into Neo4j (dry_run=True counts rows only)."""
        config = load_config()
        wh = Path(config.output.warehouse_dir)
        neo = config.neo4j
        try:
            stats = import_warehouse(
                wh,
                uri=neo.uri,
                user=neo.user,
                password=neo.password,
                dry_run=dry_run,
            )
        except ImportError as exc:
            return json.dumps({"ok": False, "error": str(exc)})
        return json.dumps(
            {"ok": True, "warehouse_dir": str(wh), "dry_run": dry_run, **stats.to_dict()},
            ensure_ascii=False,
        )

    @mcp.tool()
    def scout_drain_retry(
        limit: int = 0,
        include_partial: bool = False,
        dry_run: bool = False,
    ) -> str:
        """Re-run captcha/failed jobs from raw/retry_queue; archive on success."""
        config = load_config()
        scheduler = CollectorScheduler(config)
        try:
            summary = drain_retry_queue(
                scheduler,
                raw_dir=config.output.raw_dir,
                limit=limit,
                include_partial=include_partial,
                dry_run=dry_run,
            )
            return json.dumps(summary.to_dict(), ensure_ascii=False)
        finally:
            scheduler.close()

    return mcp


def main() -> None:
    start_type = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    mcp = create_mcp_server()
    if start_type in ("stdio", "sse", "streamable-http"):
        mcp.run(transport=start_type)
    else:
        print("Usage: enterprise-scout-mcp [stdio|sse|streamable-http]")
        sys.exit(1)


if __name__ == "__main__":
    main()
