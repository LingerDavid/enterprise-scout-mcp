"""Solve GSXT 加速乐 (JSL) two-step cookie challenge via Node.js."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import httpx

_NODE_SOLVER = r"""
const fs = require('fs');
const html = fs.readFileSync(process.argv[1], 'utf8');
const pageUrl = process.argv[2];
const userAgent = process.argv[3];
const document = {
  _c: '',
  set cookie(v) { this._c = v; },
  get cookie() { return this._c; },
};
const location = { href: pageUrl, pathname: '/', search: '', reload: () => {} };
const window = { document, location, navigator: { userAgent } };
const setTimeout = (fn) => { try { fn(); } catch (e) {} };

function emit(cookie) {
  process.stdout.write(JSON.stringify({ ok: true, cookie }));
}

const m1 = html.match(/document\.cookie\s*=\s*(.+?);location\.href/s);
if (m1) {
  document.cookie = eval(m1[1]);
  emit(document.cookie);
} else {
  const m2 = html.match(/;go\(\{([\s\S]*?)\}\)/);
  if (!m2) {
    process.stdout.write(JSON.stringify({ ok: false, error: 'no jsl pattern' }));
  } else {
    const arg = '{' + m2[1] + '}';
    const scripts = html.match(/<script[^>]*>([\s\S]*?)<\/script>/gi) || [];
    const big = scripts.map((s) => s.replace(/<\/?script[^>]*>/gi, '')).join('\n');
    const fn = new Function(
      'document', 'window', 'location', 'setTimeout',
      big + '; return go(' + arg + ');',
    );
    fn(document, window, location, setTimeout);
    emit(document.cookie);
  }
}
"""

_MAX_JSL_ROUNDS = 3


def node_available() -> bool:
    return shutil.which("node") is not None


def is_jsl_challenge(status_code: int, text: str) -> bool:
    if status_code == 521:
        return True
    lower = text.lower()
    return "document.cookie" in text and "location.href" in text or "go({" in text


def is_ct_challenge(status_code: int, text: str) -> bool:
    return status_code == 405 or "Environment Checking" in text or "ctct_bundle" in text


def _eval_jsl_html(html: str, page_url: str, user_agent: str) -> str | None:
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html)
        path = f.name
    try:
        out = subprocess.check_output(
            ["node", "-e", _NODE_SOLVER, path, page_url, user_agent],
            text=True,
            timeout=30,
            stderr=subprocess.DEVNULL,
        )
        payload = json.loads(out.strip())
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
        return None
    finally:
        Path(path).unlink(missing_ok=True)
    if not payload.get("ok"):
        return None
    cookie = str(payload.get("cookie") or "")
    if not cookie:
        return None
    return cookie.split(";")[0]


def apply_clearance_cookie(cookies: dict[str, str], clearance: str) -> None:
    if "=" not in clearance:
        return
    name, value = clearance.split("=", 1)
    cookies[name.strip()] = value.strip()


def pass_jsl_challenge(
    client: httpx.Client,
    *,
    page_url: str,
    cookies: dict[str, str],
    user_agent: str,
) -> bool:
    """Run up to two JSL rounds; mutate cookies in place. Returns True if any pass succeeded."""
    if not node_available():
        return False
    passed = False
    for _ in range(_MAX_JSL_ROUNDS):
        try:
            r = client.get(page_url, cookies=cookies)
        except httpx.HTTPError:
            return passed
        if not is_jsl_challenge(r.status_code, r.text):
            return passed or r.status_code == 200
        clearance = _eval_jsl_html(r.text, page_url, user_agent)
        if not clearance:
            return passed
        apply_clearance_cookie(cookies, clearance)
        passed = True
    return passed
