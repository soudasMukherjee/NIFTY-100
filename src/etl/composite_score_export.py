"""
Composite Quality Score Export — Sprint 3 · Day 16

Exports the composite quality score (0–100) with all sub-scores to a CSV file.
Follows the same pattern as capital_allocation_export.py.

Features:
  - P10/P90 Winsorisation: caps extreme values before scaling to 0-100
  - Sector-relative percentile scoring: normalises within each broad_sector
  - Both absolute (winsorised) and sector-relative composites are exported

The CSV contains:
  - company_id, year, broad_sector
  - Raw metric sub-scores (winsorised at P10/P90 then scored via thresholds)
  - Sector-percentile sub-scores (0-100 rank within sector peers)
  - Final composite_quality_score (based on winsorised absolute scores)
  - sector_relative_composite_score (based on sector percentile ranks)
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from src.analytics.ratio_engine import (
    _score_roe,
    _score_roce,
    _score_npm,
    _score_fcf_cagr,
    _score_cfo_pat_ratio,
    _score_fcf_positive,
    _score_revenue_cagr,
    _score_pat_cagr,
    _score_debt_to_equity,
    _score_interest_coverage,
    composite_quality_score_v2,
    winsorise_value,
    compute_winsorisation_bounds,
    sector_percentile_score,
    compute_sector_percentile_scores,
)


ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "nifty100.db"
OUTPUT_DIR = ROOT / "output"


def _safe_float(x):
    if x is None:
        return None
    try:
        return float(x)
    except Exception:
        return None


def _compute_roce_for_row(
    op: float | None, eq: float, rs: float, br: float
) -> float | None:
    if op is None:
        return None
    denom = float(eq) + float(rs) + float(br)
    if denom <= 0:
        return None
    return (float(op) / denom) * 100.0


def export_composite_scores_csv(db_path: Path = DB_PATH, out_dir: Path = OUTPUT_DIR) -> Path:
    """Export composite quality scores — absolute (winsorised) + sector-relative.

    Returns the path to the written CSV file.
    """
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "composite_scores.csv"

    conn = sqlite3.connect(db_path)

    # Load financial_ratios with latest year per company
    query = """
        SELECT
            company_id,
            year,
            return_on_equity_pct,
            debt_to_equity,
            interest_coverage,
            free_cash_flow_cr,
            revenue_cagr_5yr,
            pat_cagr_5yr,
            fcf_cagr_5yr,
            net_profit_margin_pct
        FROM financial_ratios
        WHERE year = (
            SELECT MAX(year) FROM financial_ratios fr2
            WHERE fr2.company_id = financial_ratios.company_id
        )
    """
    fr_df = pd.read_sql_query(query, conn)

    # Load sector info
    sectors_df = pd.read_sql_query(
        "SELECT company_id, broad_sector FROM sectors", conn
    )

    # Load P&L and BS for ROCE computation
    roce_df = pd.read_sql_query(
        """
        SELECT
            fr.company_id,
            fr.year,
            pl.operating_profit,
            bs.equity_capital,
            bs.reserves,
            bs.borrowings
        FROM financial_ratios fr
        LEFT JOIN profitandloss pl
            ON fr.company_id = pl.company_id
            AND CAST(fr.year AS INTEGER) = CAST(pl.year AS INTEGER)
            AND pl.period_type = 'ANNUAL'
        LEFT JOIN balancesheet bs
            ON fr.company_id = bs.company_id
            AND CAST(fr.year AS INTEGER) = CAST(bs.year AS INTEGER)
            AND bs.period_type = 'ANNUAL'
        """,
        conn,
    )
    conn.close()

    # --- Compute ROCE ---
    roce_map: dict[str, float | None] = {}
    for _, row in roce_df.iterrows():
        cid = row["company_id"]
        roce_val = _compute_roce_for_row(
            _safe_float(row.get("operating_profit")),
            _safe_float(row.get("equity_capital")) or 0,
            _safe_float(row.get("reserves")) or 0,
            _safe_float(row.get("borrowings")) or 0,
        )
        # Take first (latest) year per company
        if cid not in roce_map:
            roce_map[cid] = roce_val

    df = fr_df.copy()
    df["roce_pct"] = df["company_id"].map(roce_map)
    df = df.merge(sectors_df[["company_id", "broad_sector"]], on="company_id", how="left")
    df["broad_sector"] = df["broad_sector"].fillna("Unknown")

    # ================================================================
    # PART 1: P10/P90 Winsorisation + Absolute Scoring
    # ================================================================

    # Define the raw metrics we want to winsorise
    raw_metrics = {
        "return_on_equity_pct": True,   # higher is better
        "roce_pct": True,
        "net_profit_margin_pct": True,
        "fcf_cagr_5yr": True,
        "revenue_cagr_5yr": True,
        "pat_cagr_5yr": True,
        "debt_to_equity": False,  # lower is better
        "interest_coverage": True,
        "free_cash_flow_cr": True,
    }

    # Compute P10/P90 bounds for each metric across all companies
    bounds: dict[str, tuple[float | None, float | None]] = {}
    for metric in raw_metrics:
        values = df[metric].tolist()
        p10, p90 = compute_winsorisation_bounds(values)
        bounds[metric] = (p10, p90)

    # Create winsorised columns
    for metric in raw_metrics:
        p10, p90 = bounds[metric]
        winsorised_col = f"{metric}_winsorised"
        df[winsorised_col] = df[metric].apply(
            lambda v, p10=p10, p90=p90: winsorise_value(v, p10, p90)
        )

    # Score using winsorised values (absolute thresholds)
    df["roe_score_abs"] = df["return_on_equity_pct_winsorised"].apply(_score_roe)
    df["roce_score_abs"] = df["roce_pct_winsorised"].apply(_score_roce)
    df["npm_score_abs"] = df["net_profit_margin_pct_winsorised"].apply(_score_npm)
    df["fcf_cagr_score_abs"] = df["fcf_cagr_5yr_winsorised"].apply(_score_fcf_cagr)
    # CFO/PAT ratio not directly available — use None
    df["cfo_pat_ratio_score_abs"] = None
    df["fcf_positive_score_abs"] = df["free_cash_flow_cr_winsorised"].apply(_score_fcf_positive)
    df["revenue_cagr_score_abs"] = df["revenue_cagr_5yr_winsorised"].apply(_score_revenue_cagr)
    df["pat_cagr_score_abs"] = df["pat_cagr_5yr_winsorised"].apply(_score_pat_cagr)
    df["de_score_abs"] = df["debt_to_equity_winsorised"].apply(_score_debt_to_equity)
    df["icr_score_abs"] = df["interest_coverage_winsorised"].apply(_score_interest_coverage)

    # Compute absolute composite
    abs_composites = []
    for _, row in df.iterrows():
        cs = composite_quality_score_v2(
            roe_pct=row.get("return_on_equity_pct_winsorised"),
            roce_pct=row.get("roce_pct_winsorised"),
            npm_pct=row.get("net_profit_margin_pct_winsorised"),
            fcf_cagr_5yr=row.get("fcf_cagr_5yr_winsorised"),
            cfo_pat_ratio=None,
            fcf_value=row.get("free_cash_flow_cr_winsorised"),
            revenue_cagr_5yr=row.get("revenue_cagr_5yr_winsorised"),
            pat_cagr_5yr=row.get("pat_cagr_5yr_winsorised"),
            debt_to_equity=row.get("debt_to_equity_winsorised"),
            interest_coverage=row.get("interest_coverage_winsorised"),
        )
        abs_composites.append(cs)
    df["composite_quality_score"] = abs_composites

    # ================================================================
    # PART 2: Sector-Relative Percentile Scoring
    # ================================================================

    # Build sector map
    sector_map: dict[str, str] = dict(
        zip(df["company_id"], df["broad_sector"], strict=False)
    )

    # Compute sector-percentile scores for each raw metric
    sector_metrics = {
        "return_on_equity_pct": "roe_pctile",
        "roce_pct": "roce_pctile",
        "net_profit_margin_pct": "npm_pctile",
        "fcf_cagr_5yr": "fcf_cagr_pctile",
        "revenue_cagr_5yr": "revenue_cagr_pctile",
        "pat_cagr_5yr": "pat_cagr_pctile",
        "debt_to_equity": "de_pctile",     # lower is better — invert later
        "interest_coverage": "icr_pctile",
        "free_cash_flow_cr": "fcf_value_pctile",
    }

    for metric, score_col in sector_metrics.items():
        values_dict: dict[str, float | None] = dict(
            zip(df["company_id"], df[metric], strict=False)
        )
        pctile_scores = compute_sector_percentile_scores(
            company_values=values_dict,
            sector_map=sector_map,
            metric_name=metric,
        )
        df[score_col] = df["company_id"].map(pctile_scores)

    # For D/E (lower is better), invert the percentile score
    df["de_pctile"] = df["de_pctile"].apply(
        lambda v: 100.0 - v if v is not None else None
    )

    # Compute sector-relative composite using percentile scores as inputs
    sector_composites = []
    for _, row in df.iterrows():
        # Use percentile scores directly (they're already 0-100)
        cs = composite_quality_score_v2(
            roe_pct=None, roce_pct=None, npm_pct=None,
            fcf_cagr_5yr=None, cfo_pat_ratio=None, fcf_value=None,
            revenue_cagr_5yr=None, pat_cagr_5yr=None,
            debt_to_equity=None, interest_coverage=None,
        )
        # Build sector-relative composite manually:
        # For sector-relative, we use the percentile scores directly as sub-scores
        sector_scores: list[tuple[float | None, float]] = [
            (row.get("roe_pctile"), 15.0),
            (row.get("roce_pctile"), 10.0),
            (row.get("npm_pctile"), 10.0),
            (row.get("fcf_cagr_pctile"), 15.0),
            (row.get("de_pctile"), 10.0),       # inverted D/E percentile
            (row.get("icr_pctile"), 5.0),
            (row.get("revenue_cagr_pctile"), 10.0),
            (row.get("pat_cagr_pctile"), 10.0),
        ]
        from src.analytics.ratio_engine import _weighted_category
        contrib = (
            _weighted_category(sector_scores, total_weight=100.0)
        )
        sector_composites.append(round(contrib, 2))
    df["sector_relative_composite_score"] = sector_composites

    # ================================================================
    # Output Columns
    # ================================================================

    out_columns = [
        "company_id",
        "year",
        "broad_sector",
        # Absolute (winsorised) sub-scores
        "roe_score_abs",
        "roce_score_abs",
        "npm_score_abs",
        "fcf_cagr_score_abs",
        "cfo_pat_ratio_score_abs",
        "fcf_positive_score_abs",
        "revenue_cagr_score_abs",
        "pat_cagr_score_abs",
        "de_score_abs",
        "icr_score_abs",
        # Sector-relative percentile ranks
        "roe_pctile",
        "roce_pctile",
        "npm_pctile",
        "fcf_cagr_pctile",
        "de_pctile",
        "icr_pctile",
        "revenue_cagr_pctile",
        "pat_cagr_pctile",
        # Final composites
        "composite_quality_score",           # winsorised absolute
        "sector_relative_composite_score",   # within-sector percentile
    ]

    out_df = df[out_columns].copy()
    out_df = out_df.sort_values("composite_quality_score", ascending=False, na_position="last")
    out_df.to_csv(out_path, index=False, float_format="%.2f")

    print(f"Exported {len(out_df)} rows to {out_path}")
    return out_path


if __name__ == "__main__":
    export_composite_scores_csv()

