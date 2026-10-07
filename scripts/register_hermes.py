#!/usr/bin/env python3
"""Merge enterprise-scout-mcp into ~/.hermes/config.yaml mcp_servers."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


def hermes_config_path() -> Path:
    home = Path.home() / ".hermes" / "config.yaml"
    return home


def build_entry(project_root: Path, *, use_venv: bool) -> dict:
    if use_venv:
        exe = project_root / ".venv" / "Scripts" / "enterprise-scout-mcp.exe"
        if not exe.is_file():
            exe = project_root / ".venv" / "bin" / "enterprise-scout-mcp"
        command = str(exe) if exe.is_file() else "enterprise-scout-mcp"
    else:
        command = "enterprise-scout-mcp"
    return {
        "command": command,
        "args": [],
        "cwd": str(project_root.resolve()),
    }


def register(project_root: Path, *, dry_run: bool, use_venv: bool) -> Path:
    cfg_path = hermes_config_path()
    data: dict = {}
    if cfg_path.is_file():
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}

    servers = data.setdefault("mcp_servers", {})
    servers["enterprise-scout-mcp"] = build_entry(project_root, use_venv=use_venv)

    if dry_run:
        print(yaml.safe_dump({"mcp_servers": {"enterprise-scout-mcp": servers["enterprise-scout-mcp"]}}))
        return cfg_path

    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return cfg_path


def main() -> int:
    p = argparse.ArgumentParser(description="Register enterprise-scout-mcp in Hermes config")
    p.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-venv", action="store_true", help="Use PATH enterprise-scout-mcp")
    args = p.parse_args()
    path = register(args.project_root, dry_run=args.dry_run, use_venv=not args.no_venv)
    if not args.dry_run:
        print(f"updated {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
