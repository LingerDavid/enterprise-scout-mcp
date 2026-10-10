"""Run Fine UI HTTP server."""

from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Enterprise Scout Fine UI server")
    parser.add_argument("-c", "--config", default=None, help="Path to config.yaml")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8790)
    args = parser.parse_args(argv)

    try:
        import uvicorn
    except ImportError:
        print('Install UI deps: pip install -e ".[ui]"')
        return 1

    from enterprise_scout_mcp.http.app import create_app

    app = create_app(args.config)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
