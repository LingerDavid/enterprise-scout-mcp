"""MCP server - primary product surface for enterprise intelligence."""

from __future__ import annotations

import json
import sys

from pathlib import Path

from enterprise_scout_mcp.batch import parse_keywords, run_batch
from enterprise_scout_mcp.config import load_config
from enterprise_scout_mcp.diagnostics.doctor import build_doctor_report
from enterprise_scout_mcp.diagnostics.sidecars import build_sidecar_report
from enterprise_scout_mcp.warehouse.neo4j_loader import import_warehouse
from enterprise_scout_mcp.integrations.enscan_cookies import sync_aiqicha_to_enscan
from enterprise_scout_mcp.models import CollectTask, Platform
from enterprise_scout_mcp.scheduler import CollectorScheduler


def create_mcp_server():
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP(
        "enterprise-scout-mcp",
        instructions=(
            "Orchestrated enterprise registry intelligence. "
            "Routes across ENScan_GO (batch), Playwright (interactive), and Handaas API. "
            "Persona-aware with quota, cooldown, and consistency checks."
        ),
    )

    @mcp.tool()
    def enterprise_collect(keyword: str, platform: str = "aiqicha", depth: int = 1) -> str:
        """Collect enterprise info for a company keyword via the orchestrator."""
        config = load_config()
        scheduler = CollectorScheduler(config)
        try:
            task = CollectTask(keyword=keyword, platform=Platform(platform), depth=depth)
            result = scheduler.run(task)
            return json.dumps(
                {
                    "grade": result.grade.value,
                    "channel": result.channel.value,
                    "message": result.message,
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
        stop_on_blocked: bool = False,
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
                stop_on_blocked=stop_on_blocked,
            )
            return json.dumps(summary.to_dict(), ensure_ascii=False)
        finally:
            scheduler.close()

    @mcp.tool()
    def enterprise_search(keyword: str, platform: str = "aiqicha") -> str:
        """Lightweight search - same as collect with depth=0 fields default."""
        return enterprise_collect(keyword=keyword, platform=platform, depth=0)

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
        """Report availability of ENScan_GO, Playwright, Handaas, and loaded personas."""
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
