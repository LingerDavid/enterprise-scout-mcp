"""巨潮资讯 — announcement index + PDF download (A-share filings).

QMT supplies structured statements; this module only locates and stores the
disclosure PDF. Parsing segments from the PDF is out of scope here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx

_QUERY_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
_STATIC_BASE = "https://static.cninfo.com.cn/"
_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Referer": "http://www.cninfo.com.cn/",
    "X-Requested-With": "XMLHttpRequest",
}

# Category codes used by cninfo fulltext search.
CATEGORY_ANNUAL = "category_ndbg_szsh"
CATEGORY_INTERIM = "category_bndbg_szsh"
CATEGORY_Q1 = "category_yjdbg_szsh"
CATEGORY_Q3 = "category_sjdbg_szsh"

_SUFFIX_COLUMN = {"SH": "sse", "SZ": "szse", "BJ": "bj"}
_SUFFIX_EXCHANGE = {"SH": "SSE", "SZ": "SZSE", "BJ": "BSE"}


@dataclass(frozen=True)
class CninfoAnnouncement:
    announcement_id: str
    title: str
    adjunct_url: str
    announce_time_ms: int
    security_id: str
    code: str

    @property
    def document_id(self) -> str:
        return f"cninfo:{self.announcement_id}" if self.announcement_id else ""

    @property
    def document_date(self) -> str:
        if self.announce_time_ms <= 0:
            return ""
        # cninfo returns epoch ms in Asia/Shanghai wall clock for display dates.
        from datetime import datetime, timezone

        dt = datetime.fromtimestamp(self.announce_time_ms / 1000.0, tz=timezone.utc)
        return dt.date().isoformat()

    @property
    def pdf_url(self) -> str:
        if not self.adjunct_url:
            return ""
        if self.adjunct_url.startswith("http"):
            return self.adjunct_url
        return urljoin(_STATIC_BASE, self.adjunct_url.lstrip("/"))


def parse_tradecraft_symbol(symbol: str) -> tuple[str, str, str] | None:
    """``600519.SH`` → (``SSE:600519``, ``600519``, ``sse``)."""
    raw = str(symbol or "").strip().upper()
    if "." not in raw:
        return None
    code, suffix = raw.rsplit(".", 1)
    column = _SUFFIX_COLUMN.get(suffix)
    exchange = _SUFFIX_EXCHANGE.get(suffix)
    if not code or not column or not exchange:
        return None
    return f"{exchange}:{code}", code, column


def parse_security_id(security_id: str) -> tuple[str, str, str] | None:
    """``SSE:600519`` → (security_id, code, column)."""
    raw = str(security_id or "").strip().upper()
    if ":" not in raw:
        return None
    exchange, code = raw.split(":", 1)
    rev = {v: k for k, v in _SUFFIX_EXCHANGE.items()}
    suffix = rev.get(exchange)
    column = _SUFFIX_COLUMN.get(suffix or "")
    if not code or not column:
        return None
    return f"{exchange}:{code}", code, column


def resolve_listing(symbol_or_security: str) -> tuple[str, str, str] | None:
    text = str(symbol_or_security or "").strip()
    if ":" in text:
        return parse_security_id(text)
    return parse_tradecraft_symbol(text)


def _normalize_announcements(
    payload: dict[str, Any],
    *,
    security_id: str,
    code: str,
) -> list[CninfoAnnouncement]:
    data = payload.get("announcements")
    if not isinstance(data, list):
        return []
    out: list[CninfoAnnouncement] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        ann_id = str(item.get("announcementId") or "").strip()
        title = str(item.get("announcementTitle") or "").strip()
        adjunct = str(item.get("adjunctUrl") or "").strip()
        if not title:
            continue
        try:
            ts = int(item.get("announcementTime") or 0)
        except (TypeError, ValueError):
            ts = 0
        out.append(
            CninfoAnnouncement(
                announcement_id=ann_id,
                title=title,
                adjunct_url=adjunct,
                announce_time_ms=ts,
                security_id=security_id,
                code=code,
            )
        )
    return out


def query_announcements(
    symbol_or_security: str,
    *,
    category: str = CATEGORY_ANNUAL,
    page_num: int = 1,
    page_size: int = 30,
    se_date: str = "",
    client: httpx.Client | None = None,
) -> list[CninfoAnnouncement]:
    """Query cninfo fulltext index. Soft-fail → []."""
    listing = resolve_listing(symbol_or_security)
    if listing is None:
        return []
    security_id, code, column = listing
    form = {
        "stock": code,
        "searchkey": "",
        "sdate": "",
        "edate": "",
        "seDate": se_date,
        "category": category,
        "plate": "",
        "column": column,
        "pageNum": str(page_num),
        "pageSize": str(page_size),
        "tabName": "fulltext",
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }
    own = client is None
    http = client or httpx.Client(timeout=30.0, headers=_HEADERS)
    try:
        resp = http.post(_QUERY_URL, data=form)
        resp.raise_for_status()
        payload = resp.json()
    except Exception:
        return []
    finally:
        if own:
            http.close()
    if not isinstance(payload, dict):
        return []
    return _normalize_announcements(payload, security_id=security_id, code=code)


_ANNUAL_TITLE = re.compile(r"年度报告(?!摘要)|年报(?!摘要)")


def pick_annual_report(
    announcements: list[CninfoAnnouncement],
    *,
    year: str | int | None = None,
) -> CninfoAnnouncement | None:
    """Prefer full annual report PDF; skip abstracts when possible."""
    year_s = str(year) if year is not None else ""
    candidates = [a for a in announcements if a.adjunct_url]
    if year_s:
        candidates = [a for a in candidates if year_s in a.title]
    full = [a for a in candidates if _ANNUAL_TITLE.search(a.title) and "摘要" not in a.title]
    pool = full or candidates
    if not pool:
        return None
    return max(pool, key=lambda a: a.announce_time_ms)


def download_pdf(
    announcement: CninfoAnnouncement,
    dest_dir: Path,
    *,
    client: httpx.Client | None = None,
) -> Path | None:
    """Download PDF bytes to dest_dir. Returns path or None on soft failure."""
    url = announcement.pdf_url
    if not url:
        return None
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = announcement.announcement_id or "unknown"
    dest = dest_dir / f"{name}.pdf"
    if dest.is_file() and dest.stat().st_size > 0:
        return dest
    own = client is None
    http = client or httpx.Client(timeout=60.0, headers=_HEADERS, follow_redirects=True)
    try:
        resp = http.get(url)
        resp.raise_for_status()
        body = resp.content
        if not body or len(body) < 100:
            return None
        dest.write_bytes(body)
        return dest
    except Exception:
        return None
    finally:
        if own:
            http.close()
