"""In-page GSXT search — Ruishu-safe; runs inside real browser context only."""

from __future__ import annotations

import json
from typing import Any

from enterprise_scout_mcp.channels.official.parse import classify_browser_block, parse_search_payload
from enterprise_scout_mcp.config import GsxtConfig

# Method A: site-native ajax first, then fetch (inherits CT cookies from page)
INBROWSER_SEARCH_JS = """
async ({ kw, url, field }) => {
  const body = { pageSize: 10, pageNum: 1 };
  body[field] = kw;
  const tryNative = async () => {
    const candidates = [];
    if (typeof pajax !== 'undefined') {
      if (typeof pajax.post === 'function') candidates.push(() => pajax.post(url, body));
      if (typeof pajax.hasTokenGet === 'function') {
        candidates.push(() => pajax.hasTokenGet(url, body));
      }
      if (typeof pajax.hasTokenPost === 'function') {
        candidates.push(() => pajax.hasTokenPost(url, body));
      }
    }
    if (typeof $ !== 'undefined' && $.ajax) {
      candidates.push(() => new Promise((resolve, reject) => {
        $.ajax({
          url, method: 'POST', data: JSON.stringify(body),
          contentType: 'application/json', dataType: 'json',
          xhrFields: { withCredentials: true },
          success: resolve, error: (_x, _s, err) => reject(err || new Error('ajax failed')),
        });
      }));
    }
    for (const fn of candidates) {
      try {
        const out = await fn();
        if (out != null) {
          return { status: 200, text: JSON.stringify(out).slice(0, 50000), via: 'native' };
        }
      } catch (e) { /* next */ }
    }
    return null;
  };
  const native = await tryNative();
  if (native) return native;
  try {
    const r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: JSON.stringify(body),
      credentials: 'include',
    });
    const text = await r.text();
    return { status: r.status, text: text.slice(0, 50000), via: 'fetch' };
  } catch (e) {
    return { status: 0, text: String(e), via: 'fetch' };
  }
}
"""

RUISHU_PROBE_JS = """
async ({ url }) => {
  try {
    const r = await fetch(url, { method: 'GET', credentials: 'include' });
    const text = (await r.text()).slice(0, 200);
    return { status: r.status, head: text };
  } catch (e) {
    return { status: 0, head: String(e) };
  }
}
"""


def is_ruishu_block_status(status: int, text: str) -> bool:
    if status in (405, 412, 521):
        return True
    hint = classify_browser_block(text)
    return hint in ("ct_challenge", "jsl_challenge", "blocked")


def parse_inbrowser_payload(payload: Any) -> dict[str, str] | None:
    if not isinstance(payload, dict):
        return None
    text = str(payload.get("text") or "")
    if is_ruishu_block_status(int(payload.get("status") or 0), text):
        return None
    if classify_browser_block(text) in ("ct_challenge", "blocked"):
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = text
    return parse_search_payload(parsed)


async def inbrowser_api_search(page: Any, keyword: str, config: GsxtConfig) -> dict[str, str] | None:
    try:
        payload = await page.evaluate(
            INBROWSER_SEARCH_JS,
            {"kw": keyword, "url": config.search_url, "field": config.search_keyword_field},
        )
    except Exception:  # noqa: BLE001
        return None
    return parse_inbrowser_payload(payload)


async def wait_ruishu_ready(page: Any, config: GsxtConfig, timeout: float) -> bool:
    """Wait until in-page probe is not JSL/CT — Ruishu env must run in real browser first."""
    import asyncio
    import time

    probe_url = config.base_url.rstrip("/") + "/index.html"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            payload = await page.evaluate(RUISHU_PROBE_JS, {"url": probe_url})
        except Exception:  # noqa: BLE001
            await asyncio.sleep(1.5)
            continue
        if isinstance(payload, dict):
            status = int(payload.get("status") or 0)
            head = str(payload.get("head") or "")
            if not is_ruishu_block_status(status, head):
                return True
        await asyncio.sleep(1.5)
    return False


def search_url_matcher(config: GsxtConfig):
    needle = config.search_url.rsplit("/", 1)[-1]

    def _match(response: Any) -> bool:
        url = getattr(response, "url", "") or ""
        return needle in url and getattr(response, "request", None) and (
            getattr(response.request, "method", "") or ""
        ).upper() == "POST"

    return _match
