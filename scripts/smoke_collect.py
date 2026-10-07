#!/usr/bin/env python3
"""Live smoke: one collect via orchestrator (requires sidecars configured)."""

from __future__ import annotations

import argparse
import json
import sys

from enterprise_scout_mcp.config import load_config
from enterprise_scout_mcp.diagnostics.sidecars import build_sidecar_report
from enterprise_scout_mcp.models import CollectTask, Platform
from enterprise_scout_mcp.scheduler import CollectorScheduler


def main() -> int:
    p = argparse.ArgumentParser(description="Smoke-test one enterprise collect")
    p.add_argument("-c", "--config", default=None)
    p.add_argument("keyword", nargs="?", default="小米")
    p.add_argument("-p", "--platform", default="aiqicha")
    p.add_argument("--skip-sidecar-check", action="store_true")
    p.add_argument("--sidecar-timeout", type=float, default=2.0)
    args = p.parse_args()

    config = load_config(args.config)
    if not args.skip_sidecar_check:
        sidecars = build_sidecar_report(config, timeout=args.sidecar_timeout)
        if not sidecars["ensan_go"].get("ok"):
            print(json.dumps({"ok": False, "stage": "sidecar", "sidecars": sidecars}, ensure_ascii=False))
            return 1

    scheduler = CollectorScheduler(config)
    try:
        result = scheduler.run(
            CollectTask(keyword=args.keyword, platform=Platform(args.platform), depth=1)
        )
        payload = {
            "ok": result.grade.value in ("ok", "partial"),
            "grade": result.grade.value,
            "channel": result.channel.value,
            "message": result.message,
            "data_keys": list((result.data or {}).keys()),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["ok"] else 1
    finally:
        scheduler.close()


if __name__ == "__main__":
    sys.exit(main())
