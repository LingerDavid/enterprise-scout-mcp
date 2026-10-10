"""Phase-2 dimensions (credit / judicial) — explicit stub until paid API wired."""

from __future__ import annotations

from enterprise_scout_mcp.channels.base import CollectionChannel
from enterprise_scout_mcp.models import (
    ChannelKind,
    CollectResult,
    CollectTask,
    Dimension,
    PersonaProfile,
    ResultGrade,
)
from enterprise_scout_mcp.transport.egress import EgressContext

_MESSAGES = {
    Dimension.CREDIT: "credit dimension: enable integrations.handaas or wait for phase-2 channel",
    Dimension.JUDICIAL: "judicial dimension: enable integrations.handaas or wait for phase-2 channel",
}


class DeferredDimensionChannel(CollectionChannel):
    kind = ChannelKind.DEFERRED.value

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
        dim = task.primary_dimension
        return CollectResult(
            task=task,
            channel=ChannelKind.DEFERRED,
            grade=ResultGrade.PARTIAL,
            data={"stub": True, "dimension": dim.value},
            message=_MESSAGES.get(dim, f"dimension {dim.value!r} deferred"),
            persona_id=persona.id,
            dimension=dim,
        )
