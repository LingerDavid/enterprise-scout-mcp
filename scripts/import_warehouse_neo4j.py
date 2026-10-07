#!/usr/bin/env python3
"""Import warehouse/entities + edges/equity parquet into Neo4j."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from enterprise_scout_mcp.config import load_config
from enterprise_scout_mcp.warehouse.neo4j_loader import import_warehouse


def main() -> int:
    p = argparse.ArgumentParser(description="Import EnterpriseLake warehouse into Neo4j")
    p.add_argument("-c", "--config", default=None)
    p.add_argument("--warehouse-dir", type=Path, default=None)
    p.add_argument("--uri", default="bolt://127.0.0.1:7687")
    p.add_argument("--user", default="neo4j")
    p.add_argument("--password", default="enterprise-lake-dev")
    p.add_argument("--dry-run", action="store_true", help="Count rows only, no Neo4j write")
    args = p.parse_args()

    config = load_config(args.config)
    wh = args.warehouse_dir or Path(config.output.warehouse_dir)

    try:
        stats = import_warehouse(
            wh,
            uri=args.uri,
            user=args.user,
            password=args.password,
            dry_run=args.dry_run,
        )
    except ImportError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1

    print(json.dumps({"ok": True, "warehouse_dir": str(wh), **stats.to_dict()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
