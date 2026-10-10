"""Phase-2 dimensions (credit / judicial) — corpus or explicit stub."""

from __future__ import annotations

from pathlib import Path

from enterprise_scout_mcp.channels.base import CollectionChannel
from enterprise_scout_mcp.config import CorpusConfig, resolve_project_root
from enterprise_scout_mcp.integrations.corpus_lookup import lookup_corpus
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
    Dimension.JUDICIAL: "judicial dimension: add corpus under integrations.corpus.judicial_dir",
}


class DeferredDimensionChannel(CollectionChannel):
    kind = ChannelKind.DEFERRED.value

    def __init__(self, config: CorpusConfig, *, project_root: Path | None = None) -> None:
        self._config = config
        self._root = project_root or resolve_project_root()

    def _judicial_dir(self) -> Path:
        p = Path(self._config.judicial_dir)
        return p if p.is_absolute() else self._root / p

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
        if dim == Dimension.JUDICIAL and self._config.enabled:
            hit = lookup_corpus(self._judicial_dir(), task.keyword)
            if hit:
                return CollectResult(
                    task=task,
                    channel=ChannelKind.DEFERRED,
                    grade=ResultGrade.OK,
                    data={"judicial": hit["record"], "corpus": hit},
                    message=f"judicial corpus hit ({hit['source_file']})",
                    persona_id=persona.id,
                    dimension=dim,
                )
        return CollectResult(
            task=task,
            channel=ChannelKind.DEFERRED,
            grade=ResultGrade.PARTIAL,
            data={"stub": True, "dimension": dim.value},
            message=_MESSAGES.get(dim, f"dimension {dim.value!r} deferred"),
            persona_id=persona.id,
            dimension=dim,
        )
