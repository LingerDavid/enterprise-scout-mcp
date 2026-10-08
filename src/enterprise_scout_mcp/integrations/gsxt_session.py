"""Persist GSXT personal-login cookies for httpx reuse."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_session(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def save_session(path: Path, cookies: dict[str, str], *, note: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "note": note,
        "cookies": cookies,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _cookies_from_list(items: list[Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        out[name] = str(item.get("value", ""))
    return out


def cookies_from_export(raw: dict[str, Any] | list[Any]) -> dict[str, str]:
    """Accept session file, flat dict, or browser extension cookie list."""
    if isinstance(raw, list):
        return _cookies_from_list(raw)
    if "cookies" in raw and isinstance(raw["cookies"], dict):
        return {str(k): str(v) for k, v in raw["cookies"].items()}
    if all(isinstance(v, str) for v in raw.values()) and "saved_at" not in raw:
        return {str(k): str(v) for k, v in raw.items()}
    if isinstance(raw.get("cookies"), list):
        return _cookies_from_list(raw["cookies"])
    raise ValueError("unrecognized cookie export format")


def import_session_file(source: Path, dest: Path) -> dict[str, str]:
    raw = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(raw, (dict, list)):
        raise ValueError("cookie file must be a JSON object or array")
    cookies = cookies_from_export(raw)
    if not cookies:
        raise ValueError("no cookies found in export")
    save_session(dest, cookies, note=f"imported from {source.name}")
    preview = {k: (v[:8] + "…" if len(v) > 8 else v) for k, v in list(cookies.items())[:5]}
    return preview
