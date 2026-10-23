"""Local BFS equity penetration tree from warehouse/edges/equity parquet."""

from __future__ import annotations

import re
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

_CORP_MARKERS = (
    "公司",
    "集团",
    "有限",
    "合伙",
    "厂",
    "银行",
    "证券",
    "基金",
    "保险",
    "信托",
    "事务所",
    "合作社",
    "中心",
    "大学",
    "学院",
    "研究院",
    "Co.",
    "Ltd",
    "LLC",
    "Inc",
)


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", "", str(name or "").strip())


def looks_like_corporation(name: str) -> bool:
    text = str(name or "").strip()
    if not text or len(text) < 3:
        return False
    return any(m in text for m in _CORP_MARKERS)


def parse_ratio_pct(raw: str | None) -> float | None:
    if raw is None or raw == "":
        return None
    text = str(raw).strip().replace("%", "").replace("％", "")
    try:
        return float(text)
    except ValueError:
        return None


def equity_edges_path(warehouse_dir: Path) -> Path:
    return Path(warehouse_dir) / "edges" / "equity" / "part.parquet"


def load_edge_rows(warehouse_dir: Path) -> list[dict[str, Any]]:
    path = equity_edges_path(warehouse_dir)
    if not path.is_file():
        return []
    try:
        import pyarrow.parquet as pq
    except ImportError:
        return []
    rows = pq.read_table(path).to_pylist()
    out: list[dict[str, Any]] = []
    for r in rows:
        row = dict(r)
        row.setdefault("credit_code", "")
        out.append(row)
    return out


def resolve_center_name(rows: list[dict[str, Any]], center: str) -> str | None:
    """Pick canonical name string used in edges for this center query."""
    want = normalize_name(center)
    if not want:
        return None
    scores: dict[str, int] = defaultdict(int)
    for r in rows:
        for key in ("src_name", "dst_name", "query_keyword"):
            raw = str(r.get(key) or "").strip()
            if normalize_name(raw) == want:
                scores[raw] += 3 if key == "query_keyword" else 1
        code = str(r.get("credit_code") or "").strip()
        if code and code == center.strip():
            # credit_code match: boost query_keyword or dst/src that share the row
            qk = str(r.get("query_keyword") or "").strip()
            if qk:
                scores[qk] += 5
    if not scores:
        return None
    return max(scores.items(), key=lambda kv: (kv[1], len(kv[0])))[0]


def seeded_keywords(rows: list[dict[str, Any]]) -> set[str]:
    return {normalize_name(str(r.get("query_keyword") or "")) for r in rows if r.get("query_keyword")}


