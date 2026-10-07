"""Subprocess bridge to scripts/aiqicha_fetch_one.py on DB miss."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def fetch_one(
    keyword: str,
    *,
    db_path: Path,
    cookie_file: Path | None,
    script_path: Path,
    timeout_seconds: float = 90.0,
) -> dict:
    if not script_path.is_file():
        return {"status": "error", "message": f"fetch script missing: {script_path}"}

    cmd = [
        sys.executable,
        str(script_path),
        keyword,
        "--db",
        str(db_path),
        "--timeout",
        str(min(timeout_seconds, 60.0)),
    ]
    if cookie_file and cookie_file.is_file():
        cmd.extend(["--cookie-file", str(cookie_file)])

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "message": f"fetch exceeded {timeout_seconds}s"}

    stdout = (proc.stdout or "").strip()
    if not stdout:
        return {
            "status": "error",
            "message": proc.stderr.strip() or f"exit {proc.returncode}",
        }
    try:
        payload = json.loads(stdout.splitlines()[-1])
    except json.JSONDecodeError:
        return {"status": "error", "message": stdout[:500]}

    payload["exit_code"] = proc.returncode
    return payload
