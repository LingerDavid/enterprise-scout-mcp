#!/usr/bin/env python3
"""Fetch one aiqicha search result and upsert into companies.db (stdout JSON)."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import urllib.parse
from pathlib import Path


def extract_companies(html: str) -> list[dict[str, str]]:
    if "company-list" not in html:
        return []
    blocks = re.split(
        r'(?=<a[^>]*?data-log-title="item-\d+"[^>]*?class="card")',
        html,
    )
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for block in blocks:
        m = re.search(
            r'class="title"[^>]*>\s*<a[^>]*?title="([^"]+)"[^>]*?data-log-title="(item-\d+)"',
            block,
        )
        if not m:
            m = re.search(
                r'class="title"[^>]*>\s*<a[^>]*?data-log-title="(item-\d+)"[^>]*?title="([^"]+)"',
                block,
            )
            if m:
                cid = m.group(1).replace("item-", "")
                name = m.group(2).strip()
            else:
                continue
        else:
            name = m.group(1).strip()
            cid = m.group(2).replace("item-", "")
        if not name or len(name) < 2 or cid in seen:
            continue
        seen.add(cid)
        former = ""
        fm = re.search(
            r'曾用名：</span>\s*<span[^>]*class="legal-txt"[^>]*>(.*?)</span>',
            block,
        )
        if fm:
            former = re.sub(r"<[^>]+>", "", fm.group(1)).strip()
        out.append({"aiqicha_id": cid, "company_name": name, "former_name": former})
    return out


def ensure_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS companies (
            aiqicha_id TEXT PRIMARY KEY,
            company_name TEXT NOT NULL,
            former_name TEXT DEFAULT ''
        )
        """
    )
    conn.commit()
    conn.close()


def upsert(db_path: Path, row: dict[str, str]) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT OR IGNORE INTO companies (aiqicha_id, company_name, former_name)
        VALUES (?, ?, ?)
        """,
        (row["aiqicha_id"], row["company_name"], row.get("former_name", "")),
    )
    conn.commit()
    conn.close()


def load_cookie_header(cookie_file: Path | None) -> dict[str, str]:
    if not cookie_file or not cookie_file.is_file():
        return {}
    text = cookie_file.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    return {"Cookie": text.replace("\n", "; ")}


def _get_html(
    url: str,
    headers: dict[str, str],
    *,
    timeout: float,
    proxy: str | None,
    impersonate: str | None,
) -> str:
    if impersonate:
        try:
            from curl_cffi import requests as curl_requests
        except ImportError:
            impersonate = None
        else:
            proxies = {"http": proxy, "https": proxy} if proxy else None
            resp = curl_requests.get(
                url,
                headers=headers,
                proxies=proxies,
                timeout=timeout,
                impersonate=impersonate,
                allow_redirects=True,
            )
            resp.raise_for_status()
            return resp.text

    import httpx

    proxies = proxy
    with httpx.Client(timeout=timeout, follow_redirects=True, proxy=proxies) as client:
        resp = client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.text


def fetch(
    keyword: str,
    cookie_file: Path | None,
    timeout: float,
    *,
    proxy: str | None = None,
    impersonate: str | None = None,
    user_agent: str | None = None,
    accept_language: str | None = None,
) -> tuple[str, list[dict[str, str]]]:
    url = f"https://www.aiqicha.com/s?q={urllib.parse.quote(keyword)}&t=0"
    headers = {
        "User-Agent": user_agent
        or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept-Language": accept_language or "zh-CN,zh;q=0.9",
        **load_cookie_header(cookie_file),
    }
    html = _get_html(
        url,
        headers,
        timeout=timeout,
        proxy=proxy,
        impersonate=impersonate,
    )
    lower = html.lower()
    if "验证码" in html or "captcha" in lower or "安全验证" in html:
        return "captcha", []
    companies = extract_companies(html)
    if not companies and ("未找到" in html or "没有找到" in html):
        return "not_found", []
    return "ok", companies


def main() -> int:
    p = argparse.ArgumentParser(description="Fetch one aiqicha keyword")
    p.add_argument("keyword")
    p.add_argument("--db", required=True, type=Path)
    p.add_argument("--cookie-file", type=Path, default=None)
    p.add_argument("--timeout", type=float, default=30.0)
    p.add_argument("--proxy", default=None, help="http://host:port proxy URL")
    p.add_argument("--impersonate", default=None, help="curl_cffi impersonate profile")
    p.add_argument("--user-agent", default=None)
    p.add_argument("--accept-language", default=None)
    args = p.parse_args()

    args.db.parent.mkdir(parents=True, exist_ok=True)
    ensure_db(args.db)

    status, companies = fetch(
        args.keyword,
        args.cookie_file,
        args.timeout,
        proxy=args.proxy,
        impersonate=args.impersonate,
        user_agent=args.user_agent,
        accept_language=args.accept_language,
    )
    best = companies[0] if companies else None
    source = "aiqicha_fetch_one"
    if args.impersonate:
        source = f"{source}+curl_cffi"
    if args.proxy:
        source = f"{source}+proxy"
    if best:
        upsert(args.db, best)
        payload = {"status": status, "company": best, "source": source}
    else:
        payload = {"status": status, "company": None, "source": source}

    print(json.dumps(payload, ensure_ascii=False))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
