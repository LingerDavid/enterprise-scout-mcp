"""Unified session/cookie registry — single config surface for GSXT + L2 cookies."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from enterprise_scout_mcp.config import AppConfig, resolve_project_root
from enterprise_scout_mcp.integrations.enscan_cookies import load_yaml, sync_aiqicha_to_enscan
from enterprise_scout_mcp.integrations.gsxt_session import import_session_file, load_session


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


def warmup_gsxt_session(config: AppConfig) -> dict[str, Any]:
    from enterprise_scout_mcp.integrations.gsxt_session import load_session as load_gsxt
    from enterprise_scout_mcp.integrations.gsxt_warmup import warmup_and_save

    root = resolve_project_root()
    gsxt = config.integrations.gsxt
    dest = _resolve_path(root, config.sessions.gsxt_path(config))
    data_dir = Path(gsxt.browser_user_data_dir)
    if not data_dir.is_absolute():
        data_dir = root / data_dir
    existing = None
    if dest.is_file():
        raw = load_gsxt(dest)
        if raw and isinstance(raw.get("cookies"), dict):
            existing = raw["cookies"]
    result = warmup_and_save(
        dest,
        index_url=gsxt.base_url.rstrip("/") + "/index.html",
        wait_seconds=gsxt.browser_warmup_wait_seconds,
        user_data_dir=data_dir,
        existing=existing,
    )
    return {"ok": True, "session": "gsxt", "path": str(dest), "warmup": True, **result}
