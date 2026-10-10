#!/usr/bin/env python3
"""Nodriver fallback fetch for aiqicha (captcha / JS challenge)."""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import sys
import urllib.parse
from pathlib import Path


def _load_fetch_module():
    path = Path(__file__).with_name("aiqicha_fetch_one.py")
    spec = importlib.util.spec_from_file_location("aiqicha_fetch_one", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fetch_camoufox(
    keyword: str,
    timeout: float,
    *,
    proxy: str = "",
    headless: bool = True,
) -> tuple[str, list[dict[str, str]]]:
    mod = _load_fetch_module()
    try:
        from enterprise_scout_mcp.integrations.camoufox_fetch import (
            classify_aiqicha_html,
            fetch_html_camoufox,
        )
    except ImportError:
        # Script invoked outside installed package — load sibling module by path
        import sys

        root = Path(__file__).resolve().parents[1] / "src"
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from enterprise_scout_mcp.integrations.camoufox_fetch import (
            classify_aiqicha_html,
            fetch_html_camoufox,
        )

    url = f"https://www.aiqicha.com/s?q={urllib.parse.quote(keyword)}&t=0"
    html = fetch_html_camoufox(
        url,
        headless=headless,
        wait_seconds=min(timeout, 12.0),
        proxy_url=proxy or None,
    )
    return classify_aiqicha_html(html, mod.extract_companies)


async def fetch_nodriver(
    keyword: str,
    cookie_file: Path | None,
    user_data_dir: Path,
    timeout: float,
) -> tuple[str, list[dict[str, str]]]:
    mod = _load_fetch_module()
    try:
        import nodriver as uc
    except ImportError as exc:
        raise RuntimeError("nodriver not installed; pip install nodriver") from exc

    url = f"https://www.aiqicha.com/s?q={urllib.parse.quote(keyword)}&t=0"
    user_data_dir.mkdir(parents=True, exist_ok=True)
    browser = await uc.start(user_data_dir=str(user_data_dir.resolve()), sandbox=False)
    try:
        page = await browser.get(url)
        await asyncio.sleep(min(timeout, 8.0))
        html = await page.get_content()
    finally:
        browser.stop()

    lower = html.lower()
    if "验证码" in html or "captcha" in lower or "安全验证" in html:
        return "captcha", []
    companies = mod.extract_companies(html)
    if not companies and ("未找到" in html or "没有找到" in html):
        return "not_found", []
    return "ok", companies


def main() -> int:
    p = argparse.ArgumentParser(description="Nodriver fetch one aiqicha keyword")
    p.add_argument("keyword")
    p.add_argument("--db", required=True, type=Path)
    p.add_argument("--cookie-file", type=Path, default=None)
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--user-data-dir", type=Path, default=Path("./nodriver_data"))
    p.add_argument("--browser-backend", default="nodriver", help="nodriver | camoufox")
    p.add_argument("--proxy", default="")
    p.add_argument("--impersonate", default="")
    p.add_argument("--user-agent", default="")
    p.add_argument("--accept-language", default="")
    args = p.parse_args()

    mod = _load_fetch_module()
    args.db.parent.mkdir(parents=True, exist_ok=True)
    mod.ensure_db(args.db)

    source = "aiqicha_fetch_nodriver"
    try:
        if args.browser_backend == "camoufox":
            source = "aiqicha_fetch_camoufox"
            status, companies = fetch_camoufox(
                args.keyword,
                args.timeout,
                proxy=args.proxy,
                headless=True,
            )
        else:
            status, companies = asyncio.run(
                fetch_nodriver(args.keyword, args.cookie_file, args.user_data_dir, args.timeout)
            )
    except RuntimeError as exc:
        print(json.dumps({"status": "error", "message": str(exc), "source": source}))
        return 1

    best = companies[0] if companies else None
    if best:
        mod.upsert(args.db, best)
        payload = {"status": status, "company": best, "source": source}
    else:
        payload = {"status": status, "company": None, "source": source}

    print(json.dumps(payload, ensure_ascii=False))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
