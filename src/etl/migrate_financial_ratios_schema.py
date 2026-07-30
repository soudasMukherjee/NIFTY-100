from __future__ import annotations

import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "nifty100.db"


def migrate_financial_ratios_schema(db_path: Path = DB_PATH) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    # Add missing columns to financial_ratios table (SQLite ALTER TABLE ADD COLUMN).
    # This avoids needing to rerun the Excel loader.
    required_cols: dict[str, str] = {
        # Day 12 additions requested
        "fcf_conversion_rate_pct": "REAL",
        "cash_from_operations_cr": "REAL",
        "revenue_cagr_5yr": "REAL",
        "pat_cagr_5yr": "REAL",
        "eps_cagr_5yr": "REAL",
        "composite_quality_score": "REAL",
        # Day 16 additions — 6 Preset Screeners
        "revenue_cagr_3yr": "REAL",
        "de_yoy_change_pct": "REAL",
        # Day 16 additions — Composite Score & Export
        "fcf_cagr_5yr": "REAL",
    }

    existing = {r[1] for r in conn.execute("PRAGMA table_info(financial_ratios)").fetchall()}

    for col, col_type in required_cols.items():
        if col in existing:
            continue
        conn.execute(f"ALTER TABLE financial_ratios ADD COLUMN {col} {col_type}")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    migrate_financial_ratios_schema()

