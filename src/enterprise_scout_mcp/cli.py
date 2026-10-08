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
from enterprise_scout_mcp.integrations.gsxt_session import import_session_file
from enterprise_scout_mcp.models import CollectTask, Dimension, Platform, SourceTier
from enterprise_scout_mcp.persona.engine import PersonaEngine
from enterprise_scout_mcp.scheduler import CollectorScheduler


def _parse_dimensions(text: str) -> tuple[Dimension, ...]:
    if not text or not text.strip():
        return (Dimension.REGISTRY,)
    out: list[Dimension] = []
    for part in text.split(","):
        part = part.strip()
        if part:
            out.append(Dimension(part))
    return tuple(out) if out else (Dimension.REGISTRY,)


def _parse_prefer_tier(name: str | None) -> SourceTier | None:
    if not name:
        return None
    return SourceTier(name.lower())


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
        from enterprise_scout_mcp.defaults import DEFAULT_REGISTRY_FIELDS

        fields = (
            tuple(f.strip() for f in args.fields.split(",") if f.strip())
            if args.fields
            else DEFAULT_REGISTRY_FIELDS
        )
        prefer_tier = _parse_prefer_tier(getattr(args, "prefer_tier", None))
        platform_name = args.platform
        if prefer_tier == SourceTier.L1 and platform_name == "aiqicha":
            platform_name = "gsxt"
        dims = _parse_dimensions(getattr(args, "dims", "") or "")
        task = CollectTask(
            keyword=args.keyword,
            platform=_platform(platform_name),
            fields=fields,
            dimensions=dims,
            prefer_tier=prefer_tier,
            depth=args.depth,
        )
        result = scheduler.run(task, persona_id=args.persona)
        print(
            json.dumps(
                {
                    "grade": result.grade.value,
                    "channel": result.channel.value,
                    "source_tier": result.source_tier.value if result.source_tier else "",
                    "dimension": result.dimension.value if result.dimension else "",
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
        from enterprise_scout_mcp.defaults import DEFAULT_REGISTRY_FIELDS

        fields = (
            tuple(f.strip() for f in args.fields.split(",") if f.strip())
            if args.fields
            else DEFAULT_REGISTRY_FIELDS
        )
        summary = run_batch(
            scheduler,
            keywords,
            platform=_platform(args.platform),
            depth=args.depth,
            fields=fields,
            persona_id=args.persona,
            stop_on_blocked=args.stop_on_blocked,
            checkpoint_path=args.checkpoint,
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


def cmd_sync_gsxt_session(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    root = Path(config.state_dir)
    if not root.is_absolute():
        from enterprise_scout_mcp.config import resolve_project_root

        root = resolve_project_root(args.config) / root
    src = Path(args.from_file)
    dest = Path(args.session_file or config.integrations.gsxt.session_file)
    if not dest.is_absolute():
        from enterprise_scout_mcp.config import resolve_project_root

        dest = resolve_project_root(args.config) / dest
    preview = import_session_file(src, dest)
    print(
        json.dumps(
            {
                "ok": True,
                "session_file": str(dest),
                "mode": args.mode,
                "cookie_preview": preview,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_smoke_registry_l1(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    scheduler = CollectorScheduler(config)
    try:
        task = CollectTask(
            keyword=args.keyword,
            platform=Platform.GSXT,
            dimensions=(Dimension.REGISTRY,),
            prefer_tier=SourceTier.L1,
            fields=("enterprise_info",),
            depth=0,
        )
        result = scheduler.run(task, persona_id=args.persona)
        print(
            json.dumps(
                {
                    "grade": result.grade.value,
                    "channel": result.channel.value,
                    "source_tier": result.source_tier.value if result.source_tier else "",
                    "message": result.message,
                    "data": result.data,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if result.grade.value in ("ok", "partial") else 1
    finally:
        scheduler.close()


def cmd_drain_retry(args: argparse.Namespace) -> int:
    from enterprise_scout_mcp.retry import drain_retry_queue

    config = load_config(args.config)
    scheduler = CollectorScheduler(config)
    try:
        summary = drain_retry_queue(
            scheduler,
            raw_dir=config.output.raw_dir,
            limit=args.limit,
            include_partial=args.include_partial,
            dry_run=args.dry_run,
        )
        print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
        return 0 if summary.failed == 0 else 1
    finally:
        scheduler.close()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="escout", description="Enterprise collection orchestrator")
    p.add_argument("-c", "--config", default=None, help="Path to config.yaml")
    sub = p.add_subparsers(dest="command", required=True)

    collect = sub.add_parser("collect", help="Run one collection task")
    collect.add_argument("keyword", help="Company name or keyword")
    collect.add_argument("-p", "--platform", default="aiqicha", type=str)
    collect.add_argument("-f", "--fields", default="", help="Comma-separated ENScan fields")
    collect.add_argument("--dims", default="", help="Dimensions: registry (L1 spike)")
    collect.add_argument(
        "--prefer-tier",
        default=None,
        choices=["l1", "l2", "l3"],
        help="Source tier: l1=GSXT official, l2=ENScan",
    )
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
    batch.add_argument(
        "--checkpoint",
        default=None,
        help="JSON checkpoint path for resume (skip already-done keywords)",
    )
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

    gsxt_sess = sub.add_parser(
        "sync-gsxt-session",
        help="Import GSXT personal-login cookies (export from browser after shiming login)",
    )
    gsxt_sess.add_argument("--from-file", required=True, help="JSON cookie export")
    gsxt_sess.add_argument("--session-file", default=None, help="Override session path")
    gsxt_sess.add_argument("--mode", default="personal", choices=["personal"])
    gsxt_sess.set_defaults(func=cmd_sync_gsxt_session)

    smoke_l1 = sub.add_parser(
        "smoke-registry-l1",
        help="Live L1 GSXT registry spike (needs sync-gsxt-session)",
    )
    smoke_l1.add_argument("keyword", nargs="?", default="苏州挚途")
    smoke_l1.add_argument("--persona", default=None)
    smoke_l1.set_defaults(func=cmd_smoke_registry_l1)

    drain = sub.add_parser("drain-retry", help="Re-run jobs from raw/retry_queue")
    drain.add_argument("--limit", type=int, default=0, help="Max jobs (0 = all)")
    drain.add_argument(
        "--include-partial",
        action="store_true",
        help="Also retry grade=partial files under raw/",
    )
    drain.add_argument("--dry-run", action="store_true", help="List jobs without collecting")
    drain.set_defaults(func=cmd_drain_retry)

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
