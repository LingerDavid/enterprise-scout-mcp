"""Optional browser warmup to refresh GSXT JSL + CT cookies."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from enterprise_scout_mcp.integrations.gsxt_session import save_session


async def _collect_cookies_async(
    *,
    index_url: str,
    wait_seconds: float,
    user_data_dir: Path,
) -> dict[str, str]:
    import nodriver as uc

    user_data_dir.mkdir(parents=True, exist_ok=True)
    browser = await uc.start(
        user_data_dir=str(user_data_dir.resolve()),
        sandbox=False,
    )
    try:
        await browser.get(index_url)
        await asyncio.sleep(wait_seconds)
        raw = await browser.cookies.get_all()
        out: dict[str, str] = {}
        for c in raw:
            domain = getattr(c, "domain", "") or ""
            if "gsxt.gov.cn" not in domain:
                continue
            name = getattr(c, "name", "") or ""
            if not name:
                continue
            out[name] = getattr(c, "value", "") or ""
        return out
    finally:
        browser.stop()


def browser_warmup_cookies(
    *,
    index_url: str = "https://www.gsxt.gov.cn/index.html",
    wait_seconds: float = 6.0,
    user_data_dir: Path | None = None,
    existing: dict[str, str] | None = None,
) -> dict[str, str]:
    """Headless nodriver visit; requires pip install -e '.[browser]'."""
    _ = existing  # seed via persistent user_data_dir; manual import still supported
    data_dir = user_data_dir or Path("./.state/gsxt_nodriver_data")
    try:
        return asyncio.run(
            _collect_cookies_async(
                index_url=index_url,
                wait_seconds=wait_seconds,
                user_data_dir=data_dir,
            )
        )
    except ImportError as exc:
        raise RuntimeError("nodriver not installed — pip install -e '.[browser]'") from exc


def warmup_and_save(
    dest: Path,
    *,
    index_url: str,
    wait_seconds: float = 6.0,
    user_data_dir: Path | None = None,
    existing: dict[str, str] | None = None,
) -> dict[str, Any]:
    fresh = browser_warmup_cookies(
        index_url=index_url,
        wait_seconds=wait_seconds,
        user_data_dir=user_data_dir,
        existing=existing,
    )
    merged = dict(existing or {})
    merged.update(fresh)
    if not merged:
        raise RuntimeError("browser warmup returned no gsxt.gov.cn cookies")
    save_session(dest, merged, note="browser warmup")
    preview = {k: (v[:8] + "…" if len(v) > 8 else v) for k, v in list(merged.items())[:5]}
    return {"cookie_count": len(merged), "cookie_preview": preview}
