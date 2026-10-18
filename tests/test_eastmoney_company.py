"""Company survey payload → credit code."""

from __future__ import annotations

from enterprise_scout_mcp.sources.eastmoney_company import profile_from_survey_payload


def test_profile_from_survey_payload() -> None:
    payload = {
        "jbzl": [
            {
                "REG_NUM": "9152000071430580XT",
                "ORG_NAME": "贵州茅台酒股份有限公司",
                "INDUSTRYCSRC1": "制造业-酒、饮料和精制茶制造业",
            }
        ]
    }
    profile = profile_from_survey_payload(payload)
    assert profile["credit_code"] == "9152000071430580XT"
    assert profile["issuer_name"].startswith("贵州茅台")
    assert profile["csrc_industry_l1"] == "制造业"
    assert "酒" in profile["csrc_industry_l2"]
