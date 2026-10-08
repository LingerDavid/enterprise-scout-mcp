"""Camoufox anti-detect browser backend — architecture §统一伪装出口 / Camoufox."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CamoufoxStatus:
    available: bool
    message: str = ""


def camoufox_available() -> CamoufoxStatus:
    try:
        import camoufox  # noqa: F401

        return CamoufoxStatus(available=True, message="camoufox import ok")
    except ImportError:
        return CamoufoxStatus(
            available=False,
            message="camoufox not installed — pip install -e '.[camoufox]'",
        )


class CamoufoxTransport:
    """
    Thin adapter around Camoufox (Firefox anti-detect).

    Launch is opt-in; used when integrations.camoufox.enabled and package present.
    Callers get a Playwright-compatible browser via camoufox.sync_api / AsyncNewBrowser.
    """

    def __init__(self, *, headless: bool = True, humanize: bool = True) -> None:
        self._headless = headless
        self._humanize = humanize

    def status(self) -> CamoufoxStatus:
        return camoufox_available()

    def launch_sync(self, **kwargs: Any) -> Any:
        """Return Camoufox sync browser context manager / browser."""
        st = self.status()
        if not st.available:
            raise RuntimeError(st.message)
        from camoufox.sync_api import Camoufox

        opts = {"headless": self._headless, "humanize": self._humanize, **kwargs}
        return Camoufox(**opts)
