"""CLI - collect, doctor, personas, sync-cookies."""

from __future__ import annotations

import argparse
import json
import sys

from pathlib import Path

from enterprise_scout_mcp.batch import keywords_from_file, run_batch
from enterprise_scout_mcp.config import load_config
from enterprise_scout_mcp.diagnostics.doctor import build_doctor_report
from enterprise_scout_mcp.diagnostics.sidecars import build_sidecar_report
from enterprise_scout_mcp.integrations.enscan_cookies import sync_aiqicha_to_enscan
from enterprise_scout_mcp.models import CollectTask, Platform
from enterprise_scout_mcp.persona.engine import PersonaEngine
from enterprise_scout_mcp.scheduler import CollectorScheduler


def _platform(name: str) -> Platform:
    try:
        return Platform(name.lower())
    except ValueError as exc:
        choices = [p.value for p in Platform]
        raise argparse.ArgumentTypeError(f"unknown platform {name!r}; choose from {choices}") from exc


def cmd_collect(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    scheduler = CollectorScheduler(config)
    try:
        fields = tuple(args.fields.split(",")) if args.fields else ("enterprise_info",)
        task = CollectTask(
            keyword=args.keyword,
            platform=_platform(args.platform),
            fields=fields,
            depth=args.depth,
        )
        result = scheduler.run(task, persona_id=args.persona)
        print(
            json.dumps(
                {
                    "grade": result.grade.value,
                    "channel": result.channel.value,
                    "message": result.message,
                    "persona_id": result.persona_id,
                    "data_keys": list(result.data.keys()),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if result.grade.value in ("ok", "partial") else 1
    finally:
        scheduler.close()


def cmd_doctor(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    scheduler = CollectorScheduler(config)
    try:
        print(
            json.dumps(
                build_doctor_report(scheduler, config, probe_sidecars=args.probe),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    finally:
        scheduler.close()


def cmd_smoke_sidecars(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    report = build_sidecar_report(config, timeout=args.timeout)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    ensan_ok = report["ensan_go"].get("ok", False)
    proxy_cfg = report["proxy_pool"]
    proxy_ok = proxy_cfg.get("skipped") or proxy_cfg.get("reachable", False)
    return 0 if ensan_ok and proxy_ok else 1


def cmd_personas(_args: argparse.Namespace) -> int:
    config = load_config(_args.config)
    for pid in PersonaEngine(config.personas.dir).list_ids():
        print(pid)
    return 0


def cmd_register_hermes(args: argparse.Namespace) -> int:
    import subprocess

    script = Path(__file__).resolve().parents[2] / "scripts" / "register_hermes.py"
    cmd = [sys.executable, str(script)]
    if args.dry_run:
        cmd.append("--dry-run")
    if args.no_venv:
        cmd.append("--no-venv")
    subprocess.run(cmd, check=True)
    return 0


def cmd_collect_batch(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    scheduler = CollectorScheduler(config)
    try:
        if args.file:
            keywords = keywords_from_file(args.file)
        elif args.keywords:
            from enterprise_scout_mcp.batch import parse_keywords

            keywords = parse_keywords(args.keywords)
        else:
            print("provide --file or positional keywords", file=sys.stderr)
            return 2
        fields = tuple(args.fields.split(",")) if args.fields else ("enterprise_info",)
        summary = run_batch(
            scheduler,
            keywords,
            platform=_platform(args.platform),
            depth=args.depth,
            fields=fields,
            persona_id=args.persona,
            stop_on_blocked=args.stop_on_blocked,
        )
        print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
        failed = summary.counts.get("error", 0) + summary.counts.get("blocked", 0)
        return 0 if failed == 0 else 1
    finally:
        scheduler.close()


def cmd_import_neo4j(args: argparse.Namespace) -> int:
    import subprocess

    script = Path(__file__).resolve().parents[2] / "scripts" / "import_warehouse_neo4j.py"
    cmd = [sys.executable, str(script)]
    if args.config:
        cmd.extend(["-c", args.config])
    if args.warehouse_dir:
        cmd.extend(["--warehouse-dir", args.warehouse_dir])
    if args.uri:
        cmd.extend(["--uri", args.uri])
    if args.user:
        cmd.extend(["--user", args.user])
    if args.password:
        cmd.extend(["--password", args.password])
    if args.dry_run:
        cmd.append("--dry-run")
    proc = subprocess.run(cmd, check=False)
    return proc.returncode


def cmd_smoke_collect(args: argparse.Namespace) -> int:
    import subprocess

    script = Path(__file__).resolve().parents[2] / "scripts" / "smoke_collect.py"
    cmd = [sys.executable, str(script), args.keyword]
    if args.config:
        cmd.extend(["-c", args.config])
    cmd.extend(["-p", args.platform])
    if args.skip_sidecar_check:
        cmd.append("--skip-sidecar-check")
    proc = subprocess.run(cmd, check=False)
    return proc.returncode


def cmd_sync_cookies(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    cookie_src = Path(args.from_file or config.integrations.playwright.cookie_file)
    enscan_cfg = Path(args.enscan_config or config.integrations.ensan_go.config_path)
    preview = sync_aiqicha_to_enscan(cookie_source=cookie_src, enscan_config=enscan_cfg)
    print(json.dumps({"ok": True, "enscan_config": str(enscan_cfg), "cookie_preview": preview}))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="escout", description="Enterprise collection orchestrator")
    p.add_argument("-c", "--config", default=None, help="Path to config.yaml")
    sub = p.add_subparsers(dest="command", required=True)

    collect = sub.add_parser("collect", help="Run one collection task")
    collect.add_argument("keyword", help="Company name or keyword")
    collect.add_argument("-p", "--platform", default="aiqicha", type=str)
    collect.add_argument("-f", "--fields", default="", help="Comma-separated ENScan fields")
    collect.add_argument("--depth", type=int, default=1)
    collect.add_argument("--persona", default=None)
    collect.set_defaults(func=cmd_collect)

    batch = sub.add_parser("collect-batch", help="Collect many keywords from text or file")
    batch.add_argument("keywords", nargs="?", default="", help="Comma/newline separated keywords")
    batch.add_argument("--file", default=None, help="Text file with one keyword per line")
    batch.add_argument("-p", "--platform", default="aiqicha", type=str)
    batch.add_argument("-f", "--fields", default="", help="Comma-separated ENScan fields")
    batch.add_argument("--depth", type=int, default=1)
    batch.add_argument("--persona", default=None)
    batch.add_argument("--stop-on-blocked", action="store_true")
    batch.set_defaults(func=cmd_collect_batch)

    neo4j = sub.add_parser("import-neo4j", help="Import warehouse parquet into Neo4j")
    neo4j.add_argument("--warehouse-dir", default=None)
    neo4j.add_argument("--uri", default=None)
    neo4j.add_argument("--user", default=None)
    neo4j.add_argument("--password", default=None)
    neo4j.add_argument("--dry-run", action="store_true")
    neo4j.set_defaults(func=cmd_import_neo4j)

    doctor = sub.add_parser("doctor", help="Check integration availability")
    doctor.add_argument(
        "--probe",
        action="store_true",
        help="Live-probe ENScan / proxy_pool sidecars (short timeout)",
    )
    doctor.set_defaults(func=cmd_doctor)

    smoke = sub.add_parser("smoke-sidecars", help="Probe ENScan and proxy_pool reachability")
    smoke.add_argument("--timeout", type=float, default=2.0)
    smoke.set_defaults(func=cmd_smoke_sidecars)

    smoke_collect = sub.add_parser("smoke-collect", help="Live collect one keyword (integration smoke)")
    smoke_collect.add_argument("keyword", nargs="?", default="??")
    smoke_collect.add_argument("-p", "--platform", default="aiqicha")
    smoke_collect.add_argument("--skip-sidecar-check", action="store_true")
    smoke_collect.set_defaults(func=cmd_smoke_collect)

    personas = sub.add_parser("personas", help="List persona ids")
    personas.set_defaults(func=cmd_personas)

    sync = sub.add_parser("sync-cookies", help="Push aiqicha cookie into ENScan_GO config.yaml")
    sync.add_argument("--from-file", default=None, help="Cookie file (default: playwright.cookie_file)")
    sync.add_argument("--enscan-config", default=None, help="ENScan config path")
    sync.set_defaults(func=cmd_sync_cookies)

    reg = sub.add_parser("register-hermes", help="Add enterprise-scout-mcp to ~/.hermes/config.yaml")
    reg.add_argument("--dry-run", action="store_true")
    reg.add_argument("--no-venv", action="store_true")
    reg.set_defaults(func=cmd_register_hermes)

    return p


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    code = args.func(args)
    sys.exit(code)
