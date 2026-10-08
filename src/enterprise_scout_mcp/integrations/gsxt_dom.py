"""GSXT index-page DOM search helpers (Playwright + nodriver)."""

from __future__ import annotations

import json
from typing import Any

INPUT_SELECTORS = (
    "#keyword",
    "input[name='keyword']",
    "input[name='searchword']",
    'input[placeholder*="企业"]',
    'input[placeholder*="关键字"]',
    'input[placeholder*="名称"]',
    ".searchbox input",
    ".search_input",
    "input[type='search']",
)

BUTTON_SELECTORS = (
    ".search_button",
    ".searchBtn",
    "#btn_query",
    "a.search_button",
    "span.search_button",
    ".btn-search",
    "button[type='submit']",
)

# nodriver: keyword embedded via json.dumps(kw) — never pass raw string to Playwright destructuring
DOM_SEARCH_JS = """
(() => {
  const kw = %s;
  const setNativeValue = (input, value) => {
    const proto = input instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : HTMLInputElement.prototype;
    const desc = Object.getOwnPropertyDescriptor(proto, 'value');
    if (desc && desc.set) desc.set.call(input, value);
    else input.value = value;
    input.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: value }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  };
  const inputSelectors = %s;
  let input = null;
  let inputSel = '';
  for (const sel of inputSelectors) {
    const el = document.querySelector(sel);
    if (el && el.offsetParent !== null) { input = el; inputSel = sel; break; }
  }
  if (!input) return { ok: false, error: 'search input not found' };
  input.focus();
  setNativeValue(input, kw);
  const btnSelectors = %s;
  for (const sel of btnSelectors) {
    const btn = document.querySelector(sel);
    if (btn && btn.offsetParent !== null) {
      btn.click();
      return { ok: true, method: 'click', selector: sel, input: inputSel };
    }
  }
  if (typeof window.$ === 'function') {
    const jqBtn = window.$('.search_button');
    if (jqBtn.length) { jqBtn.click(); return { ok: true, method: 'jquery', input: inputSel }; }
  }
  input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', bubbles: true }));
  input.dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter', code: 'Enter', bubbles: true }));
  return { ok: true, method: 'enter', input: inputSel };
})()
""" % (
    "%s",
    json.dumps(list(INPUT_SELECTORS), ensure_ascii=False),
    json.dumps(list(BUTTON_SELECTORS), ensure_ascii=False),
)


def nodriver_search_script(keyword: str) -> str:
    return DOM_SEARCH_JS % json.dumps(keyword, ensure_ascii=False)


async def submit_gsxt_dom_search_playwright(page: Any, keyword: str) -> dict[str, Any]:
    """Use Playwright locators (fill/click) — avoids evaluate arg/destructuring bugs."""
    for sel in INPUT_SELECTORS:
        loc = page.locator(sel).first
        try:
            if await loc.count() == 0:
                continue
            if not await loc.is_visible():
                continue
        except Exception:  # noqa: BLE001
            continue
        await loc.scroll_into_view_if_needed()
        await loc.click()
        await loc.fill(keyword)
        await loc.evaluate(
            """(el) => {
              el.dispatchEvent(new Event('input', { bubbles: true }));
              el.dispatchEvent(new Event('change', { bubbles: true }));
            }"""
        )
        for btn_sel in BUTTON_SELECTORS:
            btn = page.locator(btn_sel).first
            try:
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click()
                    return {"ok": True, "method": "click", "selector": btn_sel, "input": sel}
            except Exception:  # noqa: BLE001
                continue
        try:
            clicked = await page.evaluate(
                """() => {
                  if (typeof window.$ !== 'function') return false;
                  const b = window.$('.search_button');
                  if (b.length) { b.click(); return true; }
                  return false;
                }"""
            )
            if clicked:
                return {"ok": True, "method": "jquery", "input": sel}
        except Exception:  # noqa: BLE001
            pass
        await loc.press("Enter")
        return {"ok": True, "method": "enter", "input": sel}
    return {"ok": False, "error": "search input not found"}
