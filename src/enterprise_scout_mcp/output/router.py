"""Output grading router — ok → warehouse, partial → raw, captcha → retry queue."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from enterprise_scout_mcp.config import OutputConfig
from enterprise_scout_mcp.models import CollectResult, ResultGrade
from enterprise_scout_mcp.output.edge_writer import append_edges
from enterprise_scout_mcp.output.parquet_writer import append_entity


class OutputRouter:
    def __init__(self, config: OutputConfig) -> None:
        self._config = config

    def _route_dir(self, grade: ResultGrade) -> Path:
        key = self._config.grade_routes.get(grade.value, "raw")
        if key == "warehouse":
            return Path(self._config.warehouse_dir)
        if key == "dead_letter":
            return Path(self._config.raw_dir) / "dead_letter"
        if key == "retry_queue":
            return Path(self._config.raw_dir) / "retry_queue"
        return Path(self._config.raw_dir)

    def persist(self, result: CollectResult) -> Path:
        out_dir = self._route_dir(result.grade)
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safe_kw = "".join(c if c.isalnum() else "_" for c in result.task.keyword)[:64]
        path = out_dir / f"{result.task.platform.value}_{safe_kw}_{ts}.json"
        payload = {
            "keyword": result.task.keyword,
            "platform": result.task.platform.value,
            "channel": result.channel.value,
            "grade": result.grade.value,
            "persona_id": result.persona_id,
            "message": result.message,
            "fields": list(result.task.fields),
            "depth": result.task.depth,
            "data": result.data,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        if self._config.parquet_enabled:
            wh = Path(self._config.warehouse_dir)
            append_entity(result, wh)
            append_edges(result, wh)
        return path
