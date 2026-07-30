"""
Day 20 — Peer Comparison Excel Report

Generates output/peer_comparison.xlsx with 11 sheets — one per peer group.

Each sheet columns:
    company_id, company_name, + 20 metric columns (raw values), + 20 percentile rank columns

Features:
  - Colour-code percentile rank cells:
      Green  fill (C6EFCE)  for >= 75th percentile
      Yellow fill (FFEB9C)  for 25th to 75th percentile
      Red    fill (FFC7CE)  for <= 25th percentile
  - Benchmark company row highlighted with gold/amber background
  - Summary row at bottom showing peer group median for each raw metric
"""

from __future__ import annotations

import logging
import math
import sqlite3
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import (
    Alignment,
    Border,
    Font,
    PatternFill,
    Side,
)
from openpyxl.utils import get_column_letter

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "nifty100.db"
OUTPUT_PATH = ROOT / "output" / "peer_comparison.xlsx"

# ====================================================================
# 20-Metric Definition
# ====================================================================
# Each tuple: (key, label, source, column_in_source, higher_is_better)
# source: 'fr' = financial_ratios, 'companies' = companies table,
#         'mcap' = market_cap table

METRICS_20: list[tuple[str, str, str, str, bool]] = [
    # Profitability
    ("return_on_equity_pct",      "ROE (%)",                "fr",       "return_on_equity_pct",           True),
    ("roce_pct",                  "ROCE (%)",               "companies", "roce_percentage",                True),
    ("net_profit_margin_pct",     "Net Profit Margin (%)",  "fr",       "net_profit_margin_pct",          True),
    ("operating_profit_margin_pct", "Operating Profit Margin (%)", "fr", "operating_profit_margin_pct",    True),

    # Leverage / Coverage
    ("debt_to_equity",            "Debt-to-Equity",         "fr",       "debt_to_equity",                 False),
    ("interest_coverage",         "Interest Coverage Ratio","fr",       "interest_coverage",              True),

    # Efficiency
    ("asset_turnover",            "Asset Turnover",         "fr",       "asset_turnover",                 True),

    # Cash Flow
    ("free_cash_flow_cr",         "FCF (₹ Cr)",             "fr",       "free_cash_flow_cr",              True),
    ("fcf_conversion_rate_pct",   "FCF Conversion Rate (%)","fr",       "fcf_conversion_rate_pct",        True),
    ("cash_from_operations_cr",   "Cash from Ops (₹ Cr)",   "fr",       "cash_from_operations_cr",        True),

    # Growth
    ("revenue_cagr_5yr",          "Revenue CAGR 5yr (%)",   "fr",       "revenue_cagr_5yr",               True),
    ("pat_cagr_5yr",              "PAT CAGR 5yr (%)",       "fr",       "pat_cagr_5yr",                   True),
    ("eps_cagr_5yr",              "EPS CAGR 5yr (%)",       "fr",       "eps_cagr_5yr",                   True),
    ("revenue_cagr_3yr",          "Revenue CAGR 3yr (%)",   "fr",       "revenue_cagr_3yr",               True),

    # Per-Share
    ("earnings_per_share",        "EPS (₹)",                "fr",       "earnings_per_share",              True),
    ("book_value_per_share",      "Book Value per Share (₹)","fr",      "book_value_per_share",            True),

    # Dividend
    ("dividend_payout_ratio_pct", "Dividend Payout Ratio (%)","fr",     "dividend_payout_ratio_pct",       True),

    # Composite
    ("composite_quality_score",   "Composite Quality Score", "fr",      "composite_quality_score",         True),

    # Market Data (from market_cap table)
    ("pe_ratio",                  "P/E Ratio",              "mcap",     "pe_ratio",                       False),
    ("market_cap_crore",          "Market Cap (₹ Cr)",      "mcap",     "market_cap_crore",                True),
]

# ====================================================================
# Helpers
# ====================================================================

def _safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        return float(x)
    except (ValueError, TypeError):
        return None


