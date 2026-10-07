"""Sync aiqicha cookies between local secrets and ENScan_GO config.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"config not found: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def save_yaml(path: Path, data: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def read_cookie_value(source: Path) -> str:
    text = source.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"empty cookie file: {source}")
    if "\n" in text:
        # Netscape or multi-line: join semicolon-separated pairs on one line
        lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
        return "; ".join(lines)
    return text


def sync_aiqicha_to_enscan(
    *,
    cookie_source: Path,
    enscan_config: Path,
    platform: str = "aiqicha",
) -> str:
    """Write cookie into ENScan_GO config; returns masked preview."""
    cookie = read_cookie_value(cookie_source)
    data = load_yaml(enscan_config)
    cookies = data.setdefault("cookies", {})
    cookies[platform] = cookie
    save_yaml(enscan_config, data)
    preview = cookie[:24] + "..." if len(cookie) > 24 else cookie
    return preview
