"""
Peer Percentile Rankings — Sprint 3 · Day 18

Loads peer_groups.xlsx and computes PERCENT_RANK for 10 metrics within each
of 11 peer groups.

Outputs:
  1. CSV with one row per (company_id, peer_group) containing:
       - company_id, peer_group_name, is_benchmark
       - Raw metric values
       - Percentile rank (0–100) for each metric within its peer group
       - Average percentile rank across all available metrics
  2. SQLite table `peer_percentiles` with rows:
       (company_id, peer_group_name, metric, value, percentile_rank, year)

For D/E (lower is better), the percentile rank is inverted so that
a lower D/E maps to a higher percentile.
"""

from __future__ import annotations

import logging
import math
import sqlite3
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "supporting"
DB_PATH = ROOT / "nifty100.db"
OUTPUT_DIR = ROOT / "output"

logger = logging.getLogger(__name__)

# ── 10 metrics — (column_name, display_label, higher_is_better) ──
# ROCE is loaded separately from companies.roce_percentage
METRICS: list[tuple[str, str, bool]] = [
    ("return_on_equity_pct",     "ROE",                True),   # higher is better
    ("roce_pct",                 "ROCE",               True),   # from companies table
    ("net_profit_margin_pct",    "Net Profit Margin",  True),
    ("debt_to_equity",           "D/E",                False),  # lower is better
    ("free_cash_flow_cr",        "FCF",                True),
    ("pat_cagr_5yr",             "PAT CAGR 5yr",       True),
    ("revenue_cagr_5yr",         "Revenue CAGR 5yr",   True),
    ("eps_cagr_5yr",             "EPS CAGR 5yr",       True),
    ("interest_coverage",        "Interest Coverage",  True),
    ("asset_turnover",           "Asset Turnover",      True),
]

# Column name used in financial_ratios for each metric (may differ from METRICS key)
METRIC_SOURCE_COLUMNS: dict[str, str] = {
    "return_on_equity_pct":    "return_on_equity_pct",
    "roce_pct":                "roce_pct",            # merged from companies table
    "net_profit_margin_pct":   "net_profit_margin_pct",
    "debt_to_equity":          "debt_to_equity",
    "free_cash_flow_cr":       "free_cash_flow_cr",
    "pat_cagr_5yr":            "pat_cagr_5yr",
    "revenue_cagr_5yr":        "revenue_cagr_5yr",
    "eps_cagr_5yr":            "eps_cagr_5yr",
    "interest_coverage":       "interest_coverage",
    "asset_turnover":          "asset_turnover",
}


def _safe_float(x):
    if x is None:
        return None
    try:
        return float(x)
    except (ValueError, TypeError):
        return None


def _percent_rank(value: float | None, series: list[float | None]) -> float | None:
    """Compute percentile rank of `value` within `series`.

    Uses the same formula as ratio_engine.sector_percentile_score:
        rank = (count_less / (n - 1)) * 100

    Returns 50.0 for single-element series, None for None/NaN inputs.
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    clean = [v for v in series if v is not None and not (isinstance(v, float) and math.isnan(v))]
    if not clean:
        return None
    v = float(value)
    n = len(clean)
    if n <= 1:
        return 50.0
    count_less = sum(1 for x in clean if x < v)
    rank = (count_less / (n - 1)) * 100.0
    return round(max(0.0, min(100.0, rank)), 2)


def load_peer_groups(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Load peer_groups.xlsx and return as a DataFrame."""
    path = data_dir / "peer_groups.xlsx"
    if not path.exists():
        raise FileNotFoundError(f"Peer groups file not found: {path}")
    df = pd.read_excel(path)
    df["is_benchmark"] = df["is_benchmark"].astype(bool)
    return df