def _percent_rank(value: float | None, series: list[float | None]) -> float | None:
    """Compute percentile rank of `value` within `series` (0-100).

    Uses formula: rank = (count_less / (n - 1)) * 100
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


def _extract_year(y: Any) -> int:
    """Extract numeric year from mixed-type year column."""
    if y is None:
        return 0
    s = str(y).strip()
    if len(s) >= 4:
        try:
            return int(s[-4:])
        except ValueError:
            pass
    try:
        return int(s)
    except ValueError:
        return 0


# ====================================================================
# Data Loading
# ====================================================================

def load_all_data(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Load all data needed for peer comparison.

    Returns a single DataFrame with one row per company containing:
      - company_id, company_name, peer_group_name, is_benchmark
      - All 20 metric columns (raw values)
    """
    conn = sqlite3.connect(str(db_path))

    # --- 1. Load financial_ratios (latest year per company) ---
    fr_cols = [
        "company_id", "year",
        "net_profit_margin_pct", "operating_profit_margin_pct",
        "return_on_equity_pct", "debt_to_equity",
        "interest_coverage", "asset_turnover",
        "free_cash_flow_cr", "fcf_conversion_rate_pct",
        "cash_from_operations_cr",
        "revenue_cagr_5yr", "pat_cagr_5yr", "eps_cagr_5yr",
        "revenue_cagr_3yr",
        "earnings_per_share", "book_value_per_share",
        "dividend_payout_ratio_pct",
        "composite_quality_score",
    ]
    fr_cols_str = ", ".join(fr_cols)
    fr_df = pd.read_sql_query(
        f"SELECT {fr_cols_str} FROM financial_ratios", conn
    )

    # Deduplicate to latest year per company using extracted year
    fr_df["_year_num"] = fr_df["year"].apply(_extract_year)
    fr_df = fr_df.sort_values(["company_id", "_year_num"], ascending=[True, False])
    fr_df = fr_df.groupby("company_id", as_index=False).first()
    fr_df.drop(columns=["_year_num"], inplace=True)

    # --- 2. Load company names + ROCE ---
    companies_df = pd.read_sql_query(
        "SELECT company_id, company_name, roce_percentage FROM companies", conn
    )

    # --- 3. Load market_cap data (latest year per company) ---
    mcap_df = pd.read_sql_query(
        "SELECT company_id, year, market_cap_crore, pe_ratio FROM market_cap", conn
    )
    mcap_df["_year_num"] = mcap_df["year"].apply(_extract_year)
    mcap_df = mcap_df.sort_values(["company_id", "_year_num"], ascending=[True, False])
    mcap_df = mcap_df.groupby("company_id", as_index=False).first()
    mcap_df.drop(columns=["year", "_year_num"], inplace=True)

    conn.close()

    # --- 4. Merge all data ---
    # Start with financial_ratios
    df = fr_df.copy()

    # Merge company name + ROCE
    df = df.merge(companies_df, on="company_id", how="left")

    # Merge market_cap
    df = df.merge(mcap_df, on="company_id", how="left")

    # --- 5. Load peer group assignments ---
    pg_conn = sqlite3.connect(str(db_path))
    pg_df = pd.read_sql_query(
        "SELECT company_id, peer_group_name, is_benchmark FROM peer_groups",
        pg_conn,
    )
    pg_conn.close()
    if pg_df.empty:
        pg_df = pd.DataFrame(columns=["company_id", "peer_group_name", "is_benchmark"])

    # Merge peer group info
    df = df.merge(
        pg_df[["company_id", "peer_group_name", "is_benchmark"]],
        on="company_id",
        how="left",
    )
    df["is_benchmark"] = df["is_benchmark"].fillna(False).astype(bool)

    # --- 6. Ensure all metric columns exist and are numeric ---
    for _key, _label, source, col, _hib in METRICS_20:
        if source == "fr":
            db_col = col
        elif source == "companies":
            db_col = col  # roce_percentage
        elif source == "mcap":
            db_col = col  # pe_ratio, market_cap_crore
        else:
            continue

        if db_col not in df.columns:
            df[db_col] = None
        else:
            df[db_col] = df[db_col].apply(_safe_float)

    return df


