"""F10-style dossier assembly."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from enterprise_scout_mcp.integrations.listed_dossier import build_listed_dossier
from enterprise_scout_mcp.output.listed_schema import identity_row, segments_row, workforce_row


def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), path)


def test_build_listed_dossier_tabs(tmp_path: Path) -> None:
    wh = tmp_path / "warehouse"
    iid = "91110000123456789X"
    sid = "SZSE:002271"
    _write(
        wh / "listed" / "identity" / "part.parquet",
        [
            identity_row(
                issuer_id=iid,
                issuer_name="东方雨虹",
                security_id=sid,
                exchange="SZSE",
                code="002271",
                board="主板",
                csrc_industry_l2="化学原料和化学制品制造业",
                document_id="t",
                collected_at="t0",
            )
        ],
    )
    _write(
        wh / "listed" / "segments" / "part.parquet",
        [
            segments_row(
                issuer_id=iid,
                period="2024",
                kind="product",
                segment_id="s1",
                parent_segment_id="",
                name="防水材料",
                revenue="100",
                cost="60",
                comparable_flag="true",
                document_id="t",
                collected_at="t0",
            )
        ],
    )
    _write(
        wh / "listed" / "workforce" / "part.parquet",
        [
            workforce_row(
                issuer_id=iid,
                period="2025",
                staff_num="10318",
                avg_salary="277051.5048",
                avg_revenue="2672868.0728",
                avg_net_profit="10977.6188",
                document_id="t",
                collected_at="t0",
            )
        ],
    )
    dossier = build_listed_dossier(wh, "002271.SZ", include_peers=False)
    assert dossier["ok"] is True
    assert dossier["symbol"] == "002271.SZ"
    assert dossier["tabs"]["公司概况"]["issuer_name"] == "东方雨虹"
    assert len(dossier["tabs"]["经营分析"]["segments"]) == 1
    assert dossier["tabs"]["员工及业务竞争力"]["workforce"][0]["period"] == "2025"
    assert dossier["tabs"]["员工及业务竞争力"]["workforce"][0]["staff_num"] == "10318"
