"""Subprocess bridge: httpx/curl_cffi fetch, nodriver fallback on captcha."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from enterprise_scout_mcp.transport.egress import EgressContext


def run_script(
    script_path: Path,
    keyword: str,
    *,
    db_path: Path,
    cookie_file: Path | None,
    timeout_seconds: float,
    extra_args: list[str] | None = None,
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
        str(min(timeout_seconds, 120.0)),
    ]
    if cookie_file and cookie_file.is_file():
        cmd.extend(["--cookie-file", str(cookie_file)])
    if extra_args:
        cmd.extend(extra_args)

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


def _egress_args(egress: EgressContext | None) -> list[str]:
    if egress is None:
        return []
    args: list[str] = []
    if egress.proxy_url:
        args.extend(["--proxy", egress.proxy_url])
    if egress.impersonate:
        args.extend(["--impersonate", egress.impersonate])
    if egress.user_agent:
        args.extend(["--user-agent", egress.user_agent])
    if egress.accept_language:
        args.extend(["--accept-language", egress.accept_language])
    return args


def fetch_one(
    keyword: str,
    *,
    db_path: Path,
    cookie_file: Path | None,
    script_path: Path,
    timeout_seconds: float = 90.0,
    egress: EgressContext | None = None,
) -> dict:
    return run_script(
        script_path,
        keyword,
        db_path=db_path,
        cookie_file=cookie_file,
        timeout_seconds=timeout_seconds,
        extra_args=_egress_args(egress),
    )


def fetch_with_fallback(
    keyword: str,
    *,
    db_path: Path,
    cookie_file: Path | None,
    httpx_script: Path,
    nodriver_script: Path | None,
    nodriver_enabled: bool,
    nodriver_user_data_dir: Path | None,
    timeout_seconds: float = 90.0,
    egress: EgressContext | None = None,
) -> dict:
    payload = fetch_one(
        keyword,
        db_path=db_path,
        cookie_file=cookie_file,
        script_path=httpx_script,
        timeout_seconds=timeout_seconds,
        egress=egress,
    )
    if payload.get("status") != "captcha":
        return payload
    if not nodriver_enabled or nodriver_script is None or not nodriver_script.is_file():
        return payload

    extra: list[str] = []
    if nodriver_user_data_dir is not None:
        extra.extend(["--user-data-dir", str(nodriver_user_data_dir)])

    return run_script(
        nodriver_script,
        keyword,
        db_path=db_path,
        cookie_file=cookie_file,
        timeout_seconds=max(timeout_seconds, 120.0),
        extra_args=extra,
    )
