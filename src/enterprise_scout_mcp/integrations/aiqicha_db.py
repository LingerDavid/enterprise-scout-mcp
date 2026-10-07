"""Read-through bridge to aiqicha_scraper SQLite (search-before-network)."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def lookup_company(keyword: str, db_path: Path) -> dict[str, Any] | None:
    if not db_path.is_file():
        return None
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT aiqicha_id, company_name, former_name
            FROM companies
            WHERE company_name = ? OR former_name = ?
            LIMIT 1
            """,
            (keyword, keyword),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "aiqicha_id": row[0],
            "company_name": row[1],
            "former_name": row[2] or "",
            "source": "aiqicha_scraper_db",
        }
    finally:
        conn.close()
