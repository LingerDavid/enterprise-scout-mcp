"""Unified session/cookie registry — single config surface for GSXT + L2 cookies."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from enterprise_scout_mcp.config import AppConfig, resolve_project_root
from enterprise_scout_mcp.integrations.enscan_cookies import load_yaml, sync_aiqicha_to_enscan
from enterprise_scout_mcp.integrations.gsxt_session import import_session_file, load_session, save_session


@dataclass(frozen=True)
class SessionSpec:
    name: str
    label: str
    path: Path
    kind: str  # json | text | ensan_yaml
    sync_target: str | None = None


def _resolve_path(root: Path, raw: str) -> Path:
    p = Path(raw)
    return p if p.is_absolute() else root / p


def session_specs(config: AppConfig, root: Path | None = None) -> list[SessionSpec]:
    root = root or resolve_project_root()
    sessions = config.sessions
    gsxt_path = _resolve_path(root, sessions.gsxt_path(config))
    aiqicha_path = _resolve_path(root, sessions.aiqicha_path(config))
    ensan_path = _resolve_path(root, config.integrations.ensan_go.config_path)
    return [
        SessionSpec(
            name="gsxt",
            label="GSXT L1 personal login",
            path=gsxt_path,
            kind="json",
        ),
        SessionSpec(
            name="aiqicha",
            label="爱企查 cookie (L2 / Playwright)",
            path=aiqicha_path,
            kind="text",
            sync_target=str(ensan_path),
        ),
        SessionSpec(
            name="enscan",
            label="ENScan_GO config (cookies.aiqicha)",
            path=ensan_path,
            kind="ensan_yaml",
        ),
    ]


def _mask(value: str, n: int = 8) -> str:
    if len(value) <= n:
        return value
    return value[:n] + "…"


def _parse_saved_at(path: Path) -> str | None:
    if path.suffix.lower() != ".json":
        return None
    raw = load_session(path)
    if not raw:
        return None
    saved = raw.get("saved_at")
    return str(saved) if saved else None


def session_status(spec: SessionSpec) -> dict[str, Any]:
    path = spec.path
    exists = path.is_file()
    row: dict[str, Any] = {
        "name": spec.name,
        "label": spec.label,
        "path": str(path),
        "exists": exists,
        "kind": spec.kind,
    }
    if spec.sync_target:
        row["sync_target"] = spec.sync_target
    if not exists:
        row["ready"] = False
        return row

    if spec.kind == "json":
        raw = load_session(path)
        cookies = raw.get("cookies") if raw else None
        count = len(cookies) if isinstance(cookies, dict) else 0
        row["cookie_count"] = count
        row["saved_at"] = _parse_saved_at(path)
        row["ready"] = count > 0
        if isinstance(cookies, dict):
            row["cookie_preview"] = {k: _mask(str(v)) for k, v in list(cookies.items())[:5]}
    elif spec.kind == "text":
        text = path.read_text(encoding="utf-8").strip()
        row["ready"] = bool(text)
        row["cookie_preview"] = _mask(text, 24)
    elif spec.kind == "ensan_yaml":
        try:
            data = load_yaml(path)
            cookies = data.get("cookies") or {}
            aqc = str(cookies.get("aiqicha") or "")
            row["ready"] = bool(aqc)
            row["cookie_preview"] = _mask(aqc, 24) if aqc else ""
            row["platforms"] = list(cookies.keys())
        except OSError:
            row["ready"] = False
    return row


def list_sessions(config: AppConfig) -> dict[str, Any]:
    root = resolve_project_root()
    sessions = config.sessions
    inbox = _resolve_path(root, sessions.export_inbox)
    specs = session_specs(config, root)
    return {
        "sessions_dir": str(_resolve_path(root, sessions.dir)),
        "export_inbox": str(inbox),
        "export_inbox_exists": inbox.is_dir(),
        "items": [session_status(s) for s in specs],
    }


def import_session(
    config: AppConfig,
    name: str,
    *,
    from_file: Path,
) -> dict[str, Any]:
    root = resolve_project_root()
    spec = next((s for s in session_specs(config, root) if s.name == name), None)
    if spec is None:
        raise ValueError(f"unknown session {name!r}; choose gsxt or aiqicha")

    if name == "gsxt":
        preview = import_session_file(from_file, spec.path)
        return {"ok": True, "session": name, "path": str(spec.path), "cookie_preview": preview}

    if name == "aiqicha":
        spec.path.parent.mkdir(parents=True, exist_ok=True)
        text = from_file.read_text(encoding="utf-8")
        spec.path.write_text(text, encoding="utf-8")
        preview = text.strip()[:24] + ("…" if len(text.strip()) > 24 else "")
        out: dict[str, Any] = {
            "ok": True,
            "session": name,
            "path": str(spec.path),
            "cookie_preview": preview,
        }
        if spec.sync_target:
            ensan = Path(spec.sync_target)
            synced = sync_aiqicha_to_enscan(cookie_source=spec.path, enscan_config=ensan)
            out["enscan_synced"] = True
            out["enscan_config"] = str(ensan)
            out["enscan_preview"] = synced
        return out

    raise ValueError(f"import not supported for {name!r}")


def gsxt_cdp_hint(config: AppConfig) -> dict[str, Any]:
    """Print how to launch real Chrome for Playwright connect_over_cdp (Ruishu-safe)."""
    from enterprise_scout_mcp.integrations.gsxt_transport import resolve_browser_backend

    root = resolve_project_root()
    gsxt = config.integrations.gsxt
    data_dir = Path(gsxt.browser_user_data_dir)
    if not data_dir.is_absolute():
        data_dir = root / data_dir
    port = int(gsxt.browser_cdp_port or 9222)
    host = (gsxt.browser_cdp_host or "127.0.0.1").strip() or "127.0.0.1"
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    launch = (
        f'chrome.exe --remote-debugging-port={port} '
        f'--user-data-dir="{data_dir}" '
        f"(Playwright connect_over_cdp -> http://{host}:{port})"
    )
    return {
        "backend": resolve_browser_backend(gsxt),
        "browser_cdp_host": host,
        "browser_cdp_port": port,
        "user_data_dir": str(data_dir),
        "launch_command": launch,
        "windows_chrome_paths": chrome_paths,
        "steps": [
            "Close all Chrome windows using the same profile.",
            f"Launch Chrome with --remote-debugging-port={port} and --user-data-dir (see launch_command).",
            "Open https://www.gsxt.gov.cn/index.html and complete Ruishu/NWAF checks manually.",
            "Optional: login at shiming.gsxt.gov.cn, then escout sessions import gsxt --from-file cookies.json",
            f"Set integrations.gsxt.browser_cdp_port: {port} in config.yaml",
            "Run: escout smoke-registry-l1 苏州挚途",
        ],
    }


def warmup_gsxt_session(config: AppConfig, *, probe_keyword: str = "苏州挚途") -> dict[str, Any]:
    """Warm profile via real browser search (preferred) — also refreshes cookies."""
    from enterprise_scout_mcp.integrations.gsxt_browser import search_registry_browser
    from enterprise_scout_mcp.integrations.gsxt_session import load_session as load_gsxt

    root = resolve_project_root()
    gsxt = config.integrations.gsxt
    dest = _resolve_path(root, config.sessions.gsxt_path(config))
    data_dir = Path(gsxt.browser_user_data_dir)
    if not data_dir.is_absolute():
        data_dir = root / data_dir
    existing: dict[str, str] = {}
    if dest.is_file():
        raw = load_gsxt(dest)
        if raw and isinstance(raw.get("cookies"), dict):
            existing = {str(k): str(v) for k, v in raw["cookies"].items()}
    probe = search_registry_browser(
        probe_keyword,
        config=gsxt,
        cookies=existing,
        user_data_dir=data_dir,
        index_url=gsxt.base_url.rstrip("/") + "/index.html",
    )
    if probe.cookies:
        save_session(dest, probe.cookies, note="warmup browser search")
    preview = {
        k: (v[:8] + "…" if len(v) > 8 else v)
        for k, v in list((probe.cookies or existing).items())[:5]
    }
    out: dict[str, Any] = {
        "ok": probe.ok,
        "session": "gsxt",
        "path": str(dest),
        "warmup": True,
        "cookie_count": len(probe.cookies or existing),
        "cookie_preview": preview,
        "probe_keyword": probe_keyword,
        "probe_ok": probe.ok,
        "probe_message": probe.message,
    }
    if probe.row:
        out["probe_row"] = probe.row
    return out
