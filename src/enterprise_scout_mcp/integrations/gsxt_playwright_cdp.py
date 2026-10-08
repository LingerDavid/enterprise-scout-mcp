"""GSXT L1 search via Playwright connect_over_cdp — real Chrome, Ruishu-safe."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from enterprise_scout_mcp.channels.official.parse import (
    classify_browser_block,
    parse_search_html,
    parse_search_payload,
)
from enterprise_scout_mcp.config import GsxtConfig
from enterprise_scout_mcp.integrations.gsxt_browser import BrowserSearchResult
from enterprise_scout_mcp.integrations.gsxt_transport import browser_uses_cdp, cdp_launch_hint


def _cdp_endpoint(config: GsxtConfig) -> str:
    host = (config.browser_cdp_host or "127.0.0.1").strip() or "127.0.0.1"
    port = int(config.browser_cdp_port)
    return f"http://{host}:{port}"


def _playwright_cookie_list(cookies: dict[str, str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for name, value in cookies.items():
        if not name or not value:
            continue
        for domain in (".gsxt.gov.cn", "www.gsxt.gov.cn", "shiming.gsxt.gov.cn"):
            rows.append({"name": name, "value": value, "domain": domain, "path": "/"})
    return rows


async def _pick_page(browser: Any, index_url: str) -> Any:
    for context in browser.contexts:
        for page in context.pages:
            url = page.url or ""
            if "gsxt.gov.cn" in url:
                return page
    context = browser.contexts[0] if browser.contexts else await browser.new_context()
    page = context.pages[0] if context.pages else await context.new_page()
    await page.goto(index_url, wait_until="domcontentloaded", timeout=60_000)
    return page


async def _context_cookies(page: Any) -> dict[str, str]:
    context = page.context
    out: dict[str, str] = {}
    for c in await context.cookies():
        domain = str(c.get("domain") or "")
        if "gsxt.gov.cn" not in domain:
            continue
        name = str(c.get("name") or "")
        if name:
            out[name] = str(c.get("value") or "")
    return out


async def _wait_page_ready(page: Any, timeout: float) -> str | None:
    deadline = time.monotonic() + timeout
    last_hint: str | None = "ct_challenge"
    while time.monotonic() < deadline:
        html = await page.content()
        last_hint = classify_browser_block(html)
        if last_hint is None:
            if (
                "keyword" in html.lower()
                or "searchword" in html.lower()
                or "国家企业信用信息公示系统" in html
                or "gsxt" in html.lower()
            ):
                return None
            await asyncio.sleep(1.0)
            continue
        if last_hint in ("ct_challenge", "blocked"):
            await asyncio.sleep(1.5)
            continue
        return last_hint
    return last_hint


_INBROWSER_SEARCH_FN = """
async ({ kw, url, field }) => {
  const body = { pageSize: 10, pageNum: 1 };
  body[field] = kw;
  // Method A: call site-native helpers when present (Ruishu params computed in-page)
  const nativeFns = [
    () => (typeof pajax !== 'undefined' && pajax.post ? pajax.post(url, body) : null),
    () => (typeof $ !== 'undefined' && $.ajax ? $.ajax({ url, method: 'POST', data: JSON.stringify(body), contentType: 'application/json', xhrFields: { withCredentials: true } }) : null),
  ];
  for (const fn of nativeFns) {
    try {
      const native = fn();
      if (native && typeof native.then === 'function') {
        const text = await native;
        if (text && typeof text === 'object') {
          return { status: 200, text: JSON.stringify(text).slice(0, 50000), via: 'native' };
        }
        if (typeof text === 'string' && text.length > 2) {
          return { status: 200, text: text.slice(0, 50000), via: 'native' };
        }
      }
    } catch (e) { /* fall through to fetch */ }
  }
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


async def _inbrowser_api_search(page: Any, keyword: str, config: GsxtConfig) -> dict[str, str] | None:
    try:
        payload = await page.evaluate(
            _INBROWSER_SEARCH_FN,
            {"kw": keyword, "url": config.search_url, "field": config.search_keyword_field},
        )
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(payload, dict):
        return None
    text = str(payload.get("text") or "")
    if classify_browser_block(text) in ("ct_challenge", "blocked"):
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = text
    return parse_search_payload(parsed)


async def search_registry_playwright_async(
    keyword: str,
    *,
    config: GsxtConfig,
    cookies: dict[str, str],
    user_data_dir: Path,
    index_url: str,
) -> BrowserSearchResult:
    if not browser_uses_cdp(config):
        return BrowserSearchResult(
            ok=False,
            message=(
                "playwright_cdp requires browser_cdp_port — start Chrome with remote debugging, "
                f"then set browser_cdp_port in config. Hint: {cdp_launch_hint(config, user_data_dir=str(user_data_dir))}"
            ),
        )

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return BrowserSearchResult(
            ok=False,
            message="playwright not installed — pip install -e '.[browser]'",
        )

    endpoint = _cdp_endpoint(config)
    async with async_playwright() as pw:
        try:
            browser = await pw.chromium.connect_over_cdp(endpoint)
        except Exception as exc:  # noqa: BLE001
            hint = cdp_launch_hint(config, user_data_dir=str(user_data_dir))
            return BrowserSearchResult(
                ok=False,
                message=f"CDP connect failed ({endpoint}): {exc}. Launch: {hint}",
            )

        page = await _pick_page(browser, index_url)
        context = page.context
        if cookies:
            try:
                await context.add_cookies(_playwright_cookie_list(cookies))
            except Exception:  # noqa: BLE001 — profile may already hold session
                pass

        if "gsxt.gov.cn" not in (page.url or ""):
            await page.goto(index_url, wait_until="domcontentloaded", timeout=60_000)

        await asyncio.sleep(2.0)
        ready_wait = min(max(config.browser_search_timeout * 0.5, 15.0), 40.0)
        block = await _wait_page_ready(page, ready_wait)
        if block == "ct_challenge":
            return BrowserSearchResult(
                ok=False,
                message="CT/瑞数 did not clear in attached Chrome — complete verification manually in that window",
                cookies=await _context_cookies(page),
            )
        if block == "blocked":
            return BrowserSearchResult(
                ok=False,
                message="GSXT NWAF in attached Chrome — use a normal (non-automation) Chrome profile via CDP",
                cookies=await _context_cookies(page),
                html_snippet=(await page.content())[:1500],
            )
        if block in ("captcha", "auth_expired"):
            return BrowserSearchResult(
                ok=False,
                message=f"GSXT browser {block}",
                cookies=await _context_cookies(page),
                html_snippet=(await page.content())[:1500],
            )

        api_row = await _inbrowser_api_search(page, keyword, config)
        if api_row and (api_row.get("name") or api_row.get("credit_code")):
            return BrowserSearchResult(
                ok=True,
                row=api_row,
                cookies=await _context_cookies(page),
                message="ok (playwright cdp api)",
            )

        # DOM search fallback
        submit_js = """
        ({ kw }) => {
          const selectors = ['#keyword','input[name="keyword"]','input[name="searchword"]','input[type="search"]'];
          let input = null;
          for (const sel of selectors) { input = document.querySelector(sel); if (input) break; }
          if (!input) return { ok: false, error: 'search input not found' };
          input.focus(); input.value = kw;
          input.dispatchEvent(new Event('input', { bubbles: true }));
          const btns = ['.search_button','.searchBtn','button.search','#btn_query'];
          for (const sel of btns) {
            const btn = document.querySelector(sel);
            if (btn) { btn.click(); return { ok: true }; }
          }
          input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
          return { ok: true };
        }
        """
        submit = await page.evaluate(submit_js, keyword)
        if isinstance(submit, dict) and not submit.get("ok"):
            return BrowserSearchResult(
                ok=False,
                message=str(submit.get("error") or "search input not found"),
                cookies=await _context_cookies(page),
            )

        deadline = time.monotonic() + config.browser_search_timeout
        last_html = ""
        while time.monotonic() < deadline:
            await asyncio.sleep(1.0)
            last_html = await page.content()
            hint = classify_browser_block(last_html)
            if hint in ("blocked", "captcha", "auth_expired"):
                return BrowserSearchResult(
                    ok=False,
                    message=f"GSXT browser {hint}",
                    cookies=await _context_cookies(page),
                    html_snippet=last_html[:1500],
                )
            row = parse_search_html(last_html, keyword=keyword)
            if row and (row.get("name") or row.get("credit_code")):
                return BrowserSearchResult(
                    ok=True,
                    row=row,
                    cookies=await _context_cookies(page),
                    message="ok (playwright cdp dom)",
                )
            api_row = await _inbrowser_api_search(page, keyword, config)
            if api_row and (api_row.get("name") or api_row.get("credit_code")):
                return BrowserSearchResult(
                    ok=True,
                    row=api_row,
                    cookies=await _context_cookies(page),
                    message="ok (playwright cdp api)",
                )

        return BrowserSearchResult(
            ok=False,
            message="GSXT playwright CDP search timed out",
            cookies=await _context_cookies(page),
            html_snippet=last_html[:1500],
        )
        # Do not close browser — user's real Chrome stays open


def search_registry_playwright_cdp(
    keyword: str,
    *,
    config: GsxtConfig,
    cookies: dict[str, str],
    user_data_dir: Path,
    index_url: str,
) -> BrowserSearchResult:
    try:
        return asyncio.run(
            search_registry_playwright_async(
                keyword,
                config=config,
                cookies=cookies,
                user_data_dir=user_data_dir,
                index_url=index_url,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return BrowserSearchResult(ok=False, message=str(exc))
