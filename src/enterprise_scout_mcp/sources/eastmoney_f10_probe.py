"""Shared helpers to introspect East Money F10 PageAjax / datacenter payloads."""

from __future__ import annotations

from typing import Any

import httpx

from enterprise_scout_mcp.sources.eastmoney_common import F10_HEADERS, F10_BASE

_DATACENTER_URL = "https://datacenter.eastmoney.com/securities/api/data/v1/get"


def summarize_list_block(items: Any, *, sample_rows: int = 1) -> dict[str, Any]:
    """Describe one PageAjax top-level list block."""
    if not isinstance(items, list):
        return {"kind": type(items).__name__ if items is not None else "null", "count": 0}
    out: dict[str, Any] = {"kind": "list", "count": len(items)}
    samples: list[dict[str, Any]] = []
    for raw in items[:sample_rows]:
        if isinstance(raw, dict):
            samples.append({"fields": sorted(raw.keys()), "sample": raw})
    if samples:
        out["samples"] = samples
    return out


def summarize_page_ajax_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return top-level keys with list/scalar structure summaries."""
    blocks: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, list):
            blocks[key] = summarize_list_block(value)
        elif isinstance(value, dict):
            blocks[key] = {"kind": "object", "fields": sorted(value.keys())}
        else:
            blocks[key] = {"kind": "scalar", "value_type": type(value).__name__}
    return {"top_level_keys": sorted(payload.keys()), "blocks": blocks}


def fetch_page_ajax(
    module: str,
    em_code: str,
    *,
    client: httpx.Client,
) -> dict[str, Any]:
    """GET ``PC_HSF10/{module}/PageAjax``; soft-fail → ``{}``."""
    try:
        resp = client.get(f"{F10_BASE}/{module}/PageAjax", params={"code": em_code})
        resp.raise_for_status()
        payload = resp.json()
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def probe_page_ajax_module(
    module: str,
    em_code: str,
    *,
    client: httpx.Client,
    mapped_keys: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Probe one F10 PageAjax module and mark mapped vs unmapped list keys."""
    payload = fetch_page_ajax(module, em_code, client=client)
    report: dict[str, Any] = {
        "module": module,
        "ok": bool(payload),
        "mapped_keys": mapped_keys or {},
    }
    if not payload:
        report["skipped"] = ["empty_payload"]
        return report
    summary = summarize_page_ajax_payload(payload)
    report.update(summary)
    unmapped = [
        k
        for k in summary.get("top_level_keys", [])
        if k not in (mapped_keys or {})
    ]
    report["unmapped_keys"] = unmapped
    return report


def probe_datacenter_report(
    report_name: str,
    symbol: str,
    *,
    client: httpx.Client,
    columns: str = "ALL",
    page_size: int = 3,
) -> dict[str, Any]:
    """Probe one datacenter report; return columns sample and row count."""
    sym = symbol.strip().upper()
    out: dict[str, Any] = {"report_name": report_name, "symbol": sym, "ok": False}
    try:
        resp = client.get(
            _DATACENTER_URL,
            params={
                "reportName": report_name,
                "columns": columns,
                "filter": f'(SECUCODE="{sym}")',
                "pageNumber": "1",
                "pageSize": str(page_size),
                "sortTypes": "-1",
                "sortColumns": "REPORT_DATE",
                "source": "HSF10",
                "client": "PC",
            },
        )
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:
        out["skipped"] = [str(exc.__class__.__name__)]
        return out
    if not isinstance(payload, dict) or not payload.get("success"):
        out["skipped"] = [str(payload.get("message") or "request_failed")]
        return out
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    data = result.get("data") if isinstance(result.get("data"), list) else []
    out["ok"] = True
    out["count"] = len(data)
    if data and isinstance(data[0], dict):
        out["fields"] = sorted(data[0].keys())
        out["sample"] = data[0]
    return out


def new_f10_client() -> httpx.Client:
    return httpx.Client(timeout=25.0, headers=F10_HEADERS, follow_redirects=True)
