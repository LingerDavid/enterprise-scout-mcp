#!/usr/bin/env python3
"""Probe ENScan_GO and proxy_pool sidecars (exit 1 if ENScan unreachable)."""

from __future__ import annotations

import argparse
import json
import sys

from enterprise_scout_mcp.config import load_config
from enterprise_scout_mcp.diagnostics.sidecars import build_sidecar_report


def main() -> int:
    p = argparse.ArgumentParser(description="Smoke-test sidecar integrations")
    p.add_argument("-c", "--config", default=None)
    p.add_argument("--timeout", type=float, default=2.0)
    args = p.parse_args()

    report = build_sidecar_report(load_config(args.config), timeout=args.timeout)
    print(json.dumps(report, ensure_ascii=False, indent=2))

    ensan_ok = report["ensan_go"].get("ok", False)
    proxy_cfg = report["proxy_pool"]
    proxy_ok = proxy_cfg.get("skipped") or proxy_cfg.get("reachable", False)
    return 0 if ensan_ok and proxy_ok else 1


if __name__ == "__main__":
    sys.exit(main())
