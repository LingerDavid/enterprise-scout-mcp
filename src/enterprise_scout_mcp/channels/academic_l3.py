"""L3 academic ingest — local corpus lookup with stub fallback."""

from __future__ import annotations

from pathlib import Path

from enterprise_scout_mcp.channels.base import CollectionChannel
from enterprise_scout_mcp.config import CorpusConfig, resolve_project_root
from enterprise_scout_mcp.integrations.corpus_lookup import corpus_dir_stats, lookup_corpus
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

    def __init__(self, config: CorpusConfig, *, project_root: Path | None = None) -> None:
        self._config = config
        self._root = project_root or resolve_project_root()

    def _corpus_dir(self) -> Path:
        p = Path(self._config.l3_dir)
        return p if p.is_absolute() else self._root / p

    def available(self) -> bool:
        if not self._config.enabled:
            return False
        stats = corpus_dir_stats(self._corpus_dir())
        return stats["exists"] and stats["files"] > 0

    def collect(
        self,
        task: CollectTask,
        persona: PersonaProfile,
        *,
        egress: EgressContext | None = None,
    ) -> CollectResult:
        _ = egress
        hit = lookup_corpus(self._corpus_dir(), task.keyword) if self._config.enabled else None
        if hit:
            return CollectResult(
                task=task,
                channel=ChannelKind.ACADEMIC_L3,
                grade=ResultGrade.OK,
                data={"academic": hit["record"], "corpus": hit},
                message=f"L3 corpus hit ({hit['source_file']})",
                persona_id=persona.id,
                source_tier=SourceTier.L3,
                dimension=task.primary_dimension,
            )
        stats = corpus_dir_stats(self._corpus_dir())
        note = "no corpus dir" if not stats["exists"] else "no matching record"
        return CollectResult(
            task=task,
            channel=ChannelKind.ACADEMIC_L3,
            grade=ResultGrade.PARTIAL,
            data={"stub": True, "tier": SourceTier.L3.value, "corpus": stats},
            message=f"L3 academic {note}; drop JSON/JSONL under {stats['path']}",
            persona_id=persona.id,
            source_tier=SourceTier.L3,
            dimension=task.primary_dimension,
        )
