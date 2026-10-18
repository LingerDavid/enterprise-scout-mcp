"""Listed disclosure sampler with mocked HTTP."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from enterprise_scout_mcp.integrations.listed_sample import sample_listed_disclosure

pq = pytest.importorskip("pyarrow.parquet")


class _FakeTransport(httpx.BaseTransport):
    def handle_request(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "szse_stock.json" in url:
            return httpx.Response(200, json={"stockList": [{"code": "600519", "orgId": "gssh0600519"}]})
        if "hisAnnouncement/query" in url:
            body = {
                "announcements": [
                    {
                        "announcementId": "ann-99",
                        "announcementTitle": "2024年年度报告",
                        "adjunctUrl": "finalpage/2025-03-29/ann-99.PDF",
                        "announcementTime": 1_743_220_800_000,
                    }
                ]
            }
            return httpx.Response(200, json=body)
        if "static.cninfo.com.cn" in url or url.endswith(".PDF"):
            return httpx.Response(200, content=b"%PDF-1.4 fake-content-long-enough-" + b"x" * 200)
        if "ShareholderResearch" in url:
            body = {
                "sdgd": [
                    {
                        "HOLDER_RANK": 1,
                        "HOLDER_NAME": "A",
                        "HOLD_NUM": 100,
                        "HOLD_NUM_RATIO": 10.5,
                        "END_DATE": "2024-12-31",
                    }
                ]
            }
            return httpx.Response(200, json=body)
        if "CompanySurvey" in url:
            body = {
                "jbzl": [
                    {
                        "REG_NUM": "9152000071430580XT",
                        "ORG_NAME": "贵州茅台酒股份有限公司",
                        "INDUSTRYCSRC1": "制造业-酒、饮料和精制茶制造业",
                    }
                ]
            }
            return httpx.Response(200, json=body)
        return httpx.Response(404)


def test_sample_listed_writes_corpus_and_holders(tmp_path: Path) -> None:
    corpus = tmp_path / "listed"
    warehouse = tmp_path / "warehouse"
    pdf_dir = tmp_path / "pdf"
    client = httpx.Client(transport=_FakeTransport())
    try:
        report = sample_listed_disclosure(
            "600519.SH",
            corpus_dir=corpus,
            warehouse_dir=warehouse,
            pdf_dir=pdf_dir,
            year=2024,
            download=True,
            client=client,
        )
    finally:
        client.close()

    assert report["security_id"] == "SSE:600519"
    assert report["issuer_id"] == "9152000071430580XT"
    assert report["holders"] == 1
    assert report["picked"]["document_id"] == "cninfo:ann-99"
    assert Path(report["pdf_path"]).is_file()
    assert Path(report["corpus_path"]).is_file()
    line = Path(report["corpus_path"]).read_text(encoding="utf-8").strip()
    record = json.loads(line)
    assert record["issuer_id"] == "9152000071430580XT"
    assert record["holders"][0]["holder_name"] == "A"
    holders_path = warehouse / "listed" / "holders" / "part.parquet"
    assert holders_path.is_file()
    assert pq.read_table(holders_path).num_rows == 1
    identity_path = warehouse / "listed" / "identity" / "part.parquet"
    assert pq.read_table(identity_path).to_pylist()[0]["issuer_id"] == "9152000071430580XT"
