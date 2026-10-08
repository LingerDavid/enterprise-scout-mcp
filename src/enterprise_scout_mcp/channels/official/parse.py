"""Parse GSXT search JSON/HTML into registry fields."""

from __future__ import annotations

import json
import re
from typing import Any


# 统一社会信用代码（国标字符集，避免把页面 hash 当成信用代码）
_CREDIT_CODE_RE = re.compile(r"\b([0-9A-HJ-NPQRTUWXY]{2}\d{6}[0-9A-HJ-NPQRTUWXY]{10})\b")
_USCC_LOOSE_RE = re.compile(
    r"统一社会信用代码[：:\s]*</?(?:span|div|font|i|b)[^>]*>\s*"
    r"([0-9A-HJ-NPQRTUWXY]{2}\d{6}[0-9A-HJ-NPQRTUWXY]{10})",
    flags=re.IGNORECASE,
)
_USCC_TEXT_RE = re.compile(
    r"统一社会信用代码[：:\s]{0,40}"
    r"([0-9A-HJ-NPQRTUWXY]{2}\d{6}[0-9A-HJ-NPQRTUWXY]{10})",
)


def parse_search_payload(payload: Any) -> dict[str, str] | None:
    """Extract name + credit_code from GSXT search API JSON."""
    if payload is None:
        return None
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return _parse_html(payload)

    if isinstance(payload, dict):
        for key in ("data", "result", "list", "records", "searchResult"):
            block = payload.get(key)
            row = _first_row(block)
            if row:
                return row
        row = _row_from_dict(payload)
        if row:
            return row

    if isinstance(payload, list):
        row = _first_row(payload)
        if row:
            return row
    return None


def _first_row(block: Any) -> dict[str, str] | None:
    if isinstance(block, list):
        for item in block:
            row = _row_from_dict(item)
            if row:
                return row
    elif isinstance(block, dict):
        for key in ("list", "records", "data", "result"):
            nested = block.get(key)
            if nested is not block:
                row = _first_row(nested)
                if row:
                    return row
        return _row_from_dict(block)
    return None


def _row_from_dict(item: Any) -> dict[str, str] | None:
    if not isinstance(item, dict):
        return None
    name = _pick(item, ("entName", "name", "corpName", "企业名称", "entityName"))
    credit = _pick(
        item,
        (
            "uniscId",
            "creditCode",
            "regNo",
            "统一社会信用代码",
            "socialCreditCode",
            "regNumber",
        ),
    )
    if not credit:
        for v in item.values():
            if isinstance(v, str):
                m = _CREDIT_CODE_RE.search(v)
                if m:
                    credit = m.group(1)
                    break
    if not name and not credit:
        return None
    return {
        "name": name or "",
        "credit_code": credit or "",
        "reg_code": credit or "",
    }


def _pick(row: dict[str, Any], keys: tuple[str, ...]) -> str:
    for k in keys:
        if k in row and row[k]:
            return str(row[k]).strip()
    return ""


def _strip_tags(raw: str) -> str:
    return re.sub(r"<[^>]+>", "", raw).replace("&nbsp;", " ").strip()


def _row_from_search_list_item(item_html: str, keyword: str = "") -> dict[str, str] | None:
    """Parse one GSXT `.search_list_item` card (name in h1, USCC in span.g3)."""
    name = ""
    h1 = re.search(r"<h1[^>]*>([\s\S]*?)</h1>", item_html, flags=re.IGNORECASE)
    if h1:
        name = _strip_tags(h1.group(1))
    credit = ""
    for pat in (_USCC_LOOSE_RE, _USCC_TEXT_RE, _CREDIT_CODE_RE):
        m = pat.search(item_html)
        if m:
            credit = m.group(1)
            break
    if keyword and name and keyword not in name:
        return None
    if not name and not credit:
        return None
    return {"name": name, "credit_code": credit, "reg_code": credit}


