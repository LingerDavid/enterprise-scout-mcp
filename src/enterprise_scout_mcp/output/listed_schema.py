"""Listed-company warehouse column contracts (no collectors yet).

See docs/listed-company-product-map.md. Amounts are decimal strings in CNY yuan.
"""

from __future__ import annotations

from typing import Any

IDENTITY_COLUMNS = (
    "issuer_id",
    "issuer_name",
    "security_id",
    "exchange",
    "code",
    "board",
    "csrc_industry_l1",
    "csrc_industry_l2",
    "list_date",
    "is_primary_listing",
    "document_id",
    "collected_at",
)

FACTS_COLUMNS = (
    "issuer_id",
    "period",
    "scope",
    "statement",
    "item_code",
    "label",
    "value",
    "unit",
    "currency",
    "scale_in_source",
    "derived",
    "document_id",
    "document_date",
    "audit_opinion",
    "collected_at",
    "supersedes_ref",
)

SEGMENTS_COLUMNS = (
    "issuer_id",
    "period",
    "kind",
    "segment_id",
    "parent_segment_id",
    "name",
    "revenue",
    "cost",
    "comparable_flag",
    "document_id",
    "collected_at",
)

CAPITAL_COLUMNS = (
    "security_id",
    "as_of",
    "total_shares",
    "float_shares",
    "document_id",
    "collected_at",
)

HOLDERS_COLUMNS = (
    "security_id",
    "as_of",
    "rank",
    "holder_name",
    "holder_type",
    "shares",
    "pct_total",
    "share_class",
    "pledge_pct_of_holding",
    "pledge_as_of",
    "freeze_flag",
    "document_id",
    "collected_at",
)

SUBSIDIARIES_COLUMNS = (
    "issuer_id",
    "period",
    "name",
    "direct_pct",
    "consolidated",
    "main_business",
    "document_id",
    "collected_at",
)

LISTED_CONTROL_COLUMNS = (
    "issuer_id",
    "as_of",
    "hop",
    "src_name",
    "dst_name",
    "ratio",
    "ratio_kind",
    "is_concert_party",
    "endpoint_type",
    "document_id",
    "collected_at",
)

EXECUTIVES_COLUMNS = (
    "security_id",
    "person_name",
    "position",
    "position_type",
    "sex",
    "age",
    "education",
    "salary",
    "shares",
    "resume",
    "incumbent_since",
    "document_id",
    "collected_at",
)

DIVIDENDS_COLUMNS = (
    "security_id",
    "notice_date",
    "ex_dividend_date",
    "pay_cash_date",
    "record_date",
    "assign_progress",
    "impl_plan",
    "document_id",
    "collected_at",
)

# Annual workforce competitiveness (CNY yuan unless noted).
WORKFORCE_COLUMNS = (
    "issuer_id",
    "period",
    "staff_num",
    "avg_salary",
    "avg_revenue",
    "avg_net_profit",
    "rd_personnel",
    "rd_ratio",
    "rd_expend",
    "pay_staff_cash",
    "staff_salary_payable",
    "document_id",
    "collected_at",
)

# Latest education mix snapshot (percent strings, sum ≈ 100).
WORKFORCE_EDUCATION_COLUMNS = (
    "issuer_id",
    "as_of",
    "bucket",
    "pct",
    "document_id",
    "collected_at",
)

HOLDER_STATS_COLUMNS = (
    "security_id",
    "as_of",
    "holder_count",
    "holder_count_change_pct",
    "avg_free_shares",
    "avg_hold_amt",
    "document_id",
    "collected_at",
)

IPO_PROFILE_COLUMNS = (
    "security_id",
    "found_date",
    "listing_date",
    "issue_price",
    "total_issue_num",
    "par_value",
    "issue_way",
    "document_id",
    "collected_at",
)

FLOAT_HOLDERS_COLUMNS = (
    "security_id",
    "as_of",
    "rank",
    "holder_name",
    "holder_type",
    "shares",
    "pct_float",
    "share_class",
    "change_shares",
    "change_pct",
    "document_id",
    "collected_at",
)

INSTITUTIONAL_HOLDINGS_COLUMNS = (
    "security_id",
    "as_of",
    "org_type",
    "org_count",
    "total_free_shares",
    "pct_float",
    "pct_total",
    "document_id",
    "collected_at",
)

EXEC_HOLDING_CHANGES_COLUMNS = (
    "security_id",
    "as_of",
    "person_name",
    "position",
    "change_shares",
    "avg_price",
    "shares_after",
    "trade_way",
    "holder_name",
    "document_id",
    "collected_at",
)

