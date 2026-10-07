"""Egress context passed from scheduler into interactive channels."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EgressContext:
    proxy_url: str | None = None
    impersonate: str | None = None
    user_agent: str | None = None
    accept_language: str | None = None
