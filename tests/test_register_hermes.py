"""Hermes config registration."""

from __future__ import annotations

import sys
from pathlib import Path

# scripts/ is not a package; import by path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import register_hermes as rh  # noqa: E402


def test_register_dry_run(tmp_path: Path, monkeypatch) -> None:
    cfg = tmp_path / ".hermes" / "config.yaml"
    monkeypatch.setattr(rh, "hermes_config_path", lambda: cfg)
    rh.register(tmp_path, dry_run=True, use_venv=False)
    assert not cfg.exists()
