"""Load warehouse parquet into Neo4j (Company + HOLDS + Supplement + Conflict)."""

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


def supplement_id(row: dict[str, Any]) -> str:
    keyword = str(row.get("query_keyword", "")).strip()
    dimension = str(row.get("dimension", "")).strip()
    corpus_file = str(row.get("corpus_file", "")).strip()
    collected_at = str(row.get("collected_at", "")).strip()
    return "|".join(p for p in (keyword, dimension, corpus_file, collected_at) if p) or keyword


def conflict_id(row: dict[str, Any]) -> str:
    keyword = str(row.get("query_keyword", "")).strip()
    field = str(row.get("field", "")).strip()
    collected_at = str(row.get("collected_at", "")).strip()
    return "|".join(p for p in (keyword, field, collected_at) if p) or keyword


@dataclass
class ImportStats:
    entities_merged: int = 0
    holds_merged: int = 0
    branches_merged: int = 0
    skipped_edges: int = 0
    supplements_merged: int = 0
    conflicts_merged: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "entities_merged": self.entities_merged,
            "holds_merged": self.holds_merged,
            "branches_merged": self.branches_merged,
            "skipped_edges": self.skipped_edges,
            "supplements_merged": self.supplements_merged,
            "conflicts_merged": self.conflicts_merged,
        }


def _supplement_paths(warehouse_dir: Path) -> list[Path]:
    base = warehouse_dir / "supplements"
    return [
        base / "l3" / "part.parquet",
        base / "judicial" / "part.parquet",
    ]


def _read_parquet(path: Path) -> list[dict[str, Any]]:
    import pyarrow.parquet as pq

    if not path.is_file():
        return []
    return pq.read_table(path).to_pylist()


def _keyword_company_index(entities: list[dict[str, Any]]) -> dict[str, str]:
    """Map query_keyword → preferred Company.id (credit_code / entity_id / name)."""
    index: dict[str, str] = {}
    for row in entities:
        keyword = str(row.get("query_keyword", "")).strip()
        if not keyword:
            continue
        cid = company_id(
            str(row.get("credit_code", "") or row.get("entity_id", "")),
            str(row.get("name", "") or keyword),
        )
        if cid:
            index[keyword] = cid
    return index


