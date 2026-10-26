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
from enterprise_scout_mcp.sessions.registry import import_session, list_sessions, warmup_gsxt_session
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
        invest_min = getattr(args, "invest_min", None)
        task = CollectTask(
            keyword=args.keyword,
            platform=_platform(platform_name),
            fields=fields,
            dimensions=dims,
            prefer_tier=prefer_tier,
            depth=args.depth,
            invest_min=float(invest_min) if invest_min is not None else None,
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


def cmd_equity_tree(args: argparse.Namespace) -> int:
    from enterprise_scout_mcp.warehouse.equity_tree import build_equity_tree

    config = load_config(args.config)
    tree = build_equity_tree(
        Path(config.output.warehouse_dir),
        args.center,
        max_depth=args.depth,
        min_ratio=args.min_ratio,
        max_nodes=args.max_nodes,
        include_supply=bool(args.include_supply),
    )
    print(json.dumps(tree, ensure_ascii=False, indent=2))
    return 0 if tree.get("resolved_name") else 1


def cmd_equity_expand(args: argparse.Namespace) -> int:
    from enterprise_scout_mcp.warehouse.equity_expand import expand_equity_tree

    config = load_config(args.config)
    scheduler = CollectorScheduler(config)
    try:

        def _collect(task: CollectTask):
            return scheduler.run(task, persona_id=args.persona)

        out = expand_equity_tree(
            Path(config.output.warehouse_dir),
            args.center,
            collect_fn=_collect,
            max_depth=args.depth,
            min_ratio=args.min_ratio,
            max_nodes=args.max_nodes,
            max_collects=args.max_collects,
        )
    finally:
        scheduler.close()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("ok") else 1


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


def _print_json(payload: dict) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(text.encode("utf-8", errors="replace"))
        sys.stdout.buffer.write(b"\n")


def cmd_sessions(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    if args.sessions_cmd == "list":
        _print_json(list_sessions(config))
        return 0
    if args.sessions_cmd == "import":
        if not args.from_file:
            print("error: --from-file required", file=sys.stderr)
            return 2
        try:
            result = import_session(config, args.name, from_file=Path(args.from_file))
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        _print_json(result)
        return 0
    if args.sessions_cmd == "warmup":
        if args.name != "gsxt":
            print("error: warmup only supports gsxt", file=sys.stderr)
            return 2
        if args.from_file:
            import_session(config, "gsxt", from_file=Path(args.from_file))
        try:
            result = warmup_gsxt_session(config)
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        _print_json(result)
        return 0
    if args.sessions_cmd == "cdp-hint":
        from enterprise_scout_mcp.sessions.registry import gsxt_cdp_hint

        _print_json(gsxt_cdp_hint(config))
        return 0
    return 2


def cmd_sync_cookies(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    if not args.from_file:
        print("error: --from-file required (or use: escout sessions import aiqicha)", file=sys.stderr)
        return 2
    try:
        result = import_session(config, "aiqicha", from_file=Path(args.from_file))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    _print_json(result)
    return 0


def cmd_sync_gsxt_session(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    if args.warmup:
        if args.from_file:
            import_session(config, "gsxt", from_file=Path(args.from_file))
        try:
            result = warmup_gsxt_session(config)
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        _print_json({**result, "mode": args.mode})
        return 0
    if not args.from_file:
        print("error: --from-file required unless --warmup", file=sys.stderr)
        return 2
    try:
        result = import_session(config, "gsxt", from_file=Path(args.from_file))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    _print_json({**result, "mode": args.mode})
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
        payload = json.dumps(
            {
                "grade": result.grade.value,
                "channel": result.channel.value,
                "source_tier": result.source_tier.value if result.source_tier else "",
                "degraded": result.degraded,
                "message": result.message,
                "data": result.data,
            },
            ensure_ascii=False,
            indent=2,
        )
        try:
            print(payload)
        except UnicodeEncodeError:
            sys.stdout.buffer.write(payload.encode("utf-8", errors="replace"))
            sys.stdout.buffer.write(b"\n")
        return 0 if result.grade.value in ("ok", "partial") else 1
    finally:
        scheduler.close()


def cmd_serve(args: argparse.Namespace) -> int:
    from enterprise_scout_mcp.http.serve import main as serve_main

    argv = ["--host", args.host, "--port", str(args.port)]
    if args.config:
        argv.extend(["--config", args.config])
    return serve_main(argv)


def cmd_verify(args: argparse.Namespace) -> int:
    from enterprise_scout_mcp.diagnostics.verify import build_verify_report

    config = load_config(args.config)
    scheduler = CollectorScheduler(config)
    try:
        report = build_verify_report(scheduler, config)
        if args.summary:
            summary = {
                "ok": report["ok"],
                "failed": report["failed"],
                "checks": report["checks"],
                "note": report["note"],
            }
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1
    finally:
        scheduler.close()


def cmd_corpus_init(args: argparse.Namespace) -> int:
    from enterprise_scout_mcp.config import resolve_project_root
    from enterprise_scout_mcp.integrations.corpus_init import init_corpus_dirs

    config = load_config(args.config)
    root = resolve_project_root()
    corpus = config.integrations.corpus

    def _dir(rel: str) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else root / p

    report = init_corpus_dirs(
        _dir(corpus.l3_dir),
        _dir(corpus.judicial_dir),
        _dir(corpus.listed_dir),
        write_samples=not args.no_samples,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def cmd_corpus_status(args: argparse.Namespace) -> int:
    from enterprise_scout_mcp.config import resolve_project_root
    from enterprise_scout_mcp.integrations.corpus_lookup import corpus_dir_stats

    config = load_config(args.config)
    root = resolve_project_root()
    corpus = config.integrations.corpus

    def _dir(rel: str) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else root / p

    report = {
        "enabled": corpus.enabled,
        "l3": corpus_dir_stats(_dir(corpus.l3_dir)),
        "judicial": corpus_dir_stats(_dir(corpus.judicial_dir)),
        "listed": corpus_dir_stats(_dir(corpus.listed_dir)),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def cmd_corpus_backfill_segments(args: argparse.Namespace) -> int:
    from enterprise_scout_mcp.config import resolve_project_root
    from enterprise_scout_mcp.integrations.listed_segments_backfill import backfill_listed_segments

    config = load_config(args.config)
    root = resolve_project_root()

    def _dir(rel: str) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else root / p

    warehouse_dir = _dir(config.output.warehouse_dir)
    limit = int(args.limit) if int(args.limit) > 0 else None
    progress = Path(args.progress) if args.progress else None
    summary = backfill_listed_segments(
        warehouse_dir,
        workers=int(args.workers),
        limit=limit,
        progress_path=progress,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary.get("segments_written", 0) > 0 else 1


def cmd_corpus_backfill_f10(args: argparse.Namespace) -> int:
    from enterprise_scout_mcp.config import resolve_project_root
    from enterprise_scout_mcp.integrations.listed_f10_backfill import backfill_listed_f10

    config = load_config(args.config)
    root = resolve_project_root()

    def _dir(rel: str) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else root / p

    warehouse_dir = _dir(config.output.warehouse_dir)
    limit = int(args.limit) if int(args.limit) > 0 else None
    progress = Path(args.progress) if args.progress else None
    tables = tuple(t.strip() for t in str(args.tables or "").split(",") if t.strip()) or None
    summary = backfill_listed_f10(
        warehouse_dir,
        tables=tables or (
            "segments",
            "holders",
            "capital",
            "executives",
            "dividends",
            "control",
        ),
        workers=int(args.workers),
        limit=limit,
        progress_path=progress,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    written = sum(int((v or {}).get("rows_written") or 0) for v in (summary.get("results") or {}).values())
    return 0 if written > 0 or summary.get("error") is None else 1


def cmd_corpus_backfill_facts_em(args: argparse.Namespace) -> int:
    from enterprise_scout_mcp.config import resolve_project_root
    from enterprise_scout_mcp.integrations.listed_facts_em_backfill import backfill_listed_facts_em

    config = load_config(args.config)
    root = resolve_project_root()

    def _dir(rel: str) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else root / p

    warehouse_dir = _dir(config.output.warehouse_dir)
    limit = int(args.limit) if int(args.limit) > 0 else None
    progress = Path(args.progress) if args.progress else None
    summary = backfill_listed_facts_em(
        warehouse_dir,
        workers=int(args.workers),
        limit=limit,
        page_size=int(args.page_size),
        progress_path=progress,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary.get("facts_written", 0) > 0 else 1


def cmd_corpus_sync_facts(args: argparse.Namespace) -> int:
    from enterprise_scout_mcp.config import resolve_project_root
    from enterprise_scout_mcp.integrations.listed_facts_bridge import sync_panel_to_listed_facts

    config = load_config(args.config)
    root = resolve_project_root()

    def _dir(rel: str) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else root / p

    warehouse_dir = _dir(config.output.warehouse_dir)
    panel_dir = Path(args.panel_dir) if args.panel_dir else root.parent / "tradecraft" / "data"
    if not panel_dir.is_absolute():
        panel_dir = root / panel_dir
    report = sync_panel_to_listed_facts(
        panel_dir,
        warehouse_dir,
        dry_run=bool(args.dry_run),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


def cmd_listed_dossier(args: argparse.Namespace) -> int:
    from enterprise_scout_mcp.config import resolve_project_root
    from enterprise_scout_mcp.integrations.listed_dossier import build_listed_dossier

    config = load_config(args.config)
    root = resolve_project_root()

    def _dir(rel: str) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else root / p

    dossier = build_listed_dossier(
        _dir(config.output.warehouse_dir),
        args.symbol,
        include_peers=not args.no_peers,
    )
    print(json.dumps(dossier, ensure_ascii=False, indent=2))
    return 0 if dossier.get("ok") else 1


def cmd_corpus_import_listed(args: argparse.Namespace) -> int:
    from enterprise_scout_mcp.config import resolve_project_root
    from enterprise_scout_mcp.integrations.listed_corpus import import_listed_corpus

    config = load_config(args.config)
    root = resolve_project_root()

    def _dir(rel: str) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else root / p

    corpus_dir = Path(args.corpus_dir) if args.corpus_dir else _dir(config.integrations.corpus.listed_dir)
    if not corpus_dir.is_absolute():
        corpus_dir = root / corpus_dir
    warehouse_dir = _dir(config.output.warehouse_dir)
    report = import_listed_corpus(
        corpus_dir,
        warehouse_dir,
        dry_run=bool(args.dry_run),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("records", 0) or report.get("dry_run") else 1


def cmd_corpus_extract_equity(args: argparse.Namespace) -> int:
    """Re-extract equity tables from an on-disk annual PDF (no download)."""
    from enterprise_scout_mcp.config import resolve_project_root
    from enterprise_scout_mcp.integrations.listed_equity_extract import extract_and_store_equity
    from enterprise_scout_mcp.sources.cninfo import resolve_listing

    config = load_config(args.config)
    root = resolve_project_root()

    def _dir(rel: str) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else root / p

    listing = resolve_listing(args.symbol)
    if listing is None:
        print(json.dumps({"skipped": ["unresolved_symbol"]}, ensure_ascii=False, indent=2))
        return 1
    security_id, code, _column = listing
    exchange = security_id.split(":", 1)[0]
    corpus_dir = Path(args.corpus_dir) if args.corpus_dir else _dir(config.integrations.corpus.listed_dir)
    if not corpus_dir.is_absolute():
        corpus_dir = root / corpus_dir
    warehouse_dir = None if args.no_warehouse else _dir(config.output.warehouse_dir)
    pdf_path = Path(args.pdf)
    if not pdf_path.is_file():
        alt = corpus_dir / "pdf" / args.pdf
        if alt.is_file():
            pdf_path = alt
    report = extract_and_store_equity(
        pdf_path,
        security_id=security_id,
        issuer_id=str(args.issuer_id or security_id),
        issuer_name=str(args.issuer_name or ""),
        exchange=exchange,
        code=code,
        document_id=str(args.document_id or f"local:{pdf_path.name}"),
        document_date=str(args.document_date or ""),
        title=str(args.title or ""),
        year=args.year or None,
        corpus_dir=None if args.no_corpus else corpus_dir,
        warehouse_dir=warehouse_dir,
        dry_run=bool(args.dry_run),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report.get("skipped") and not (
        report.get("holders")
        or report.get("subsidiaries")
        or report.get("suppliers")
        or report.get("investments")
        or report.get("edges")
    ):
        return 1
    return 0


def cmd_corpus_reextract_equity_batch(args: argparse.Namespace) -> int:
    """Re-extract annual PDFs already in corpus → listed tables + edges/equity."""
    from enterprise_scout_mcp.config import resolve_project_root
    from enterprise_scout_mcp.integrations.listed_equity_extract import (
        batch_reextract_listed_equity,
    )

    config = load_config(args.config)
    root = resolve_project_root()

    def _dir(rel: str) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else root / p

    corpus_dir = Path(args.corpus_dir) if args.corpus_dir else _dir(config.integrations.corpus.listed_dir)
    if not corpus_dir.is_absolute():
        corpus_dir = root / corpus_dir
    warehouse_dir = None if args.no_warehouse else _dir(config.output.warehouse_dir)
    progress = (
        Path(args.progress)
        if args.progress
        else corpus_dir / "_reextract_equity_batch.jsonl"
    )
    summary = batch_reextract_listed_equity(
        corpus_dir,
        warehouse_dir=warehouse_dir,
        progress_path=progress,
        limit=int(args.limit),
        skip_ok=not args.no_skip_ok,
        dry_run=bool(args.dry_run),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary.get("failed", 0) == 0 else 1


def cmd_corpus_sample_listed(args: argparse.Namespace) -> int:
    """Index cninfo annual PDF + equity extract / Eastmoney holders for one listing."""
    from enterprise_scout_mcp.config import resolve_project_root
    from enterprise_scout_mcp.integrations.listed_sample import sample_listed_disclosure

    config = load_config(args.config)
    root = resolve_project_root()

    def _dir(rel: str) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else root / p

    corpus_dir = Path(args.corpus_dir) if args.corpus_dir else _dir(config.integrations.corpus.listed_dir)
    if not corpus_dir.is_absolute():
        corpus_dir = root / corpus_dir
    warehouse_dir = None if args.no_warehouse else _dir(config.output.warehouse_dir)
    pdf_dir = Path(args.pdf_dir) if args.pdf_dir else corpus_dir / "pdf"
    report = sample_listed_disclosure(
        args.symbol,
        corpus_dir=corpus_dir,
        warehouse_dir=warehouse_dir,
        pdf_dir=pdf_dir,
        year=args.year or None,
        download=not args.no_download,
        dry_run=bool(args.dry_run),
        prospectus_fallback=not args.no_prospectus_fallback,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report.get("skipped") and not report.get("picked") and not report.get("holders"):
        return 1
    return 0


def cmd_corpus_sample_prospectus(args: argparse.Namespace) -> int:
    """Download 招股说明书 and extract named suppliers into edges/equity."""
    from enterprise_scout_mcp.config import resolve_project_root
    from enterprise_scout_mcp.integrations.listed_prospectus import sample_prospectus_disclosure

    config = load_config(args.config)
    root = resolve_project_root()

    def _dir(rel: str) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else root / p

    corpus_dir = Path(args.corpus_dir) if args.corpus_dir else _dir(config.integrations.corpus.listed_dir)
    if not corpus_dir.is_absolute():
        corpus_dir = root / corpus_dir
    warehouse_dir = None if args.no_warehouse else _dir(config.output.warehouse_dir)
    pdf_dir = Path(args.pdf_dir) if args.pdf_dir else corpus_dir / "pdf"
    report = sample_prospectus_disclosure(
        args.symbol,
        corpus_dir=corpus_dir,
        warehouse_dir=warehouse_dir,
        pdf_dir=pdf_dir,
        download=not args.no_download,
        dry_run=bool(args.dry_run),
        suppliers_only=not args.full_equity,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report.get("skipped") and not report.get("suppliers") and not report.get("edges"):
        return 1
    return 0


def cmd_corpus_sample_listed_batch(args: argparse.Namespace) -> int:
    """Batch-download missing annual PDFs + top-10 holders (resumable)."""
    from enterprise_scout_mcp.config import resolve_project_root
    from enterprise_scout_mcp.integrations.listed_sample import (
        batch_sample_listed_disclosure,
        symbols_from_instruments_parquet,
        symbols_from_text_file,
    )

    config = load_config(args.config)
    root = resolve_project_root()

    def _dir(rel: str) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else root / p

    corpus_dir = Path(args.corpus_dir) if args.corpus_dir else _dir(config.integrations.corpus.listed_dir)
    if not corpus_dir.is_absolute():
        corpus_dir = root / corpus_dir
    warehouse_dir = None if args.no_warehouse else _dir(config.output.warehouse_dir)
    pdf_dir = Path(args.pdf_dir) if args.pdf_dir else corpus_dir / "pdf"
    progress = (
        Path(args.progress)
        if args.progress
        else corpus_dir / "_sample_listed_batch.jsonl"
    )

    if args.instruments:
        symbols = symbols_from_instruments_parquet(Path(args.instruments))
    elif args.symbols_file:
        symbols = symbols_from_text_file(Path(args.symbols_file))
    else:
        print("error: pass --instruments or --symbols-file", file=sys.stderr)
        return 2

    summary = batch_sample_listed_disclosure(
        symbols,
        corpus_dir=corpus_dir,
        warehouse_dir=warehouse_dir,
        pdf_dir=pdf_dir,
        progress_path=progress,
        year=args.year or None,
        download=not args.no_download,
        delay_seconds=float(args.delay),
        limit=int(args.limit),
        skip_existing_corpus=not args.no_skip_existing,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary.get("failed", 0) == 0 else 1


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
    collect.add_argument(
        "--dims",
        default="",
        help="Dimensions: registry,equity,digital,ip,credit,judicial (comma-separated)",
    )
    collect.add_argument(
        "--prefer-tier",
        default=None,
        choices=["l1", "l2", "l3"],
        help="Source tier: l1=GSXT official, l2=ENScan",
    )
    collect.add_argument("--depth", type=int, default=1)
    collect.add_argument(
        "--invest-min",
        type=float,
        default=None,
        help="ENScan invest= ratio filter (percent); omit to leave unset",
    )
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

    etree = sub.add_parser(
        "equity-tree",
        help="BFS equity tree from warehouse edges (local; no live pull)",
    )
    etree.add_argument("center", help="Company name (must appear in edges)")
    etree.add_argument("--depth", type=int, default=2)
    etree.add_argument("--min-ratio", type=float, default=0.0, help="Filter invest edges below %%")
    etree.add_argument("--max-nodes", type=int, default=200)
    etree.add_argument("--include-supply", action="store_true")
    etree.set_defaults(func=cmd_equity_tree)

    eexp = sub.add_parser(
        "equity-expand",
        help="Iteratively collect missing equity neighbors via aiqicha (refuses tyc)",
    )
    eexp.add_argument("center", help="Company name")
    eexp.add_argument("--depth", type=int, default=2)
    eexp.add_argument("--min-ratio", type=float, default=20.0)
    eexp.add_argument("--max-nodes", type=int, default=200)
    eexp.add_argument("--max-collects", type=int, default=30)
    eexp.add_argument("--persona", default=None)
    eexp.set_defaults(func=cmd_equity_expand)

    neo4j = sub.add_parser("import-neo4j", help="Import warehouse parquet into Neo4j")
    neo4j.add_argument("--warehouse-dir", default=None)
    neo4j.add_argument("--uri", default=None)
    neo4j.add_argument("--user", default=None)
    neo4j.add_argument("--password", default=None)
    neo4j.add_argument("--dry-run", action="store_true")
    neo4j.set_defaults(func=cmd_import_neo4j)

    verify = sub.add_parser("verify", help="Architecture backend checklist (includes Fine UI scaffold)")
    verify.add_argument("--summary", action="store_true", help="Print checks only, omit full doctor")
    verify.set_defaults(func=cmd_verify)

    serve = sub.add_parser("serve", help="Fine UI HTTP server (API + optional ui/dist)")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8790)
    serve.set_defaults(func=cmd_serve)

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

    sess = sub.add_parser("sessions", help="Unified cookie/session registry (config.sessions.*)")
    sess_sub = sess.add_subparsers(dest="sessions_cmd", required=True)
    sess_list = sess_sub.add_parser("list", help="Show all session paths and readiness")
    sess_list.set_defaults(func=cmd_sessions, sessions_cmd="list")
    sess_import = sess_sub.add_parser("import", help="Import browser export into a session slot")
    sess_import.add_argument("name", choices=["gsxt", "aiqicha"])
    sess_import.add_argument("--from-file", required=True, help="Browser export or cookie text file")
    sess_import.set_defaults(func=cmd_sessions, sessions_cmd="import")
    sess_warmup = sess_sub.add_parser("warmup", help="Browser refresh session cookies")
    sess_warmup.add_argument("name", choices=["gsxt"], default="gsxt", nargs="?")
    sess_warmup.add_argument("--from-file", default=None, help="Optional import before warmup")
    sess_warmup.set_defaults(func=cmd_sessions, sessions_cmd="warmup")
    sess_cdp = sess_sub.add_parser(
        "cdp-hint",
        help="How to attach real Chrome via CDP for GSXT (Ruishu / NWAF bypass)",
    )
    sess_cdp.set_defaults(func=cmd_sessions, sessions_cmd="cdp-hint")

    sync = sub.add_parser("sync-cookies", help="[alias] escout sessions import aiqicha")
    sync.add_argument("--from-file", default=None, help="Cookie file")
    sync.add_argument("--enscan-config", default=None, help="Ignored — uses integrations.ensan_go.config_path")
    sync.set_defaults(func=cmd_sync_cookies)

    gsxt_sess = sub.add_parser(
        "sync-gsxt-session",
        help="Import GSXT personal-login cookies (export from browser after shiming login)",
    )
    gsxt_sess.add_argument("--from-file", default=None, help="JSON cookie export (browser / EditThisCookie)")
    gsxt_sess.add_argument(
        "--warmup",
        action="store_true",
        help="Headless browser refresh JSL+CT cookies (requires pip install -e '.[browser]')",
    )
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

    corpus = sub.add_parser("corpus", help="L3 / judicial / listed local corpus")
    corpus_sub = corpus.add_subparsers(dest="corpus_cmd", required=True)
    corpus_status = corpus_sub.add_parser("status", help="Show corpus dirs and file counts")
    corpus_status.set_defaults(func=cmd_corpus_status, corpus_cmd="status")
    corpus_init = corpus_sub.add_parser("init", help="Create corpus dirs and example JSONL")
    corpus_init.add_argument("--no-samples", action="store_true", help="Skip writing _example.jsonl")
    corpus_init.set_defaults(func=cmd_corpus_init, corpus_cmd="init")
    corpus_import = corpus_sub.add_parser(
        "import-listed",
        help="Import listed JSON/JSONL into warehouse/listed parquet",
    )
    corpus_import.add_argument(
        "--corpus-dir",
        default="",
        help="Override corpus.listed_dir",
    )
    corpus_import.add_argument("--dry-run", action="store_true", help="Count rows without writing")
    corpus_import.set_defaults(func=cmd_corpus_import_listed, corpus_cmd="import-listed")
    corpus_extract = corpus_sub.add_parser(
        "extract-equity",
        help="Extract holders/subsidiaries/suppliers/invest/control from an on-disk annual PDF",
    )
    corpus_extract.add_argument("symbol", help="600519.SH or SSE:600519")
    corpus_extract.add_argument(
        "--pdf",
        required=True,
        help="PDF path, or filename under corpus/pdf/",
    )
    corpus_extract.add_argument("--year", default="", help="Report period YYYY")
    corpus_extract.add_argument("--document-id", default="", help="Stable document id")
    corpus_extract.add_argument("--document-date", default="", help="YYYY-MM-DD announcement date")
    corpus_extract.add_argument("--title", default="", help="Announcement title (period hint)")
    corpus_extract.add_argument("--issuer-id", default="", help="Credit code (default security_id)")
    corpus_extract.add_argument("--issuer-name", default="", help="Issuer display name")
    corpus_extract.add_argument("--corpus-dir", default="", help="Override corpus.listed_dir")
    corpus_extract.add_argument("--no-corpus", action="store_true", help="Skip corpus JSON write")
    corpus_extract.add_argument("--no-warehouse", action="store_true", help="Skip warehouse write")
    corpus_extract.add_argument("--dry-run", action="store_true", help="Extract without writing")
    corpus_extract.set_defaults(func=cmd_corpus_extract_equity, corpus_cmd="extract-equity")
    corpus_reextract = corpus_sub.add_parser(
        "reextract-equity-batch",
        help="Re-extract corpus annual PDFs → listed parquet + edges/equity (supply/invest)",
    )
    corpus_reextract.add_argument("--corpus-dir", default="", help="Override corpus.listed_dir")
    corpus_reextract.add_argument(
        "--progress",
        default="",
        help="Resume JSONL (default corpus/_reextract_equity_batch.jsonl)",
    )
    corpus_reextract.add_argument("--limit", type=int, default=0, help="Max records (0=all)")
    corpus_reextract.add_argument(
        "--no-skip-ok",
        action="store_true",
        help="Re-process symbols already ok in progress",
    )
    corpus_reextract.add_argument("--no-warehouse", action="store_true", help="Corpus JSON only")
    corpus_reextract.add_argument("--dry-run", action="store_true", help="Extract without writing")
    corpus_reextract.set_defaults(
        func=cmd_corpus_reextract_equity_batch,
        corpus_cmd="reextract-equity-batch",
    )
    corpus_sample = corpus_sub.add_parser(
        "sample-listed",
        help="Sample one listing: cninfo annual PDF + equity extract (F10 / prospectus fallback)",
    )
    corpus_sample.add_argument("symbol", help="600519.SH or SSE:600519")
    corpus_sample.add_argument("--year", default="", help="Prefer annual report title containing year")
    corpus_sample.add_argument("--corpus-dir", default="", help="Override corpus.listed_dir")
    corpus_sample.add_argument("--pdf-dir", default="", help="PDF download directory (default corpus/pdf)")
    corpus_sample.add_argument("--no-download", action="store_true", help="Index only, skip PDF bytes")
    corpus_sample.add_argument("--no-warehouse", action="store_true", help="Write corpus JSONL only")
    corpus_sample.add_argument(
        "--no-prospectus-fallback",
        action="store_true",
        help="Do not fetch 招股说明书 when annual has no named suppliers",
    )
    corpus_sample.add_argument("--dry-run", action="store_true", help="Query without writing")
    corpus_sample.set_defaults(func=cmd_corpus_sample_listed, corpus_cmd="sample-listed")
    corpus_prospectus = corpus_sub.add_parser(
        "sample-prospectus",
        help="Download 招股说明书 and extract named suppliers into edges/equity",
    )
    corpus_prospectus.add_argument("symbol", help="600519.SH or SSE:600519")
    corpus_prospectus.add_argument("--corpus-dir", default="", help="Override corpus.listed_dir")
    corpus_prospectus.add_argument("--pdf-dir", default="", help="PDF download directory")
    corpus_prospectus.add_argument("--no-download", action="store_true", help="Index only")
    corpus_prospectus.add_argument("--no-warehouse", action="store_true", help="Corpus JSON only")
    corpus_prospectus.add_argument(
        "--full-equity",
        action="store_true",
        help="Also extract subsidiaries/invest (default: suppliers only)",
    )
    corpus_prospectus.add_argument("--dry-run", action="store_true", help="Query without writing")
    corpus_prospectus.set_defaults(func=cmd_corpus_sample_prospectus, corpus_cmd="sample-prospectus")
    corpus_batch = corpus_sub.add_parser(
        "sample-listed-batch",
        help="Batch sample: cninfo annual PDF + Eastmoney top-10 (resumable)",
    )
    corpus_batch.add_argument(
        "--instruments",
        default="",
        help="tradecraft instruments.parquet (symbol column)",
    )
    corpus_batch.add_argument(
        "--symbols-file",
        default="",
        help="Text file: one 600519.SH or SSE:600519 per line",
    )
    corpus_batch.add_argument("--year", default="", help="Prefer annual report title containing year")
    corpus_batch.add_argument("--corpus-dir", default="", help="Override corpus.listed_dir")
    corpus_batch.add_argument("--pdf-dir", default="", help="PDF download directory")
    corpus_batch.add_argument(
        "--progress",
        default="",
        help="JSONL progress path (default corpus/_sample_listed_batch.jsonl)",
    )
    corpus_batch.add_argument("--delay", type=float, default=1.5, help="Seconds between symbols")
    corpus_batch.add_argument("--limit", type=int, default=0, help="Max symbols this run (0=all)")
    corpus_batch.add_argument("--no-download", action="store_true", help="Index only, skip PDF bytes")
    corpus_batch.add_argument("--no-warehouse", action="store_true", help="Write corpus JSONL only")
    corpus_batch.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="Do not skip symbols that already have corpus+PDF",
    )
    corpus_batch.set_defaults(func=cmd_corpus_sample_listed_batch, corpus_cmd="sample-listed-batch")
    corpus_segments = corpus_sub.add_parser(
        "backfill-segments",
        help="Backfill listed/segments from East Money F10 主营构成",
    )
    corpus_segments.add_argument("--workers", type=int, default=12, help="Parallel fetch workers")
    corpus_segments.add_argument("--limit", type=int, default=0, help="Max symbols (0=all)")
    corpus_segments.add_argument("--progress", default="", help="Append summary JSONL path")
    corpus_segments.set_defaults(func=cmd_corpus_backfill_segments, corpus_cmd="backfill-segments")
    corpus_f10 = corpus_sub.add_parser(
        "backfill-f10",
        help="Backfill F10 tabs: segments/holders/capital/executives/dividends/control",
    )
    corpus_f10.add_argument("--workers", type=int, default=12, help="Parallel fetch workers")
    corpus_f10.add_argument("--limit", type=int, default=0, help="Max symbols (0=all)")
    corpus_f10.add_argument("--progress", default="", help="Append summary JSONL path")
    corpus_f10.add_argument(
        "--tables",
        default="",
        help="Comma list: segments,holders,capital,executives,dividends,control (default all)",
    )
    corpus_f10.set_defaults(func=cmd_corpus_backfill_f10, corpus_cmd="backfill-f10")
    corpus_facts = corpus_sub.add_parser(
        "sync-facts",
        help="Sync tradecraft panel financials → warehouse/listed/facts",
    )
    corpus_facts.add_argument(
        "--panel-dir",
        default="",
        help="Tradecraft data dir (default ../tradecraft/data)",
    )
    corpus_facts.add_argument("--dry-run", action="store_true", help="Count rows only")
    corpus_facts.set_defaults(func=cmd_corpus_sync_facts, corpus_cmd="sync-facts")
    corpus_facts_em = corpus_sub.add_parser(
        "backfill-facts-em",
        help="Backfill listed/facts from East Money datacenter (no QMT)",
    )
    corpus_facts_em.add_argument("--workers", type=int, default=12)
    corpus_facts_em.add_argument("--limit", type=int, default=0, help="Max symbols (0=all)")
    corpus_facts_em.add_argument("--page-size", type=int, default=12, help="Periods per statement")
    corpus_facts_em.add_argument("--progress", default="", help="Append summary JSONL path")
    corpus_facts_em.set_defaults(func=cmd_corpus_backfill_facts_em, corpus_cmd="backfill-facts-em")

    listed = sub.add_parser("listed", help="Listed-company dossier (East Money F10 shape)")
    listed_sub = listed.add_subparsers(dest="listed_cmd", required=True)
    listed_dossier = listed_sub.add_parser("dossier", help="Assemble F10-style dossier from warehouse")
    listed_dossier.add_argument("symbol", help="600519.SH or SSE:600519")
    listed_dossier.add_argument("--no-peers", action="store_true", help="Skip peer comparison tab")
    listed_dossier.set_defaults(func=cmd_listed_dossier, listed_cmd="dossier")

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
