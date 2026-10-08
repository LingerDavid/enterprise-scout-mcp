"""GSXT egress helpers — proxy resolution and nodriver launch options."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse

from enterprise_scout_mcp.config import GsxtConfig
from enterprise_scout_mcp.transport.egress import EgressContext


def resolve_gsxt_proxy(
    config: GsxtConfig,
    egress: EgressContext | None = None,
) -> str | None:
    """Prefer scheduler egress, then config.proxy_url, then HTTP(S)_PROXY env."""
    if egress and egress.proxy_url:
        return egress.proxy_url.strip() or None
    explicit = (config.proxy_url or "").strip()
    if explicit:
        return explicit
    if config.proxy_from_env:
        for key in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
            val = os.environ.get(key, "").strip()
            if val:
                return val
    return None


def browser_uses_cdp(config: GsxtConfig) -> bool:
    return int(config.browser_cdp_port or 0) > 0


def resolve_browser_backend(config: GsxtConfig) -> str:
    """auto: playwright_cdp when browser_cdp_port set, else nodriver."""
    mode = (config.browser_backend or "auto").lower()
    if mode == "playwright_cdp":
        return "playwright_cdp"
    if mode == "nodriver":
        return "nodriver"
    if browser_uses_cdp(config):
        return "playwright_cdp"
    return "nodriver"


def build_browser_start_kwargs(
    config: GsxtConfig,
    *,
    user_data_dir: str,
    proxy_url: str | None = None,
) -> dict[str, Any]:
    """Build nodriver uc.start() kwargs for GSXT browser search / warmup."""
    browser_args = [
        "--disable-blink-features=AutomationControlled",
        f"--user-agent={config.user_agent}",
    ]
    if proxy_url:
        browser_args.append(f"--proxy-server={proxy_url}")

    kwargs: dict[str, Any] = {
        "sandbox": False,
        "headless": config.browser_headless,
        "browser_args": browser_args,
    }

    if browser_uses_cdp(config):
        kwargs["host"] = (config.browser_cdp_host or "127.0.0.1").strip() or "127.0.0.1"
        kwargs["port"] = int(config.browser_cdp_port)
    else:
        kwargs["user_data_dir"] = user_data_dir

    return kwargs


def cdp_launch_hint(config: GsxtConfig, *, user_data_dir: str) -> str:
    host = (config.browser_cdp_host or "127.0.0.1").strip() or "127.0.0.1"
    port = int(config.browser_cdp_port)
    return (
        f'chrome.exe --remote-debugging-port={port} '
        f'--user-data-dir="{user_data_dir}" '
        f"(connect nodriver to {host}:{port})"
    )


def proxy_preview(proxy_url: str | None) -> str | None:
    if not proxy_url:
        return None
    try:
        parsed = urlparse(proxy_url)
        if parsed.hostname:
            return f"{parsed.scheme}://{parsed.hostname}:{parsed.port or ''}".rstrip(":")
    except Exception:  # noqa: BLE001
        pass
    return proxy_url[:40] + ("…" if len(proxy_url) > 40 else "")
