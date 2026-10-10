"""Camoufox browser fetch — shared by scripts and optional in-process callers."""

from __future__ import annotations

import time
from typing import Callable


def fetch_html_camoufox(
    url: str,
    *,
    headless: bool = True,
    humanize: bool = True,
    wait_seconds: float = 6.0,
    proxy_url: str | None = None,
) -> str:
    """Load URL in Camoufox and return page HTML."""
    try:
        from camoufox.sync_api import Camoufox
    except ImportError as exc:
        raise RuntimeError("camoufox not installed; pip install -e '.[camoufox]'") from exc

    opts: dict = {"headless": headless, "humanize": humanize}
    if proxy_url:
        opts["proxy"] = {"server": proxy_url}

    with Camoufox(**opts) as browser:
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded")
        time.sleep(min(wait_seconds, 30.0))
        return page.content()


def classify_aiqicha_html(html: str, extract: Callable[[str], list]) -> tuple[str, list]:
    """Map HTML to status + company rows using shared extract hook."""
    lower = html.lower()
    if "验证码" in html or "captcha" in lower or "安全验证" in html:
        return "captcha", []
    companies = extract(html)
    if not companies and ("未找到" in html or "没有找到" in html):
        return "not_found", []
    return "ok", companies
