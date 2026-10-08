"""GSXT L1 registry search inside real Chromium — bypasses CT/瑞数 API gate."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from enterprise_scout_mcp.channels.official.parse import (
    classify_browser_block,
    parse_search_html,
    parse_search_payload,
)
from enterprise_scout_mcp.config import GsxtConfig
from enterprise_scout_mcp.integrations.gsxt_transport import (
    browser_uses_cdp,
    build_browser_start_kwargs,
    resolve_browser_backend,
)


@dataclass
class BrowserSearchResult:
    ok: bool
    row: dict[str, str] | None = None
    cookies: dict[str, str] = field(default_factory=dict)
    message: str = ""
    html_snippet: str = ""


_SEARCH_JS = """
(() => {
  const kw = %s;
  const selectors = [
    '#keyword', 'input[name="keyword"]', 'input[name="searchword"]',
    'input[placeholder*="企业"]', 'input[placeholder*="关键字"]', 'input[type="search"]',
  ];
  let input = null;
  for (const sel of selectors) {
    input = document.querySelector(sel);
    if (input) break;
  }
  if (!input) return {ok: false, error: 'search input not found'};
  input.focus();
  input.value = kw;
  input.dispatchEvent(new Event('input', {bubbles: true}));
  input.dispatchEvent(new Event('change', {bubbles: true}));
  const btnSelectors = [
    '.search_button', '.searchBtn', 'button.search', '#btn_query',
    'a.search_button', 'span.search_button', '.btn-search', 'button[type="submit"]',
  ];
  for (const sel of btnSelectors) {
    const btn = document.querySelector(sel);
    if (btn) { btn.click(); return {ok: true, method: 'click', selector: sel}; }
  }
  input.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', bubbles: true}));
  return {ok: true, method: 'enter'};
})()
"""


async def _set_cookies(browser: Any, cookies: dict[str, str]) -> None:
    for name, value in cookies.items():
        if not name or not value:
            continue
        for domain in (".gsxt.gov.cn", "www.gsxt.gov.cn", "shiming.gsxt.gov.cn"):
            try:
                await browser.cookies.set(name, value, domain=domain)
            except Exception:  # noqa: BLE001 — best-effort per domain
                pass


async def _collect_cookies(browser: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    for c in await browser.cookies.get_all():
        domain = getattr(c, "domain", "") or ""
        if "gsxt.gov.cn" not in domain:
            continue
        name = getattr(c, "name", "") or ""
        if name:
            out[name] = getattr(c, "value", "") or ""
    return out


async def _page_html(page: Any) -> str:
    content = await page.get_content()
    return content if isinstance(content, str) else str(content)


async def _eval_json(page: Any, expression: str) -> Any:
    """nodriver evaluate returns expression result; coerce RemoteObject when needed."""
    raw = await page.evaluate(expression, await_promise=True, return_by_value=True)
    if isinstance(raw, tuple):
        remote, _exc = raw
        value = getattr(remote, "value", None)
        if value is not None:
            return value
        return None
    return raw


async def _inbrowser_api_search(page: Any, keyword: str, config: GsxtConfig) -> dict[str, str] | None:
    """Call GSXT search API from page JS context (inherits CT cookies)."""
    # nodriver.evaluate only accepts an expression string — embed args via json.dumps
    expression = """
    (async () => {
      const kw = %s;
      const url = %s;
      const field = %s;
      const body = { pageSize: 10, pageNum: 1 };
      body[field] = kw;
      try {
        const r = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
          body: JSON.stringify(body),
          credentials: 'include',
        });
        const text = await r.text();
        return JSON.stringify({ status: r.status, text: text.slice(0, 50000) });
      } catch (e) {
        return JSON.stringify({ status: 0, text: String(e) });
      }
    })()
    """ % (
        json.dumps(keyword, ensure_ascii=False),
        json.dumps(config.search_url, ensure_ascii=False),
        json.dumps(config.search_keyword_field, ensure_ascii=False),
    )
    try:
        raw = await _eval_json(page, expression)
    except Exception:  # noqa: BLE001
        return None
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
    elif isinstance(raw, dict):
        payload = raw
    else:
        return None
    text = str(payload.get("text") or "")
    if classify_browser_block(text) in ("ct_challenge", "blocked"):
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = text
    return parse_search_payload(parsed)


async def _wait_page_ready(page: Any, timeout: float) -> str | None:
    """Wait until CT/NWAF challenge clears. Returns remaining block hint or None if ready."""
    deadline = time.monotonic() + timeout
    last_hint: str | None = "ct_challenge"
    while time.monotonic() < deadline:
        html = await _page_html(page)
        last_hint = classify_browser_block(html)
        if last_hint is None:
            # Also require a search box or GSXT chrome to be present
            if (
                "keyword" in html.lower()
                or "searchword" in html.lower()
                or "国家企业信用信息公示系统" in html
                or "gsxt" in html.lower()
            ):
                return None
            # Page may still be loading
            await asyncio.sleep(1.0)
            continue
        if last_hint in ("ct_challenge", "blocked"):
            await asyncio.sleep(1.5)
            continue
        # auth_expired / captcha — stop waiting
        return last_hint
    return last_hint


async def search_registry_async(
    keyword: str,
    *,
    config: GsxtConfig,
    cookies: dict[str, str],
    user_data_dir: Path,
    index_url: str,
    proxy_url: str | None = None,
) -> BrowserSearchResult:
    import nodriver as uc

    user_data_dir.mkdir(parents=True, exist_ok=True)
    attached = browser_uses_cdp(config)
    start_kwargs = build_browser_start_kwargs(
        config,
        user_data_dir=str(user_data_dir.resolve()),
        proxy_url=proxy_url,
    )
    browser = await uc.start(**start_kwargs)
    try:
        if cookies:
            await _set_cookies(browser, cookies)
        page = await browser.get(index_url)
        await asyncio.sleep(2.0)
        ready_wait = min(max(config.browser_search_timeout * 0.5, 15.0), 40.0)
        block = await _wait_page_ready(page, ready_wait)
        if block == "ct_challenge":
            return BrowserSearchResult(
                ok=False,
                message="CT/瑞数 challenge did not clear — try headed browser or re-import session",
                cookies=await _collect_cookies(browser),
            )
        if block == "blocked":
            hint = (
                "GSXT NWAF/WAF blocked browser — set browser_headless: false, "
                "keep .state/gsxt_nodriver_data profile, retry after manual visit"
            )
            if not attached:
                hint += "; or attach real Chrome: browser_cdp_port=9222 + escout sessions cdp-hint"
            return BrowserSearchResult(
                ok=False,
                message=hint,
                cookies=await _collect_cookies(browser),
                html_snippet=(await _page_html(page))[:1500],
            )
        if block in ("captcha", "auth_expired"):
            return BrowserSearchResult(
                ok=False,
                message=f"GSXT browser {block}",
                cookies=await _collect_cookies(browser),
                html_snippet=(await _page_html(page))[:1500],
            )

        api_row = await _inbrowser_api_search(page, keyword, config)
        if api_row and (api_row.get("name") or api_row.get("credit_code")):
            return BrowserSearchResult(
                ok=True,
                row=api_row,
                cookies=await _collect_cookies(browser),
                message="ok (in-browser api)",
            )

        script = _SEARCH_JS % json.dumps(keyword, ensure_ascii=False)
        try:
            submit = await _eval_json(page, script)
        except Exception as exc:  # noqa: BLE001
            return BrowserSearchResult(
                ok=False,
                message=f"browser search submit failed: {exc}",
                cookies=await _collect_cookies(browser),
            )
        if isinstance(submit, dict) and not submit.get("ok"):
            return BrowserSearchResult(
                ok=False,
                message=str(submit.get("error") or "search input not found on GSXT page"),
                cookies=await _collect_cookies(browser),
            )

        deadline = time.monotonic() + config.browser_search_timeout
        last_html = ""
        while time.monotonic() < deadline:
            await asyncio.sleep(1.0)
            last_html = await _page_html(page)
            hint = classify_browser_block(last_html)
            if hint == "blocked":
                return BrowserSearchResult(
                    ok=False,
                    message=(
                        "GSXT NWAF/WAF blocked browser — set browser_headless: false, "
                        "run sessions warmup gsxt once, retry"
                    ),
                    cookies=await _collect_cookies(browser),
                    html_snippet=last_html[:1500],
                )
            if hint in ("captcha", "auth_expired"):
                return BrowserSearchResult(
                    ok=False,
                    message=f"GSXT browser {hint}",
                    cookies=await _collect_cookies(browser),
                    html_snippet=last_html[:1500],
                )
            if "未查询到" in last_html or "没有找到" in last_html or "查询无结果" in last_html:
                return BrowserSearchResult(
                    ok=False,
                    message="GSXT browser search — no results",
                    cookies=await _collect_cookies(browser),
                    html_snippet=last_html[:1500],
                )
            row = parse_search_html(last_html, keyword=keyword)
            if row and (row.get("name") or row.get("credit_code")):
                return BrowserSearchResult(
                    ok=True,
                    row=row,
                    cookies=await _collect_cookies(browser),
                    message="ok (dom)",
                )
            api_row = await _inbrowser_api_search(page, keyword, config)
            if api_row and (api_row.get("name") or api_row.get("credit_code")):
                return BrowserSearchResult(
                    ok=True,
                    row=api_row,
                    cookies=await _collect_cookies(browser),
                    message="ok (in-browser api)",
                )

        row = parse_search_html(last_html, keyword=keyword)
        if row:
            return BrowserSearchResult(
                ok=True,
                row=row,
                cookies=await _collect_cookies(browser),
                message="ok (dom)",
            )
        return BrowserSearchResult(
            ok=False,
            message="GSXT browser search timed out without registry row",
            cookies=await _collect_cookies(browser),
            html_snippet=last_html[:1500],
        )
    finally:
        if not attached:
            browser.stop()


def search_registry_browser(
    keyword: str,
    *,
    config: GsxtConfig,
    cookies: dict[str, str],
    user_data_dir: Path,
    index_url: str,
    proxy_url: str | None = None,
) -> BrowserSearchResult:
    backend = resolve_browser_backend(config)
    if backend == "playwright_cdp":
        from enterprise_scout_mcp.integrations.gsxt_playwright_cdp import search_registry_playwright_cdp

        return search_registry_playwright_cdp(
            keyword,
            config=config,
            cookies=cookies,
            user_data_dir=user_data_dir,
            index_url=index_url,
        )
    try:
        return asyncio.run(
            search_registry_async(
                keyword,
                config=config,
                cookies=cookies,
                user_data_dir=user_data_dir,
                index_url=index_url,
                proxy_url=proxy_url,
            )
        )
    except ImportError:
        return BrowserSearchResult(
            ok=False,
            message="nodriver not installed — pip install -e '.[browser]'",
        )
    except Exception as exc:  # noqa: BLE001 — surface to channel
        return BrowserSearchResult(ok=False, message=str(exc))