def parse_search_html(html: str, keyword: str = "") -> dict[str, str] | None:
    """Parse GSXT search result page — list cards, embedded JSON, or text USCC."""
    if not html:
        return None
    # Use browser classifier — classify_response_text false-positives on ctct_bundle/geetest
    # that are embedded on every normal GSXT result page.
    block = classify_browser_block(html)
    if block in ("ct_challenge", "jsl_challenge", "blocked"):
        return None
    if "search_list_item" not in html.lower() and "统一社会信用代码" not in html:
        if block == "captcha" or classify_response_text(html) in ("ct_challenge", "jsl_challenge"):
            return None

    # Prefer structured result cards (corp-query-search-*.html)
    for m in re.finditer(
        r'<a[^>]*class="[^"]*search_list_item[^"]*"[^>]*>([\s\S]*?)</a>',
        html,
        flags=re.IGNORECASE,
    ):
        row = _row_from_search_list_item(m.group(0), keyword=keyword)
        if row and (row.get("credit_code") or row.get("name")):
            return row

    for pattern in (
        r"uniscId[\"']?\s*[:=]\s*[\"']([0-9A-HJ-NPQRTUWXY]{18})[\"']",
        r"creditCode[\"']?\s*[:=]\s*[\"']([0-9A-HJ-NPQRTUWXY]{18})[\"']",
        r"统一社会信用代码[\s\S]{0,120}?([0-9A-HJ-NPQRTUWXY]{2}\d{6}[0-9A-HJ-NPQRTUWXY]{10})",
    ):
        for block in re.finditer(pattern, html, flags=re.IGNORECASE | re.DOTALL):
            credit = block.group(1)
            # look backward for company name near the USCC
            start = max(0, block.start() - 500)
            chunk = html[start : block.end()]
            name = ""
            for name_pat in (
                r"entName[\"']?\s*[:=]\s*[\"']([^\"']+)[\"']",
                r"corpName[\"']?\s*[:=]\s*[\"']([^\"']+)[\"']",
                r"<h1[^>]*>([\s\S]*?)</h1>",
                r"<a[^>]*>([^<]{2,80})</a>",
            ):
                nm = re.search(name_pat, chunk, flags=re.IGNORECASE)
                if nm:
                    name = _strip_tags(nm.group(1))
                    break
            if keyword and name and keyword not in name:
                continue
            if name or credit:
                return {"name": name, "credit_code": credit, "reg_code": credit}

    return _parse_html(html, keyword=keyword)


def _parse_html(html: str, *, keyword: str = "") -> dict[str, str] | None:
    # Geetest scripts are normal on GSXT result pages — only block standalone captcha walls
    lower = html.lower()
    has_results = "search_list_item" in lower or "统一社会信用代码" in html
    if not has_results and ("geetest" in lower or "验证码" in html or "captcha" in lower):
        return None
    name_m = re.search(r'entName["\']?\s*[:=]\s*["\']([^"\']+)', html)
    name = name_m.group(1) if name_m else ""
    if not name:
        h1 = re.search(r"<h1[^>]*>([\s\S]*?)</h1>", html, flags=re.IGNORECASE)
        if h1:
            name = _strip_tags(h1.group(1))
    code_m = _USCC_LOOSE_RE.search(html) or _USCC_TEXT_RE.search(html) or _CREDIT_CODE_RE.search(html)
    credit = code_m.group(1) if code_m else ""
    if keyword and name and keyword not in name:
        return None
    if not name and not credit:
        return None
    return {
        "name": name,
        "credit_code": credit,
        "reg_code": credit,
    }


def classify_browser_block(html: str) -> str | None:
    """Stricter block hints for full GSXT pages (avoid footer 实名注册 false positives)."""
    lower = html.lower()
    if "nwaf" in lower or "waf页面" in html:
        return "blocked"
    if "environment checking" in lower:
        return "ct_challenge"
    # ctct_bundle is embedded on normal GSXT pages — only block when search chrome is absent
    if "ctct_bundle" in lower and (
        "keyword" not in lower
        and "searchword" not in lower
        and "国家企业信用信息公示系统" not in html
    ):
        return "ct_challenge"
    if "document.cookie" in html and "location.href" in html:
        return "jsl_challenge"
    login_wall = (
        "登录后再进行访问" in html
        or "请先登录" in html
        or "请登录后" in html
        or ("user-login" in lower and "keyword" not in lower and "searchword" not in lower)
    )
    if login_wall:
        return "auth_expired"
    has_search_chrome = (
        "keyword" in lower
        or "searchword" in lower
        or "国家企业信用信息公示系统" in html
    )
    if not has_search_chrome and ("geetest" in lower or "验证码" in html):
        return "captcha"
    if "IP请求异常" in html or "可疑的攻击" in html:
        return "blocked"
    return None


def classify_response_text(text: str, *, status_code: int = 0) -> str | None:
    """Return captcha/auth_expired/block/challenge hint or None (API / short responses)."""
    lower = text.lower()
    if status_code == 521 or ("document.cookie" in text and "location.href" in text):
        return "jsl_challenge"
    if status_code == 405 or "environment checking" in lower or "ctct_bundle" in lower:
        return "ct_challenge"
    if "登录后再进行访问" in text or "请先登录" in text or "请登录后" in text:
        return "auth_expired"
    if "geetest" in lower or "验证码" in text or "captcha" in lower:
        return "captcha"
    if "IP请求异常" in text or "可疑的攻击" in text:
        return "blocked"
    return None
