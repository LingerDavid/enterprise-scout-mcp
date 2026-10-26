"""East Money CompanySurvey jbzl profile."""

from __future__ import annotations

from enterprise_scout_mcp.sources.eastmoney_company_profile import company_profile_from_payload


def test_company_profile_from_payload() -> None:
    payload = {
        "jbzl": [
            {
                "ORG_NAME": "东方雨虹",
                "ORG_PROFILE": "国内防水龙头。",
                "CHAIRMAN": "李卫国",
                "REG_NUM": "91110000102551540H",
                "REG_CAPITAL": 238869.9866,
                "EMP_NUM": 10318,
                "INDUSTRYCSRC1": "制造业-化学原料和化学制品制造业",
                "EM2016": "建材-其他建材",
            }
        ],
    }
    rows = company_profile_from_payload(payload, security_id="SZSE:002271", collected_at="t0")
    assert len(rows) == 1
    assert rows[0]["issuer_name"] == "东方雨虹"
    assert rows[0]["org_profile"] == "国内防水龙头。"
    assert rows[0]["chairman"] == "李卫国"
    assert rows[0]["emp_num"] == "10318.0"