# ====================================================================
# Percentile computation per peer group
# ====================================================================

def compute_group_percentiles(
    group_df: pd.DataFrame,
    metrics: list[tuple[str, str, str, str, bool]] = METRICS_20,
) -> pd.DataFrame:
    """For each metric in the group, compute percentile rank within the group.

    The input `group_df` must contain rows for a single peer group.
    Modifies the DataFrame in-place adding ``{key}_pctl`` columns.
    """
    result = group_df.copy()

    for key, label, source, col, higher_is_better in metrics:
        # Get the actual column name in the DataFrame
        if source == "companies" and col == "roce_percentage":
            db_col = "roce_percentage"
        elif source == "mcap":
            db_col = col
        else:
            db_col = col

        if db_col not in result.columns:
            result[f"{key}_pctl"] = None
            continue

        # Get all values in this group for the metric
        group_values = result[db_col].tolist()
        raw_col = f"{key}_raw"

        # Copy raw value to a named column for clarity
        result[raw_col] = result[db_col]

        # Compute percentile rank for each company
        pctl_values: list[float | None] = []
        for _, row in result.iterrows():
            raw_val = row.get(db_col)
            rank = _percent_rank(raw_val, group_values)

            # Invert for lower-is-better metrics
            if rank is not None and not higher_is_better:
                rank = round(100.0 - rank, 2)

            pctl_values.append(rank)

        result[f"{key}_pctl"] = pctl_values

    return result


# ====================================================================
# XLSX Formatting Constants
# ====================================================================

GREEN_FILL = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
YELLOW_FILL = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
RED_FILL = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
GOLD_FILL = PatternFill(start_color="FFD700", end_color="FFD700", fill_type="solid")
AMBER_BENCHMARK_FILL = PatternFill(start_color="F4B183", end_color="F4B183", fill_type="solid")
SUMMARY_FILL = PatternFill(start_color="D9E2F3", end_color="D9E2F3", fill_type="solid")

HEADER_FILL = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True, size=10)
HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center", wrap_text=True)
BENCHMARK_FONT = Font(bold=True, italic=False, size=10)
SUMMARY_FONT = Font(bold=True, italic=True, size=10)
SUMMARY_HEADER_FONT = Font(bold=True, italic=True, size=10, color="1F3864")

THIN_BORDER = Border(
    left=Side(style="thin"),
    right=Side(style="thin"),
    top=Side(style="thin"),
    bottom=Side(style="thin"),
)

# Percentile thresholds
PCTL_HIGH = 75.0   # >= 75 → green
PCTL_MID_LOW = 25.0  # <= 25 → red


def _get_pctl_fill(pctl_value: Any) -> PatternFill:
    """Return the appropriate fill for a percentile value."""
    if pctl_value is None:
        return PatternFill()  # no fill
    if not isinstance(pctl_value, (int, float)):
        return PatternFill()
    v = float(pctl_value)
    if math.isnan(v):
        return PatternFill()
    if v >= PCTL_HIGH:
        return GREEN_FILL
    if v <= PCTL_MID_LOW:
        return RED_FILL
    return YELLOW_FILL


# ====================================================================
# Sheet Writing
# ====================================================================

# Column layout: company_id | company_name | k1_raw | k1_pctl | k2_raw | k2_pctl | ...
# That's 2 + 20*2 = 42 columns

BASE_COLUMNS = ["company_id", "company_name"]


def _build_column_defs() -> list[tuple[str, str, bool]]:
    """Build column definitions for the output sheet.

    Returns list of (column_key, display_label, is_percentile) tuples.
    """
    cols: list[tuple[str, str, bool]] = [
        ("company_id", "Company ID", False),
        ("company_name", "Company Name", False),
    ]
    for key, label, _source, _col, _hib in METRICS_20:
        short_label = label[:25]  # keep headers readable
        cols.append((f"{key}_raw", short_label, False))
        cols.append((f"{key}_pctl", f"{short_label} (Pctl)", True))
    return cols


