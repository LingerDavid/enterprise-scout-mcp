"""East Money 核心题材 (CoreConception)."""

from __future__ import annotations

from enterprise_scout_mcp.sources.eastmoney_core_conception import (
    concept_boards_from_payload,
    core_highlights_from_payload,
)


def test_core_highlights_from_payload() -> None:
    payload = {
        "hxtc": [
            {
                "KEYWORD": "防水龙头",
                "KEY_CLASSIF": "行业地位",
                "KEY_CLASSIF_CODE": "001",
                "MAINPOINT": "1",
                "MAINPOINT_CONTENT": "国内防水行业龙头",
                "IS_POINT": "1",
            }
        ],
    }
    rows = core_highlights_from_payload(payload, security_id="SZSE:002271", collected_at="t0")
    assert len(rows) == 1
    assert rows[0]["keyword"] == "防水龙头"
    assert rows[0]["is_highlight"] == "1"


def test_concept_boards_from_payload() -> None:
    payload = {
        "ssbk": [
            {
                "BOARD_CODE": "1208",
                "BOARD_NAME": "建材概念",
                "BOARD_RANK": 1,
                "IS_PRECISE": "1",
            }
        ],
    }
    rows = concept_boards_from_payload(payload, security_id="SZSE:002271", collected_at="t0")
    assert len(rows) == 1
    assert rows[0]["board_name"] == "建材概念"
    assert rows[0]["board_rank"] == "1"
