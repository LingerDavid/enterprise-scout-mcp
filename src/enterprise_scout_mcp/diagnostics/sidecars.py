"""Live probes for ENScan_GO, proxy_pool, and optional collect smoke."""

from __future__ import annotations

from typing import Any

import httpx

from enterprise_scout_mcp.config import AppConfig
from enterprise_scout_mcp.transport.proxy_pool import ProxyPoolClient


def _probe_get(url: str, *, timeout: float = 2.0) -> dict[str, Any]:
    try:
        r = httpx.get(url, timeout=timeout, follow_redirects=True)
        return {"reachable": True, "status_code": r.status_code, "ok": r.status_code == 200}
    except Exception as exc:  # noqa: BLE001 - probe must not raise
        return {"reachable": False, "ok": False, "error": str(exc)}


def probe_enscan(base_url: str, *, timeout: float = 2.0) -> dict[str, Any]:
    return _probe_get(f"{base_url.rstrip('/')}/", timeout=timeout)


def probe_proxy_pool(base_url: str, *, timeout: float = 2.0) -> dict[str, Any]:
    report = _probe_get(f"{base_url.rstrip('/')}/", timeout=timeout)
    if not report.get("reachable"):
        return report
    client = ProxyPoolClient(base_url, timeout=timeout)
    try:
        endpoint = client.get(https=False)
        report["has_proxy"] = endpoint is not None
        if endpoint:
            report["sample_proxy"] = endpoint.url
    except httpx.HTTPError as exc:
        report["has_proxy"] = False
        report["proxy_error"] = str(exc)
    finally:
        client.close()
    return report


def build_sidecar_report(config: AppConfig, *, timeout: float = 2.0) -> dict[str, Any]:
    ensan = config.integrations.ensan_go
    proxy = config.integrations.proxy_pool
    report: dict[str, Any] = {
        "ensan_go": {
            "enabled": ensan.enabled,
            "base_url": ensan.base_url,
            **probe_enscan(ensan.base_url, timeout=timeout),
        },
        "proxy_pool": {
            "enabled": proxy.enabled,
            "base_url": proxy.base_url,
        },
    }
    if proxy.enabled:
        report["proxy_pool"].update(probe_proxy_pool(proxy.base_url, timeout=timeout))
    else:
        report["proxy_pool"]["skipped"] = True
    return report