def write_peer_sheet(
    wb: Workbook,
    sheet_name: str,
    group_df: pd.DataFrame,
    df_with_pctls: pd.DataFrame,
) -> None:
    """Write a single peer group sheet with all formatting.

    Parameters
    ----------
    wb : Workbook
        The openpyxl Workbook to add the sheet to.
    sheet_name : str
        Name of the sheet (max 31 chars).
    group_df : pd.DataFrame
        The raw group data (source DataFrame).
    df_with_pctls : pd.DataFrame
        The group data with percentile columns computed.
    """
    ws = wb.create_sheet(title=sheet_name[:31])

    column_defs = _build_column_defs()
    num_cols = len(column_defs)

    # Determine order: sorted by average percentile rank descending
    pctl_cols = [f"{m[0]}_pctl" for m in METRICS_20]
    available_pctls = [c for c in pctl_cols if c in df_with_pctls.columns]

    if available_pctls:
        df_with_pctls["_avg_pctl"] = df_with_pctls[available_pctls].mean(axis=1, skipna=True)
        df_with_pctls = df_with_pctls.sort_values("_avg_pctl", ascending=False, na_position="last")
    else:
        df_with_pctls = df_with_pctls.copy()

    # --- Write Header Row ---
    for col_idx, (ckey, label, is_pctl) in enumerate(column_defs, start=1):
        cell = ws.cell(row=1, column=col_idx, value=label)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = HEADER_ALIGNMENT
        cell.border = THIN_BORDER

    # --- Write Data Rows ---
    row_idx = 2
    for _, row in df_with_pctls.iterrows():
        cid = row.get("company_id", "")
        is_benchmark = bool(row.get("is_benchmark", False))

        for col_idx, (ckey, _label, is_pctl) in enumerate(column_defs, start=1):
            if ckey == "company_id":
                value = cid
            elif ckey == "company_name":
                value = row.get("company_name", "")
            else:
                # Determine which column in the source data holds this value
                value = row.get(ckey)

            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.border = THIN_BORDER

            # Format numbers
            if isinstance(value, float):
                cell.number_format = "#,##0.00"

            # Benchmark row highlight
            if is_benchmark:
                cell.fill = AMBER_BENCHMARK_FILL
                cell.font = BENCHMARK_FONT

            # Colour-code percentile cells
            if is_pctl and not is_benchmark:
                pctl_fill = _get_pctl_fill(value)
                if pctl_fill is not None and pctl_fill.start_color and pctl_fill.start_color.rgb:
                    cell.fill = pctl_fill

            # Alignment
            if col_idx <= 2:
                cell.alignment = Alignment(horizontal="left")
            else:
                cell.alignment = Alignment(horizontal="right")

        row_idx += 1

    # --- Write Summary Row (peer group median) ---
    summary_row = row_idx
    median_values: dict[str, Any] = {}

    for ckey, _label, is_pctl in column_defs:
        if ckey == "company_id":
            median_values[ckey] = "Peer Group Median"
        elif ckey == "company_name":
            median_values[ckey] = ""
        else:
            # Compute median of raw values across the peer group
            raw_values = df_with_pctls[ckey].dropna().tolist()
            if raw_values and not is_pctl:
                median_values[ckey] = round(pd.Series(raw_values).median(), 2)
            elif is_pctl:
                # For percentile columns, compute median percentile too
                pctl_vals = df_with_pctls[ckey].dropna().tolist()
                if pctl_vals:
                    median_values[ckey] = round(pd.Series(pctl_vals).median(), 2)
                else:
                    median_values[ckey] = None
            else:
                median_values[ckey] = None

    for col_idx, (ckey, _label, _is_pctl) in enumerate(column_defs, start=1):
        value = median_values.get(ckey)
        cell = ws.cell(row=summary_row, column=col_idx, value=value)
        cell.fill = SUMMARY_FILL
        cell.font = SUMMARY_FONT
        cell.border = THIN_BORDER
        if ckey == "company_id":
            cell.font = SUMMARY_HEADER_FONT
            cell.alignment = Alignment(horizontal="left")
        else:
            cell.alignment = Alignment(horizontal="right")
            if isinstance(value, float):
                cell.number_format = "#,##0.00"

    # --- Column Widths ---
    for col_idx in range(1, num_cols + 1):
        header_text = column_defs[col_idx - 1][1]
        max_len = len(str(header_text))

        # Sample data for width estimation
        for sample_row in range(2, min(summary_row, min(8, summary_row))):
            cell_val = ws.cell(row=sample_row, column=col_idx).value
            if cell_val is not None:
                val_str = f"{cell_val:.2f}" if isinstance(cell_val, float) else str(cell_val)
                max_len = max(max_len, len(val_str))

        # Cap widths
        col_width = min(max_len + 3, 25)
        col_width = max(col_width, 12)
        ws.column_dimensions[get_column_letter(col_idx)].width = col_width

    # Freeze top row
    ws.freeze_panes = "A2"

    logger.info(
        f"  Sheet '{sheet_name[:31]}': {len(df_with_pctls)} companies, "
        f"{num_cols} columns, summary row at {summary_row}"
    )


