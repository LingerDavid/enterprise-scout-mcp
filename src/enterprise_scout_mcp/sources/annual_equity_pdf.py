"""Deterministic equity extraction from A-share annual report page text/tables.

PDF bytes go through pdfplumber when the optional ``pdf`` extra is installed.
Tests feed synthetic pages — no real filings in the repo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from enterprise_scout_mcp.output.listed_schema import (
    holders_row,
    listed_control_row,
    subsidiaries_row,
)

# Prefer the main top-10 holdings table; avoid 转融通 / 无限售续页误命中.
_HOLDER_TITLE = re.compile(
    r"前\s*十\s*名\s*股\s*东\s*持\s*股\s*情\s*况|前\s*10\s*名\s*股\s*东\s*持\s*股|"
    r"截至报告期末前十名股东",
    re.I,
)
_SUB_TITLE = re.compile(
    r"重要子公司|纳入合并范围的子公司|在子公司中的权益|合并范围内子公司",
    re.I,
)
_CONTROL_TITLE = re.compile(r"实际控制人|控股股东|股权结构", re.I)
_DIAGRAM_HINT = re.compile(r"股权结构图|见下图|如下图|示意图", re.I)

_YEAR_IN_TITLE = re.compile(r"(20\d{2})\s*年")
_PCT_CELL = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*%?\s*$")
_SHARES_CELL = re.compile(r"^\s*[\d,]+(?:\.\d+)?\s*$")

_MAX_SUBSIDIARIES = 80

_HOLDER_NAME_HINTS = ("股东名称", "股东姓名")
_HOLDER_PCT_HINTS = ("持股比例", "占总股本比例", "比例(%)", "比例（%）", "比例")
_HOLDER_SHARES_HINTS = ("期末持股数量", "持股数量", "持股数")
_HOLDER_TYPE_HINTS = ("股东性质", "股份性质")
_SUB_NAME_HINTS = ("子公司名称", "公司名称", "企业名称")
_SUB_PCT_HINTS = ("持股比例", "直接持股", "权益比例", "比例")
_SUB_BIZ_HINTS = ("主营业务", "主要业务", "经营范围")


@dataclass
class PageContent:
    """One PDF page: plain text plus table matrices (row → cells)."""

    index: int
    text: str
    tables: list[list[list[str]]] = field(default_factory=list)


@dataclass
class EquityExtractResult:
    holders: list[dict[str, Any]] = field(default_factory=list)
    subsidiaries: list[dict[str, Any]] = field(default_factory=list)
    listed_control: list[dict[str, Any]] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    page_hits: dict[str, list[int]] = field(default_factory=dict)


def period_from_annual_meta(
    *,
    title: str = "",
    document_date: str = "",
    year: str | int | None = None,
) -> str:
    """Derive report period ``YYYY`` from CLI year, title, or announcement date."""
    if year is not None and str(year).strip():
        raw = str(year).strip()
        if re.fullmatch(r"20\d{2}", raw):
            return raw
    m = _YEAR_IN_TITLE.search(str(title or ""))
    if m:
        return m.group(1)
    date = str(document_date or "").strip()
    if len(date) >= 4 and date[:4].isdigit():
        # Announcement in year N+1 for year-N annual → prefer N-1 when Jan–Apr.
        y = int(date[:4])
        month = int(date[5:7]) if len(date) >= 7 and date[5:7].isdigit() else 6
        if month <= 4:
            return str(y - 1)
        return str(y)
    return ""


def _cell(v: Any) -> str:
    if v is None:
        return ""
    return re.sub(r"\s+", " ", str(v).replace("\n", " ")).strip()


def _norm_header(cell: str) -> str:
    return re.sub(r"\s+", "", _cell(cell))


def _find_col(headers: Sequence[str], hints: Sequence[str]) -> int | None:
    norms = [_norm_header(h) for h in headers]
    for hint in hints:
        h = re.sub(r"\s+", "", hint)
        for i, n in enumerate(norms):
            if h and h in n:
                return i
    return None


def _parse_pct_percent(raw: str, *, assume_percent: bool = True) -> str:
    """Return percentage string (F10-compatible), or empty.

    Annual-report 「比例(%)」 cells are already percent (including 0.40).
    Only promote fraction→percent when ``assume_percent`` is False.
    """
    s = _cell(raw).replace(",", "").replace("％", "%")
    m = _PCT_CELL.match(s)
    if not m:
        return ""
    val = float(m.group(1))
    if not assume_percent and 0 < abs(val) <= 1.0 and "%" not in s:
        val *= 100.0
    return f"{val:.4f}".rstrip("0").rstrip(".")


def _parse_shares(raw: str) -> str:
    s = _cell(raw).replace(",", "").replace(" ", "")
    if not _SHARES_CELL.match(s):
        return ""
    try:
        return str(int(float(s)))
    except (TypeError, ValueError):
        return ""


def _table_has_title_nearby(page_text: str, title_re: re.Pattern[str]) -> bool:
    return bool(title_re.search(page_text or ""))


def _is_holder_seed_page(text: str) -> bool:
    if not _table_has_title_nearby(text, _HOLDER_TITLE):
        return False
    # 转融通专表也会写「前十名股东」；主表标题常含「不含通过转融通」，需放行。
    t = text or ""
    if "参与转融通业务出借" in t or "转融通出借/归还原因" in t:
        return False
    return True

def _pick_holder_tables(
    pages: Sequence[PageContent],
) -> tuple[list[list[list[str]]], list[int]]:
    """Collect holder tables; include the immediate next page for continuations."""
    by_index = {p.index: p for p in pages}
    ordered = sorted(by_index)
    seed_idxs = [idx for idx in ordered if _is_holder_seed_page(by_index[idx].text)]
    if not seed_idxs:
        return [], []
    # First real top-10 section only (avoid later repeats).
    seed = seed_idxs[0]
    want = {seed}
    pos = ordered.index(seed)
    if pos + 1 < len(ordered):
        want.add(ordered[pos + 1])
    hits = sorted(want)
    tables: list[list[list[str]]] = []
    for idx in hits:
        for tbl in by_index[idx].tables:
            if len(tbl) >= 2:
                tables.append(tbl)
    return tables, hits
def _pick_first_sub_table(
    pages: Sequence[PageContent],
) -> tuple[list[list[str]] | None, list[int]]:
    for page in pages:
        if not _table_has_title_nearby(page.text, _SUB_TITLE):
            continue
        for tbl in page.tables:
            if len(tbl) >= 2:
                return tbl, [page.index]
    return None, []


def _is_holder_noise_name(name: str) -> bool:
    n = _cell(name)
    if not n or n in {"合计", "小计"}:
        return True
    if n.startswith("前十") or "转融通" in n or "无限售条件股东" in n:
        return True
    if "股东名称" in n:
        return True
    return False


def _heuristic_holder_fields(cells: list[str]) -> tuple[str, str, str, str] | None:
    """Infer name / shares / pct / share_class from a continuation row (no header)."""
    if not cells:
        return None
    name = cells[0]
    if _is_holder_noise_name(name) or len(name) < 2:
        return None
    pct = ""
    pct_i: int | None = None
    for i, c in enumerate(cells[1:], start=1):
        if not c:
            continue
        p = _parse_pct_percent(c, assume_percent=True)
        if not p:
            continue
        try:
            v = float(p)
        except ValueError:
            continue
        if 0 < v <= 100:
            pct = p
            pct_i = i
            break
    if pct_i is None:
        return None
    # End-of-period shares sit before 比例; pick the largest to skip 报告期内增减.
    shares = ""
    best_n = -1
    for c in cells[1:pct_i]:
        s = _parse_shares(c)
        if not s:
            continue
        n = int(s)
        if n > best_n:
            best_n = n
            shares = s
    share_class = ""
    for c in cells[pct_i + 1 :]:
        if c and re.search(r"法人|其他|国家|未知|境内|境外|自然人", c):
            share_class = c
            break
    return name, shares, pct, share_class

def _rows_from_holder_table(
    table: list[list[str]],
    *,
    security_id: str,
    as_of: str,
    document_id: str,
    collected_at: str,
    start_rank: int = 0,
) -> list[dict[str, Any]]:
    if not table:
        return []
    headers = [_cell(c) for c in table[0]]
    name_i = _find_col(headers, _HOLDER_NAME_HINTS)
    pct_i = _find_col(headers, _HOLDER_PCT_HINTS)
    shares_i = _find_col(headers, _HOLDER_SHARES_HINTS)
    type_i = _find_col(headers, _HOLDER_TYPE_HINTS)
    use_header = name_i is not None and pct_i is not None
    data_rows = table[1:] if use_header else table
    out: list[dict[str, Any]] = []
    rank = start_rank
    for raw in data_rows:
        if rank >= 10:
            break
        cells = [_cell(c) for c in raw]
        if use_header:
            if name_i >= len(cells):
                continue
            name = cells[name_i]
            if _is_holder_noise_name(name):
                continue
            pct = _parse_pct_percent(
                cells[pct_i] if pct_i < len(cells) else "",
                assume_percent=True,
            )
            if not pct:
                continue
            shares = ""
            if shares_i is not None and shares_i < len(cells):
                shares = _parse_shares(cells[shares_i])
            share_class = ""
            if type_i is not None and type_i < len(cells):
                share_class = cells[type_i]
        else:
            guessed = _heuristic_holder_fields(cells)
            if guessed is None:
                continue
            name, shares, pct, share_class = guessed
        rank += 1
        out.append(
            holders_row(
                security_id=security_id,
                as_of=as_of,
                rank=str(rank),
                holder_name=name,
                holder_type="",
                shares=shares,
                pct_total=pct,
                share_class=share_class,
                document_id=document_id,
                collected_at=collected_at,
            )
        )
    return out

def _validate_holders(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    total = 0.0
    ok: list[dict[str, Any]] = []
    for row in rows:
        try:
            pct = float(str(row.get("pct_total") or "") or "nan")
        except ValueError:
            continue
        if not (0 < pct <= 100):
            continue
        total += pct
        ok.append(row)
    if not ok or total > 105.0:
        return []
    return ok


def _rows_from_sub_table(
    table: list[list[str]],
    *,
    issuer_id: str,
    period: str,
    document_id: str,
    collected_at: str,
) -> list[dict[str, Any]]:
    if not table or not issuer_id or not period:
        return []
    headers = [_cell(c) for c in table[0]]
    name_i = _find_col(headers, _SUB_NAME_HINTS)
    pct_i = _find_col(headers, _SUB_PCT_HINTS)
    biz_i = _find_col(headers, _SUB_BIZ_HINTS)
    if name_i is None:
        return []
    out: list[dict[str, Any]] = []
    for raw in table[1:]:
        if len(out) >= _MAX_SUBSIDIARIES:
            break
        cells = [_cell(c) for c in raw]
        if name_i >= len(cells):
            continue
        name = cells[name_i]
        if not name or name in {"合计", "小计"}:
            continue
        pct = ""
        if pct_i is not None and pct_i < len(cells):
            pct = _parse_pct_percent(cells[pct_i])
        biz = ""
        if biz_i is not None and biz_i < len(cells):
            biz = cells[biz_i]
        out.append(
            subsidiaries_row(
                issuer_id=issuer_id,
                period=period,
                name=name,
                direct_pct=pct,
                consolidated="true",
                main_business=biz,
                document_id=document_id,
                collected_at=collected_at,
            )
        )
    return out


def _extract_control_from_text(
    pages: Sequence[PageContent],
    *,
    issuer_id: str,
    issuer_name: str,
    as_of: str,
    document_id: str,
    collected_at: str,
) -> tuple[list[dict[str, Any]], list[str], list[int]]:
    skipped: list[str] = []
    hits: list[int] = []
    blobs: list[str] = []
    for page in pages:
        if _CONTROL_TITLE.search(page.text or ""):
            hits.append(page.index)
            blobs.append(page.text or "")
            if _DIAGRAM_HINT.search(page.text or ""):
                skipped.append("control_diagram_image")
    if not blobs:
        skipped.append("no_control_section")
        return [], skipped, hits
    if "control_diagram_image" in skipped and len("".join(blobs)) < 80:
        return [], skipped, hits

    text = "\n".join(blobs)
    # Prefer explicit endpoint sentence.
    endpoint = ""
    endpoint_type = ""
    if re.search(r"无实际控制人|不存在实际控制人", text):
        endpoint_type = "none"
        endpoint = "无实际控制人"
    elif re.search(r"国务院|国资委|财政[厅部]|人民政府", text):
        endpoint_type = "state"
    elif re.search(r"先生|女士|自然人", text):
        endpoint_type = "natural"

    hops: list[dict[str, Any]] = []
    # Very small heuristic: "A 持有 本公司 xx%" style near 实际控制人.
    for m in re.finditer(
        r"([\u4e00-\u9fffA-Za-z0-9（）()·\-]{2,30})"
        r"(?:直接|间接|合计)?"
        r"(?:持有|控制)"
        r"(?:本公司|公司|发行人)?"
        r".{0,8}?"
        r"(\d+(?:\.\d+)?)\s*%",
        text,
    ):
        src = m.group(1).strip()
        if src in {"公司", "本公司", "发行人"} or len(src) < 2:
            continue
        pct = _parse_pct_percent(m.group(2) + "%")
        dst = issuer_name or "本公司"
        hops.append(
            listed_control_row(
                issuer_id=issuer_id,
                as_of=as_of,
                hop=str(len(hops) + 1),
                src_name=src,
                dst_name=dst,
                ratio=pct,
                ratio_kind="ownership",
                is_concert_party="false",
                endpoint_type=endpoint_type if len(hops) == 0 else "",
                document_id=document_id,
                collected_at=collected_at,
            )
        )
        if len(hops) >= 6:
            break

    if endpoint_type == "none" and not hops:
        hops.append(
            listed_control_row(
                issuer_id=issuer_id,
                as_of=as_of,
                hop="1",
                src_name=endpoint,
                dst_name=issuer_name or "本公司",
                ratio="",
                ratio_kind="ownership",
                is_concert_party="false",
                endpoint_type="none",
                document_id=document_id,
                collected_at=collected_at,
            )
        )

    if not hops:
        skipped.append("control_parse_failed")
        return [], skipped, hits
    # Require endpoint_type on first hop when we claim a chain.
    if not str(hops[0].get("endpoint_type") or "").strip() and endpoint_type:
        hops[0]["endpoint_type"] = endpoint_type
    if not str(hops[0].get("endpoint_type") or "").strip():
        skipped.append("control_no_endpoint")
        return [], skipped, hits
    return hops, skipped, hits


def extract_equity_from_pages(
    pages: Sequence[PageContent],
    *,
    security_id: str,
    issuer_id: str,
    document_id: str,
    period: str,
    as_of: str,
    collected_at: str = "",
    issuer_name: str = "",
) -> EquityExtractResult:
    """Extract holders / subsidiaries / control from in-memory pages."""
    result = EquityExtractResult()
    if not security_id or not document_id:
        result.skipped.append("missing_ids")
        return result

    holder_tables, holder_pages = _pick_holder_tables(pages)
    result.page_hits["holders"] = holder_pages
    best: list[dict[str, Any]] = []
    stitched: list[dict[str, Any]] = []
    for tbl in holder_tables:
        chunk = _rows_from_holder_table(
            tbl,
            security_id=security_id,
            as_of=as_of,
            document_id=document_id,
            collected_at=collected_at,
            start_rank=0,
        )
        alone = _validate_holders(chunk[:10])
        if len(alone) > len(best):
            best = alone
        # Cross-page: header page often has 0 data rows; stitch onto continuation.
        if len(stitched) < 10:
            more = _rows_from_holder_table(
                tbl,
                security_id=security_id,
                as_of=as_of,
                document_id=document_id,
                collected_at=collected_at,
                start_rank=len(stitched),
            )
            stitched.extend(more)
    stitched_ok = _validate_holders(stitched[:10])
    holders = stitched_ok if len(stitched_ok) >= len(best) else best
    if holders:
        for i, row in enumerate(holders, start=1):
            row["rank"] = str(i)
        result.holders = holders
    else:
        result.skipped.append("no_holders_table")
    if not period:
        result.skipped.append("no_period_for_subsidiaries")
    else:
        sub_table, sub_pages = _pick_first_sub_table(pages)
        result.page_hits["subsidiaries"] = sub_pages
        if sub_table is None:
            result.skipped.append("no_subsidiaries_table")
        else:
            result.subsidiaries = _rows_from_sub_table(
                sub_table,
                issuer_id=issuer_id,
                period=period,
                document_id=document_id,
                collected_at=collected_at,
            )
            if not result.subsidiaries:
                result.skipped.append("subsidiaries_parse_failed")

    if not issuer_id:
        result.skipped.append("no_issuer_for_control")
    else:
        control, ctrl_skipped, ctrl_pages = _extract_control_from_text(
            pages,
            issuer_id=issuer_id,
            issuer_name=issuer_name,
            as_of=as_of,
            document_id=document_id,
            collected_at=collected_at,
        )
        result.page_hits["listed_control"] = ctrl_pages
        result.skipped.extend(ctrl_skipped)
        result.listed_control = control

    return result


def load_pdf_pages(pdf_path: Path) -> list[PageContent] | None:
    """Load pages via pdfplumber. None when dependency missing or file unreadable."""
    try:
        import pdfplumber
    except ImportError:
        return None
    path = Path(pdf_path)
    if not path.is_file():
        return None
    pages: list[PageContent] = []
    try:
        with pdfplumber.open(path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                raw_tables = page.extract_tables() or []
                tables: list[list[list[str]]] = []
                for tbl in raw_tables:
                    if not tbl:
                        continue
                    tables.append([[_cell(c) for c in row] for row in tbl])
                pages.append(PageContent(index=i, text=text, tables=tables))
    except Exception:
        return None
    return pages


def extract_equity_from_pdf(
    pdf_path: Path,
    *,
    security_id: str,
    issuer_id: str,
    document_id: str,
    period: str,
    as_of: str,
    collected_at: str = "",
    issuer_name: str = "",
) -> EquityExtractResult:
    pages = load_pdf_pages(pdf_path)
    if pages is None:
        return EquityExtractResult(skipped=["pdfplumber_missing_or_unreadable"])
    if not pages:
        return EquityExtractResult(skipped=["empty_pdf"])
    return extract_equity_from_pages(
        pages,
        security_id=security_id,
        issuer_id=issuer_id,
        document_id=document_id,
        period=period,
        as_of=as_of,
        collected_at=collected_at,
        issuer_name=issuer_name,
    )
