"""Sprint 4 · Day 22 — Financial Ratios Year Cleanup Migration

Removes stale duplicate rows from `financial_ratios` caused by mixed-type
year columns:

  - The source `financial_ratios.xlsx` stores years as text, e.g. 'Mar 2024'.
  - `financial_ratios_populator.py` re-inserts the SAME fiscal year as an
    integer (2024) with fully computed metrics (composite_quality_score,
    CAGR columns, etc.).
  - Because `'Mar 2024' != 2024`, the `INSERT OR REPLACE` on the
    (company_id, year) unique key does NOT deduplicate — both rows coexist,
    so the table has 2092 rows but only 1141 distinct (company, fiscal-year)
    pairs.

This migration deletes the text-year rows (which lack composite/CAGR
columns) and keeps the integer-year rows that carry the full computed
metric set. After the cleanup, all downstream queries (dashboard, screener,
peer analysis, valuation) operate on a single row per (company, fiscal year).

Usage:
    python -m src.etl.clean_financial_ratios_years
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "nifty100.db"


def clean_financial_ratios_years(db_path: Path = DB_PATH) -> dict[str, int]:
    """Remove text-year rows from financial_ratios.

    Returns a summary dict with:
      - total_before: rows in table before cleanup
      - text_rows_deleted: number of text-year rows removed
      - total_after: rows remaining
      - distinct_pairs_after: distinct (company_id, fiscal_year) pairs after cleanup
      - companies_covered: distinct companies with at least one row after cleanup
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    total_before = cur.execute("SELECT COUNT(*) FROM financial_ratios").fetchone()[0]

    cur.execute("DELETE FROM financial_ratios WHERE typeof(year) != 'integer'")
    text_rows_deleted = cur.rowcount

    total_after = cur.execute("SELECT COUNT(*) FROM financial_ratios").fetchone()[0]
    distinct_pairs_after = cur.execute(
        "SELECT COUNT(*) FROM (SELECT DISTINCT company_id, year FROM financial_ratios)"
    ).fetchone()[0]
    companies_covered = cur.execute(
        "SELECT COUNT(DISTINCT company_id) FROM financial_ratios"
    ).fetchone()[0]

    conn.commit()
    conn.close()

    return {
        "total_before": total_before,
        "text_rows_deleted": text_rows_deleted,
        "total_after": total_after,
        "distinct_pairs_after": distinct_pairs_after,
        "companies_covered": companies_covered,
    }


def report_financial_ratios_years(db_path: Path = DB_PATH) -> None:
    """Print a per-year coverage summary after cleanup."""
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    print("\n=== financial_ratios year coverage (post-cleanup) ===")
    rows = cur.execute(
        """
        SELECT year, COUNT(DISTINCT company_id)
        FROM financial_ratios
        GROUP BY year
        ORDER BY year
        """
    ).fetchall()
    for year, count in rows:
        print(f"  {year}: {count} companies")

    print("\n=== companies WITHOUT financial_ratios ===")
    missing = cur.execute(
        """
        SELECT c.company_id FROM companies c
        WHERE NOT EXISTS (SELECT 1 FROM financial_ratios fr WHERE fr.company_id = c.company_id)
        ORDER BY c.company_id
        """
    ).fetchall()
    print(f"  count: {len(missing)}")
    for (cid,) in missing:
        print(f"  - {cid}")
    conn.close()


if __name__ == "__main__":
    summary = clean_financial_ratios_years()
    for key, value in summary.items():
        print(f"{key}: {value}")
    report_financial_ratios_years()