# ====================================================================
# Main Export Function
# ====================================================================

def export_peer_comparison_xlsx(
    db_path: Path = DB_PATH,
    output_path: Path = OUTPUT_PATH,
) -> Path:
    """Generate output/peer_comparison.xlsx with 11 sheets — one per peer group.

    Returns the path to the generated file.
    """
    logger.info("=" * 60)
    logger.info("PEER COMPARISON XLSX EXPORTER")
    logger.info("=" * 60)

    output_path.parent.mkdir(exist_ok=True)

    # --- Load all data ---
    logger.info("Loading data from database...")
    df = load_all_data(db_path)
    logger.info(f"  Loaded {len(df)} companies with {len(df.columns)} columns")

    # --- Filter to companies with peer group assignments ---
    assigned = df[df["peer_group_name"].notna()].copy()
    logger.info(f"  Companies with peer group: {len(assigned)}")

    if assigned.empty:
        raise ValueError("No companies have peer group assignments — cannot generate report.")

    # --- Create Workbook ---
    wb = Workbook()
    # Remove default sheet
    default_sheet = wb.active
    if default_sheet is not None:
        wb.remove(default_sheet)

    # --- Process each peer group ---
    peer_groups = assigned["peer_group_name"].unique()
    logger.info(f"  Peer groups to process: {len(peer_groups)}")

    for group_name in sorted(peer_groups):
        logger.info(f"\n--- Peer Group: {group_name} ---")
        group_df = assigned[assigned["peer_group_name"] == group_name].copy()

        if group_df.empty:
            logger.warning(f"  WARNING: Group '{group_name}' has no data, skipping")
            continue

        logger.info(f"  Companies in group: {len(group_df)}")

        # Compute percentile ranks for all 20 metrics within this group
        group_with_pctls = compute_group_percentiles(group_df, METRICS_20)

        # Write sheet
        write_peer_sheet(wb, group_name, group_df, group_with_pctls)

    # --- Save Workbook ---
    logger.info(f"\nSaving to {output_path}...")
    wb.save(str(output_path))
    logger.info(f"✓ Successfully exported to {output_path}")

    # --- Print Summary ---
    print()
    print("=" * 60)
    print("  PEER COMPARISON XLSX GENERATED")
    print("=" * 60)
    print(f"  File: {output_path}")
    print(f"  Sheets: {len(wb.sheetnames)}")
    for name in wb.sheetnames:
        ws = wb[name]
        n_companies = ws.max_row - 2  # subtract header + summary rows
        n_cols = ws.max_column
        print(f"    • {name:30s}  {n_companies:2d} companies × {n_cols:2d} columns")
    print("=" * 60)

    return output_path


# ====================================================================
# CLI Entry Point
# ====================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    export_peer_comparison_xlsx()

