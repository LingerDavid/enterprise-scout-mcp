"""Parse GSXT search JSON/HTML into registry fields."""

from __future__ import annotations

import json
import re
from typing import Any


_CREDIT_CODE_RE = re.compile(r"\b([0-9A-Z]{18})\b")


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


def _parse_html(html: str) -> dict[str, str] | None:
    lower = html.lower()
    if "geetest" in lower or "验证码" in html or "captcha" in lower:
        return None
    name_m = re.search(r'entName["\']?\s*[:=]\s*["\']([^"\']+)', html)
    code_m = _CREDIT_CODE_RE.search(html)
    if not name_m and not code_m:
        return None
    return {
        "name": name_m.group(1) if name_m else "",
        "credit_code": code_m.group(1) if code_m else "",
        "reg_code": code_m.group(1) if code_m else "",
    }


def classify_response_text(text: str, *, status_code: int = 0) -> str | None:
    """Return captcha/auth_expired/block/challenge hint or None."""
    lower = text.lower()
    if status_code == 521 or ("document.cookie" in text and "location.href" in text):
        return "jsl_challenge"
    if status_code == 405 or "environment checking" in lower or "ctct_bundle" in lower:
        return "ct_challenge"
    if "实名注册" in text or "登录后再进行访问" in text or "auth" in lower and "login" in lower:
        return "auth_expired"
    if "geetest" in lower or "验证码" in text or "captcha" in lower:
        return "captcha"
    if "IP请求异常" in text or "可疑的攻击" in text:
        return "blocked"
    return None
