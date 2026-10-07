"""CLI - collect, doctor, personas, sync-cookies."""

from __future__ import annotations

import argparse
import json
import sys

from pathlib import Path

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