def build_equity_tree(
    warehouse_dir: Path,
    center: str,
    *,
    max_depth: int = 2,
    min_ratio: float = 0.0,
    max_nodes: int = 200,
    include_supply: bool = False,
) -> dict[str, Any]:
    rows = load_edge_rows(warehouse_dir)
    if not rows:
        return {
            "center": center,
            "resolved_name": None,
            "nodes": [],
            "edges": [],
            "truncated": False,
            "missing_neighbors": [],
            "stats": {"edge_rows": 0},
            "hint": "no edges; run collect first (aiqicha / aqc)",
        }

    resolved = resolve_center_name(rows, center)
    if resolved is None:
        return {
            "center": center,
            "resolved_name": None,
            "nodes": [],
            "edges": [],
            "truncated": False,
            "missing_neighbors": [],
            "stats": {"edge_rows": len(rows)},
            "hint": f"center {center!r} not found in edge table",
        }

    # Indexes by normalized name
    out_invest: dict[str, list[dict[str, Any]]] = defaultdict(list)
    in_holder: dict[str, list[dict[str, Any]]] = defaultdict(list)
    out_branch: dict[str, list[dict[str, Any]]] = defaultdict(list)
    out_supply: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for r in rows:
        rel = str(r.get("relation") or "")
        src = str(r.get("src_name") or "").strip()
        dst = str(r.get("dst_name") or "").strip()
        if not src or not dst:
            continue
        sn, dn = normalize_name(src), normalize_name(dst)
        if rel == "invest":
            ratio = parse_ratio_pct(r.get("ratio"))
            if min_ratio > 0:
                if ratio is None or ratio < min_ratio:
                    continue
            out_invest[sn].append(r)
        elif rel == "holder":
            in_holder[dn].append(r)
        elif rel == "branch":
            out_branch[sn].append(r)
        elif rel == "supply" and include_supply:
            out_supply[sn].append(r)

    seeded = seeded_keywords(rows)
    center_key = normalize_name(resolved)

    nodes: dict[str, dict[str, Any]] = {}
    tree_edges: list[dict[str, Any]] = []
    truncated = False
    missing: list[str] = []

    def add_node(name: str, depth: int, role: str) -> bool:
        nonlocal truncated
        key = normalize_name(name)
        if key in nodes:
            return True
        if len(nodes) >= max_nodes:
            truncated = True
            return False
        nodes[key] = {
            "name": name,
            "depth": depth,
            "role": role,
            "corporate": looks_like_corporation(name),
            "seeded": key in seeded,
        }
        return True

    add_node(resolved, 0, "center")
    q: deque[tuple[str, str, int]] = deque([(resolved, center_key, 0)])
    seen_edge: set[tuple[str, str, str]] = set()

    while q:
        display_name, key, depth = q.popleft()
        if depth >= max_depth:
            continue

        def walk(edge_list: list[dict[str, Any]], direction: str) -> None:
            nonlocal truncated
            for r in edge_list:
                src = str(r.get("src_name") or "").strip()
                dst = str(r.get("dst_name") or "").strip()
                rel = str(r.get("relation") or "")
                ek = (src, dst, rel)
                if ek in seen_edge:
                    continue
                if direction == "invest":
                    neighbor, nrole = dst, "investee"
                elif direction == "holder":
                    neighbor, nrole = src, "holder"
                elif direction == "branch":
                    neighbor, nrole = dst, "branch"
                else:
                    neighbor, nrole = dst, "supplier"
                if not neighbor:
                    continue
                if rel == "invest" and min_ratio > 0:
                    ratio = parse_ratio_pct(r.get("ratio"))
                    if ratio is not None and ratio < min_ratio:
                        continue
                nd = depth + 1
                if not add_node(neighbor, nd, nrole):
                    return
                seen_edge.add(ek)
                tree_edges.append(
                    {
                        "src_name": src,
                        "dst_name": dst,
                        "relation": rel,
                        "ratio": r.get("ratio") or "",
                        "section": r.get("section") or "",
                        "credit_code": r.get("credit_code") or "",
                        "depth": nd,
                    }
                )
                nk = normalize_name(neighbor)
                # branch / supply: show only, do not expand further
                if direction in ("branch", "supply"):
                    continue
                if nd < max_depth:
                    q.append((neighbor, nk, nd))

        walk(out_invest.get(key, []), "invest")
        if truncated:
            break
        walk(in_holder.get(key, []), "holder")
        if truncated:
            break
        walk(out_branch.get(key, []), "branch")
        if truncated:
            break
        if include_supply:
            walk(out_supply.get(key, []), "supply")

    # missing: corporate neighbors at depth < max that were never collected as keyword
    for key, node in nodes.items():
        if node["depth"] >= max_depth:
            continue
        if node["role"] == "center":
            continue
        if node["role"] in ("branch", "supplier"):
            continue
        if not node["corporate"]:
            continue
        if key not in seeded:
            missing.append(node["name"])

    # stable unique missing
    seen_m: set[str] = set()
    missing_u: list[str] = []
    for m in missing:
        k = normalize_name(m)
        if k in seen_m:
            continue
        seen_m.add(k)
        missing_u.append(m)

    return {
        "center": center,
        "resolved_name": resolved,
        "nodes": list(nodes.values()),
        "edges": tree_edges,
        "truncated": truncated,
        "missing_neighbors": missing_u,
        "stats": {
            "edge_rows": len(rows),
            "node_count": len(nodes),
            "edge_count": len(tree_edges),
            "missing_count": len(missing_u),
            "max_depth": max_depth,
            "min_ratio": min_ratio,
        },
    }
