"""L3 academic ingest stub — placeholder until external corpus wired."""

from __future__ import annotations

from enterprise_scout_mcp.channels.base import CollectionChannel
from enterprise_scout_mcp.models import (
    ChannelKind,
    CollectResult,
    CollectTask,
    PersonaProfile,
    ResultGrade,
    SourceTier,
)
from enterprise_scout_mcp.transport.egress import EgressContext


class AcademicL3Channel(CollectionChannel):
    kind = ChannelKind.ACADEMIC_L3.value

    def available(self) -> bool:
        return True

    def collect(
        self,
        task: CollectTask,
        persona: PersonaProfile,
        *,
        egress: EgressContext | None = None,
    ) -> CollectResult:
        _ = egress
        return CollectResult(
            task=task,
            channel=ChannelKind.ACADEMIC_L3,
            grade=ResultGrade.PARTIAL,
            data={"stub": True, "tier": SourceTier.L3.value},
            message="L3 academic ingest not wired; configure external corpus ingest",
            persona_id=persona.id,
            source_tier=SourceTier.L3,
            dimension=task.primary_dimension,
        )