# Profit waterfall order (display). gross_profit may be derived at read time.
INCOME_ITEM_CODES = (
    "revenue",
    "operating_cost",
    "gross_profit",
    "tax_surcharge",
    "selling_exp",
    "admin_exp",
    "rd_exp",
    "finance_exp",
    "other_income",
    "invest_income",
    "fv_change",
    "credit_impairment",
    "asset_impairment",
    "asset_disposal",
    "operating_profit",
    "non_operating_income",
    "non_operating_expense",
    "profit_before_tax",
    "income_tax",
    "net_profit",
    "net_profit_parent",
    "net_profit_minority",
)

INCOME_SIDE_CODES = ("net_profit_parent_ex_nonrecurring",)

BALANCE_ITEM_CODES = (
    "cash",
    "trading_assets",
    "notes_receivable",
    "accounts_receivable",
    "receivables_financing",
    "prepayments",
    "inventory",
    "contract_assets",
    "other_current_assets",
    "long_term_equity",
    "fixed_assets",
    "cip",
    "intangible",
    "goodwill",
    "deferred_tax_assets",
    "total_assets",
    "short_term_borrowings",
    "notes_payable",
    "accounts_payable",
    "contract_liabilities",
    "long_term_borrowings",
    "bonds_payable",
    "lease_liabilities",
    "total_liabilities",
    "equity_parent",
    "equity_minority",
    "total_equity",
)

CASHFLOW_ITEM_CODES = (
    "cash_from_sales",
    "cfo",
    "cfi",
    "cff",
    "capex_cash",
    "cash_end",
    "dividends_paid",
    "buyback_cash",
)

EXCHANGE_TO_TICKER_SUFFIX = {
    "SSE": "SH",
    "SZSE": "SZ",
    "BSE": "BJ",
}


def security_id(exchange: str, code: str) -> str:
    ex = str(exchange or "").strip().upper()
    cd = str(code or "").strip()
    if not ex or not cd:
        raise ValueError("exchange and code are required")
    return f"{ex}:{cd}"


def to_tradecraft_symbol(security_id_value: str) -> str | None:
    """Map SSE:600519 → 600519.SH. Unknown exchange → None."""
    raw = str(security_id_value or "").strip().upper()
    if ":" not in raw:
        return None
    exchange, code = raw.split(":", 1)
    suffix = EXCHANGE_TO_TICKER_SUFFIX.get(exchange)
    if not suffix or not code:
        return None
    return f"{code}.{suffix}"


def _row(columns: tuple[str, ...], **fields: Any) -> dict[str, Any]:
    return {key: fields.get(key, "") for key in columns}


def identity_row(**fields: Any) -> dict[str, Any]:
    return _row(IDENTITY_COLUMNS, **fields)


def facts_row(**fields: Any) -> dict[str, Any]:
    return _row(FACTS_COLUMNS, **fields)


def segments_row(**fields: Any) -> dict[str, Any]:
    return _row(SEGMENTS_COLUMNS, **fields)


def capital_row(**fields: Any) -> dict[str, Any]:
    return _row(CAPITAL_COLUMNS, **fields)


def holders_row(**fields: Any) -> dict[str, Any]:
    return _row(HOLDERS_COLUMNS, **fields)


def subsidiaries_row(**fields: Any) -> dict[str, Any]:
    return _row(SUBSIDIARIES_COLUMNS, **fields)


def listed_control_row(**fields: Any) -> dict[str, Any]:
    return _row(LISTED_CONTROL_COLUMNS, **fields)


def executives_row(**fields: Any) -> dict[str, Any]:
    return _row(EXECUTIVES_COLUMNS, **fields)


def dividends_row(**fields: Any) -> dict[str, Any]:
    return _row(DIVIDENDS_COLUMNS, **fields)


def workforce_row(**fields: Any) -> dict[str, Any]:
    return _row(WORKFORCE_COLUMNS, **fields)


def workforce_education_row(**fields: Any) -> dict[str, Any]:
    return _row(WORKFORCE_EDUCATION_COLUMNS, **fields)


def holder_stats_row(**fields: Any) -> dict[str, Any]:
    return _row(HOLDER_STATS_COLUMNS, **fields)


def ipo_profile_row(**fields: Any) -> dict[str, Any]:
    return _row(IPO_PROFILE_COLUMNS, **fields)


def float_holders_row(**fields: Any) -> dict[str, Any]:
    return _row(FLOAT_HOLDERS_COLUMNS, **fields)


def institutional_holding_row(**fields: Any) -> dict[str, Any]:
    return _row(INSTITUTIONAL_HOLDINGS_COLUMNS, **fields)


def exec_holding_change_row(**fields: Any) -> dict[str, Any]:
    return _row(EXEC_HOLDING_CHANGES_COLUMNS, **fields)