def _ensure_constraints(session: Any) -> None:
    for cypher in (
        "CREATE CONSTRAINT company_id IF NOT EXISTS FOR (c:Company) REQUIRE c.id IS UNIQUE",
        "CREATE CONSTRAINT supplement_id IF NOT EXISTS FOR (s:Supplement) REQUIRE s.id IS UNIQUE",
        "CREATE CONSTRAINT conflict_id IF NOT EXISTS FOR (x:Conflict) REQUIRE x.id IS UNIQUE",
    ):
        session.run(cypher)


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
    conflicts = _read_parquet(warehouse_dir / "conflicts" / "part.parquet")
    supplements: list[dict[str, Any]] = []
    for path in _supplement_paths(warehouse_dir):
        supplements.extend(_read_parquet(path))

    if dry_run:
        stats.entities_merged = len(entities)
        stats.holds_merged = sum(1 for e in edges if e.get("relation") in ("invest", "holder"))
        stats.branches_merged = sum(1 for e in edges if e.get("relation") == "branch")
        stats.supplements_merged = len(supplements)
        stats.conflicts_merged = len(conflicts)
        return stats

    from neo4j import GraphDatabase

    keyword_index = _keyword_company_index(entities)
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session() as session:
            _ensure_constraints(session)

            for row in entities:
                cid = company_id(
                    str(row.get("credit_code", "") or row.get("entity_id", "")),
                    str(row.get("name", "")),
                )
                if not cid:
                    continue
                session.run(
                    """
                    MERGE (c:Company {id: $id})
                    SET c.name = $name,
                        c.former_name = $former_name,
                        c.credit_code = $credit_code,
                        c.entity_id = $entity_id,
                        c.platform = $platform,
                        c.source_channel = $source_channel,
                        c.source_tier = $source_tier,
                        c.dimension = $dimension,
                        c.query_keyword = $query_keyword,
                        c.grade = $grade,
                        c.persona_id = $persona_id,
                        c.degraded = $degraded,
                        c.collected_at = $collected_at
                    """,
                    id=cid,
                    name=str(row.get("name", "")),
                    former_name=str(row.get("former_name", "")),
                    credit_code=str(row.get("credit_code", "")),
                    entity_id=str(row.get("entity_id", "")),
                    platform=str(row.get("platform", "")),
                    source_channel=str(row.get("source_channel", "")),
                    source_tier=str(row.get("source_tier", "")),
                    dimension=str(row.get("dimension", "")),
                    query_keyword=str(row.get("query_keyword", "")),
                    grade=str(row.get("grade", "")),
                    persona_id=str(row.get("persona_id", "")),
                    degraded=bool(row.get("degraded", False)),
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

            for row in supplements:
                keyword = str(row.get("query_keyword", "")).strip()
                if not keyword:
                    continue
                cid = keyword_index.get(keyword) or company_id("", keyword)
                sid = supplement_id(row)
                if not sid:
                    continue
                session.run(
                    "MERGE (c:Company {id: $id}) SET c.name = coalesce(c.name, $name)",
                    id=cid,
                    name=keyword,
                )
                session.run(
                    """
                    MERGE (s:Supplement {id: $sid})
                    SET s.query_keyword = $query_keyword,
                        s.dimension = $dimension,
                        s.source_tier = $source_tier,
                        s.source_channel = $source_channel,
                        s.corpus_file = $corpus_file,
                        s.grade = $grade,
                        s.collected_at = $collected_at,
                        s.payload_json = $payload_json,
                        s.message = $message
                    WITH s
                    MATCH (c:Company {id: $cid})
                    MERGE (c)-[r:HAS_SUPPLEMENT]->(s)
                    SET r.dimension = $dimension,
                        r.source_tier = $source_tier
                    """,
                    sid=sid,
                    cid=cid,
                    query_keyword=keyword,
                    dimension=str(row.get("dimension", "")),
                    source_tier=str(row.get("source_tier", "")),
                    source_channel=str(row.get("source_channel", "")),
                    corpus_file=str(row.get("corpus_file", "")),
                    grade=str(row.get("grade", "")),
                    collected_at=str(row.get("collected_at", "")),
                    payload_json=str(row.get("payload_json", "")),
                    message=str(row.get("message", "")),
                )
                stats.supplements_merged += 1

            for row in conflicts:
                keyword = str(row.get("query_keyword", "")).strip()
                if not keyword:
                    continue
                cid = keyword_index.get(keyword) or company_id("", keyword)
                xid = conflict_id(row)
                if not xid:
                    continue
                session.run(
                    "MERGE (c:Company {id: $id}) SET c.name = coalesce(c.name, $name)",
                    id=cid,
                    name=keyword,
                )
                session.run(
                    """
                    MERGE (x:Conflict {id: $xid})
                    SET x.query_keyword = $query_keyword,
                        x.field = $field,
                        x.l1_value = $l1_value,
                        x.l2_value = $l2_value,
                        x.l1_grade = $l1_grade,
                        x.l2_grade = $l2_grade,
                        x.l1_channel = $l1_channel,
                        x.l2_channel = $l2_channel,
                        x.platform = $platform,
                        x.collected_at = $collected_at,
                        x.message = $message
                    WITH x
                    MATCH (c:Company {id: $cid})
                    MERGE (c)-[r:HAS_CONFLICT]->(x)
                    SET r.field = $field
                    """,
                    xid=xid,
                    cid=cid,
                    query_keyword=keyword,
                    field=str(row.get("field", "")),
                    l1_value=str(row.get("l1_value", "")),
                    l2_value=str(row.get("l2_value", "")),
                    l1_grade=str(row.get("l1_grade", "")),
                    l2_grade=str(row.get("l2_grade", "")),
                    l1_channel=str(row.get("l1_channel", "")),
                    l2_channel=str(row.get("l2_channel", "")),
                    platform=str(row.get("platform", "")),
                    collected_at=str(row.get("collected_at", "")),
                    message=str(row.get("message", "")),
                )
                stats.conflicts_merged += 1
    finally:
        driver.close()
    return stats