def load_financial_ratios(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Load latest-year financial ratios for all companies.

    Merges ROCE from the companies table since financial_ratios does not
    have a roce_percentage column.
    """
    conn = sqlite3.connect(str(db_path))

    # Columns available in financial_ratios (excludes roce_pct)
    fr_metric_cols = [
        "return_on_equity_pct",
        "net_profit_margin_pct",
        "debt_to_equity",
        "interest_coverage",
        "asset_turnover",
        "free_cash_flow_cr",
        "revenue_cagr_5yr",
        "pat_cagr_5yr",
        "eps_cagr_5yr",
    ]
    fr_cols = ["company_id", "year"] + fr_metric_cols

    query = f"""
        SELECT {', '.join(fr_cols)}
        FROM financial_ratios
        WHERE year = (
            SELECT MAX(year) FROM financial_ratios fr2
            WHERE fr2.company_id = financial_ratios.company_id
        )
    """
    df = pd.read_sql_query(query, conn)

    # Load ROCE from companies table
    roce_df = pd.read_sql_query(
        "SELECT company_id, roce_percentage FROM companies",
        conn,
    )
    conn.close()

    # Merge ROCE into the ratios DataFrame
    roce_map = dict(
        zip(roce_df["company_id"], roce_df["roce_percentage"], strict=False)
    )
    df["roce_pct"] = df["company_id"].map(roce_map)

    # Convert numeric columns
    all_metric_cols = [m[0] for m in METRICS]
    for col in all_metric_cols:
        if col in df.columns:
            df[col] = df[col].apply(_safe_float)

    return df


def compute_peer_percentile_rankings(
    pg_df: pd.DataFrame,
    ratios_df: pd.DataFrame,
) -> pd.DataFrame:
    """Compute PERCENT_RANK for each metric within each peer group.

    Parameters
    ----------
    pg_df : DataFrame
        Peer groups table with columns: peer_group_name, company_id, is_benchmark.
    ratios_df : DataFrame
        Financial ratios table with at least the metric columns + company_id.

    Returns
    -------
    DataFrame with rows (company_id, peer_group_name, is_benchmark, metric ranks…)
    """
    rows: list[dict] = []

    # Group peer groups
    peer_groups = pg_df.groupby("peer_group_name")

    for group_name, group_df in peer_groups:
        group_companies = group_df["company_id"].tolist()

        # Filter ratios to this peer group
        group_ratios = ratios_df[ratios_df["company_id"].isin(group_companies)].copy()

        if group_ratios.empty:
            continue

        # Build a lookup: company_id → is_benchmark
        benchmark_map = dict(
            zip(
                group_df["company_id"],
                group_df["is_benchmark"],
                strict=False,
            )
        )

        for _, row in group_ratios.iterrows():
            cid = row["company_id"]
            out_row: dict = {
                "company_id": cid,
                "peer_group_name": group_name,
                "is_benchmark": benchmark_map.get(cid, False),
            }

            rank_values: list[float] = []

            for col, label, higher_is_better in METRICS:
                raw_val = row.get(col)
                out_row[f"{label} (raw)"] = raw_val

                # Get all peer group values for this metric
                pg_values = group_ratios[col].tolist()
                rank = _percent_rank(raw_val, pg_values)

                # Invert for lower-is-better metrics
                if rank is not None and not higher_is_better:
                    rank = round(100.0 - rank, 2)

                out_row[f"{label} (pctl)"] = rank

                if rank is not None:
                    rank_values.append(rank)

            # Average percentile rank across all available metrics
            out_row["avg_percentile_rank"] = (
                round(sum(rank_values) / len(rank_values), 2) if rank_values else None
            )

            rows.append(out_row)

    return pd.DataFrame(rows)


def load_all_companies(db_path: Path = DB_PATH) -> set[str]:
    """Load all company IDs from the companies table."""
    conn = sqlite3.connect(str(db_path))
    cids = {r[0] for r in conn.execute("SELECT company_id FROM companies").fetchall()}
    conn.close()
    return cids


def populate_peer_percentiles_table(
    result_df: pd.DataFrame,
    ratios_df: pd.DataFrame,
    pg_df: pd.DataFrame,
    db_path: Path = DB_PATH,
) -> int:
    """Populate the peer_percentiles SQLite table with per-metric percentile rows.

    Columns: company_id, peer_group_name, metric, value, percentile_rank, year

    Returns the number of rows inserted.
    """
    conn = sqlite3.connect(str(db_path))

    # Create table if not exists
    conn.execute("""
        CREATE TABLE IF NOT EXISTS peer_percentiles (
            id              INTEGER PRIMARY KEY,
            company_id      TEXT NOT NULL,
            peer_group_name TEXT NOT NULL,
            metric          TEXT NOT NULL,
            value           REAL,
            percentile_rank REAL,
            year            INTEGER NOT NULL,
            FOREIGN KEY (company_id) REFERENCES companies(company_id)
        )
    """)

    # Clear existing data
    conn.execute("DELETE FROM peer_percentiles")

    # Build a company_id -> year mapping from ratios_df
    year_map: dict[str, int] = {}
    for _, row in ratios_df.iterrows():
        year_map[row["company_id"]] = row["year"]

    insert_sql = """
        INSERT INTO peer_percentiles (company_id, peer_group_name, metric, value, percentile_rank, year)
        VALUES (?, ?, ?, ?, ?, ?)
    """

    rows_inserted = 0
    for _, row in result_df.iterrows():
        cid = row["company_id"]
        group_name = row["peer_group_name"]
        year = year_map.get(cid)

        for col, label, higher_is_better in METRICS:
            raw_val = row.get(f"{label} (raw)")
            pctl_rank = row.get(f"{label} (pctl)")

            conn.execute(insert_sql, (
                cid,
                group_name,
                label,
                raw_val,
                pctl_rank,
                year,
            ))
            rows_inserted += 1

    conn.commit()
    conn.close()

    print(f"  → Populated peer_percentiles table with {rows_inserted} rows")
    return rows_inserted


def export_peer_percentile_rankings(
    db_path: Path = DB_PATH,
    data_dir: Path = DATA_DIR,
    out_dir: Path = OUTPUT_DIR,
) -> Path:
    """Main entry point: load data, compute ranks, export CSV.

    Returns the path to the written CSV file.
    """
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "peer_percentile_rankings.csv"

    print("Loading peer groups...")
    pg_df = load_peer_groups(data_dir)
    print(f"  → {len(pg_df)} rows, {pg_df['peer_group_name'].nunique()} peer groups")

    print("Loading financial ratios (latest year)...")
    ratios_df = load_financial_ratios(db_path)
    print(f"  → {len(ratios_df)} companies")

    # Identify companies not in any peer group
    all_companies = load_all_companies(db_path)
    peer_group_companies = set(pg_df["company_id"].unique())
    unassigned = sorted(all_companies - peer_group_companies)
    if unassigned:
        print(f"\n  Companies without peer group assignment ({len(unassigned)}):")
        for cid in unassigned:
            print(f"    No peer group assigned — {cid}")
    else:
        print("  All companies have peer group assignments.")

    print("\nComputing peer percentile rankings...")
    result_df = compute_peer_percentile_rankings(pg_df, ratios_df)
    result_df = result_df.sort_values(
        ["peer_group_name", "avg_percentile_rank"],
        ascending=[True, False],
        na_position="last",
    )

    result_df.to_csv(out_path, index=False, float_format="%.2f")
    print(f"Exported {len(result_df)} rows to {out_path}")

    # Populate SQLite peer_percentiles table
    print("\nPopulating peer_percentiles table in SQLite...")
    populate_peer_percentiles_table(result_df, ratios_df, pg_df, db_path)

    # Summary
    print("\n=== Summary ===")
    for group_name, group_df in result_df.groupby("peer_group_name"):
        n = len(group_df)
        avg_rank = group_df["avg_percentile_rank"].mean()
        print(f"  {group_name:25s}  {n:2d} companies  avg rank: {avg_rank:.1f}")

    return out_path


if __name__ == "__main__":
    export_peer_percentile_rankings()

