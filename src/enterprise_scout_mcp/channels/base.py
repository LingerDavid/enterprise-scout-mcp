"""Channel ABC — ENScan_GO batch vs Playwright interactive."""

from __future__ import annotations

from abc import ABC, abstractmethod

from enterprise_scout_mcp.models import CollectResult, CollectTask, PersonaProfile


class CollectionChannel(ABC):
    kind: str

    @abstractmethod
    def available(self) -> bool:
        ...

    @abstractmethod
    def collect(self, task: CollectTask, persona: PersonaProfile) -> CollectResult:
        ...
