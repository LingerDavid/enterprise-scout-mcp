"""Load warehouse parquet into Neo4j (Company + HOLDS edges)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def company_id(entity_id: str, name: str) -> str:
    eid = (entity_id or "").strip()
    return eid if eid else name.strip()


def parse_percent(ratio: str) -> float | None:
    if not ratio:
        return None
    text = ratio.replace("%", "").strip()
    m = re.search(r"([\d.]+)", text)
    if not m:
        return None
    val = float(m.group(1))
    if val <= 0:
        return None
    return val if val <= 100 else None


@dataclass
class ImportStats:
    entities_merged: int = 0
    holds_merged: int = 0
    branches_merged: int = 0
    skipped_edges: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "entities_merged": self.entities_merged,
            "holds_merged": self.holds_merged,
            "branches_merged": self.branches_merged,
            "skipped_edges": self.skipped_edges,
        }


def _read_parquet(path: Path) -> list[dict[str, Any]]:
    import pyarrow.parquet as pq

    if not path.is_file():
        return []
    return pq.read_table(path).to_pylist()


def import_warehouse(
    warehouse_dir: Path,
    *,
    uri: str,
    user: str,
    password: str,
    dry_run: bool = False,
) -> ImportStats:
    stats = ImportStats()
    entities = _read_parquet(warehouse_dir / "entities" / "part.parquet")
    edges = _read_parquet(warehouse_dir / "edges" / "equity" / "part.parquet")

    if dry_run:
        stats.entities_merged = len(entities)
        stats.holds_merged = sum(1 for e in edges if e.get("relation") in ("invest", "holder"))
        stats.branches_merged = sum(1 for e in edges if e.get("relation") == "branch")
        return stats

    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session() as session:
            for row in entities:
                cid = company_id(str(row.get("entity_id", "")), str(row.get("name", "")))
                if not cid:
                    continue
                session.run(
                    """
                    MERGE (c:Company {id: $id})
                    SET c.name = $name,
                        c.former_name = $former_name,
                        c.platform = $platform,
                        c.source_channel = $source_channel,
                        c.query_keyword = $query_keyword,
                        c.grade = $grade,
                        c.collected_at = $collected_at
                    """,
                    id=cid,
                    name=str(row.get("name", "")),
                    former_name=str(row.get("former_name", "")),
                    platform=str(row.get("platform", "")),
                    source_channel=str(row.get("source_channel", "")),
                    query_keyword=str(row.get("query_keyword", "")),
                    grade=str(row.get("grade", "")),
                    collected_at=str(row.get("collected_at", "")),
                )
                stats.entities_merged += 1

            for row in edges:
                src_name = str(row.get("src_name", "")).strip()
                dst_name = str(row.get("dst_name", "")).strip()
                if not src_name or not dst_name:
                    stats.skipped_edges += 1
                    continue
                src_id = company_id("", src_name)
                dst_id = company_id("", dst_name)
                relation = str(row.get("relation", ""))
                percent = parse_percent(str(row.get("ratio", "")))

                session.run(
                    "MERGE (c:Company {id: $id}) SET c.name = $name",
                    id=src_id,
                    name=src_name,
                )
                session.run(
                    "MERGE (c:Company {id: $id}) SET c.name = $name",
                    id=dst_id,
                    name=dst_name,
                )

                if relation == "branch":
                    session.run(
                        """
                        MATCH (a:Company {id: $src_id}), (b:Company {id: $dst_id})
                        MERGE (a)-[:BRANCH]->(b)
                        """,
                        src_id=src_id,
                        dst_id=dst_id,
                    )
                    stats.branches_merged += 1
                elif relation in ("invest", "holder"):
                    session.run(
                        """
                        MATCH (a:Company {id: $src_id}), (b:Company {id: $dst_id})
                        MERGE (a)-[r:HOLDS]->(b)
                        SET r.percent = $percent,
                            r.relation = $relation,
                            r.section = $section
                        """,
                        src_id=src_id,
                        dst_id=dst_id,
                        percent=percent,
                        relation=relation,
                        section=str(row.get("section", "")),
                    )
                    stats.holds_merged += 1
                else:
                    stats.skipped_edges += 1
    finally:
        driver.close()
    return stats
