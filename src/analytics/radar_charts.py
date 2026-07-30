"""
Day 19 — Radar / Polar Charts for Peer Group Analysis

Generates radar (polar) charts for each company in a peer group across 8 axes:

  ROE | ROCE | NPM | D/E | FCF Score | PAT CAGR 5yr | Revenue CAGR 5yr | Composite Score

- Each chart shows the company's values as a filled polygon overlaid with the
  peer group average as a dashed outline.
- For companies with no peer group assignment, a standalone bar chart is generated
  showing the company's composite score vs the Nifty 100 average as reference.
- Exports as PNG to reports/radar_charts/<company_id>_radar.png

Uses matplotlib polar plots with readable font sizes.
"""

from __future__ import annotations

import logging
import math
import sqlite3
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "nifty100.db"
OUTPUT_DIR = ROOT / "reports" / "radar_charts"

logger = logging.getLogger(__name__)

# 8 radar axes — (label, db_column_in_financial_ratios, higher_is_better)
# ROCE is loaded from companies.roce_percentage separately
METRICS: list[tuple[str, str, bool]] = [
    ("ROE",                "return_on_equity_pct",   True),
    ("ROCE",               "roce_pct",               True),   # merged from companies
    ("NPM",                "net_profit_margin_pct",  True),
    ("D/E",                "debt_to_equity",         False),  # lower is better → invert
    ("FCF Score",          "free_cash_flow_cr",      True),
    ("PAT CAGR 5yr",       "pat_cagr_5yr",           True),
    ("Rev CAGR 5yr",       "revenue_cagr_5yr",       True),
    ("Composite Score",    "composite_quality_score", True),
]

# Matplotlib style constants
COMPANY_COLOR = "#1f77b4"       # muted blue fill
COMPANY_ALPHA = 0.35
PEER_AVG_COLOR = "#d62728"      # muted red dashed
GRID_COLOR = "#cccccc"
BG_COLOR = "#fafafa"
DPI = 150

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def _safe_float(x):
    if x is None:
        return None
    try:
        return float(x)
    except (ValueError, TypeError):
        return None


def _extract_year(y):
    """Extract the numeric year from mixed-type year column."""
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


def load_data(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Load latest-year financial ratios + ROCE + peer group assignments.

    Returns a DataFrame with one row per company containing:
      - company_id, company_name, peer_group_name, is_benchmark
      - The 8 metric columns defined in METRICS
      - broad_sector (for context)
    """
    conn = sqlite3.connect(str(db_path))

    # --- financial_ratios (latest year per company) ---
    # year column has mixed types (int, 'Mar 2024', 'Sep 2024'...)
    # Load all and deduplicate in pandas for reliable ordering
    fr_cols = [
        "company_id",
        "year",
        "return_on_equity_pct",
        "net_profit_margin_pct",
        "debt_to_equity",
        "interest_coverage",
        "free_cash_flow_cr",
        "pat_cagr_5yr",
        "revenue_cagr_5yr",
        "composite_quality_score",
        "asset_turnover",
    ]
    fr_cols_str = ", ".join(fr_cols)
    fr_df = pd.read_sql_query(f"SELECT {fr_cols_str} FROM financial_ratios", conn)

    # Deduplicate to latest year per company using extracted year number
    fr_df["_year_num"] = fr_df["year"].apply(_extract_year)
    fr_df = fr_df.sort_values(["company_id", "_year_num"], ascending=[True, False])
    fr_df = fr_df.groupby("company_id", as_index=False).first()
    fr_df.drop(columns=["_year_num"], inplace=True)

    # --- ROCE from companies table ---
    roce_df = pd.read_sql_query(
        "SELECT company_id, roce_percentage, company_name FROM companies",
        conn,
    )
    conn.close()

    # Merge ROCE into ratios
    roce_map = dict(zip(roce_df["company_id"], roce_df["roce_percentage"], strict=False))
    name_map = dict(zip(roce_df["company_id"], roce_df["company_name"], strict=False))
    fr_df["roce_pct"] = fr_df["company_id"].map(roce_map)
    fr_df["company_name"] = fr_df["company_id"].map(name_map)

    # Convert numeric columns
    metric_cols = [m[1] for m in METRICS]
    for col in metric_cols:
        if col in fr_df.columns:
            fr_df[col] = fr_df[col].apply(_safe_float)

    # --- Peer group assignments ---
    pg_conn = sqlite3.connect(str(db_path))
    pg_df = pd.read_sql_query(
        "SELECT company_id, peer_group_name, is_benchmark FROM peer_groups",
        pg_conn,
    )
    pg_conn.close()
    if pg_df.empty:
        pg_df = pd.DataFrame(columns=["company_id", "peer_group_name", "is_benchmark"])

    # Merge peer group info
    fr_df = fr_df.merge(
        pg_df[["company_id", "peer_group_name", "is_benchmark"]],
        on="company_id",
        how="left",
    )
    fr_df["is_benchmark"] = fr_df["is_benchmark"].fillna(False).astype(bool)

    return fr_df


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


def normalize_to_0_100(
    df: pd.DataFrame,
    metrics: list[tuple[str, str, bool]] = METRICS,
) -> pd.DataFrame:
    """Min-max normalize each metric column to 0-100 across the given DataFrame.

    For lower-is-better metrics, the value is inverted (100 - normalized).
    Missing values remain None.
    The ``_norm`` column is always created (all None if no valid data).
    """
    result = df.copy()
    for label, col, higher_is_better in metrics:
        norm_col = f"{col}_norm"
        values = result[col].dropna()
        if values.empty:
            result[norm_col] = None
            continue
        vmin, vmax = values.min(), values.max()
        if vmax == vmin:
            result[norm_col] = result[col].apply(
                lambda v: 50.0 if v is not None else None
            )
        else:
            result[norm_col] = result[col].apply(
                lambda v: ((float(v) - vmin) / (vmax - vmin)) * 100.0
                if v is not None else None
            )
        if not higher_is_better:
            result[norm_col] = result[norm_col].apply(
                lambda v: round(100.0 - v, 2) if v is not None else None
            )
        else:
            result[norm_col] = result[norm_col].apply(
                lambda v: round(v, 2) if v is not None else None
            )
    return result


# ---------------------------------------------------------------------------
# Radar chart rendering (matplotlib polar)
# ---------------------------------------------------------------------------


def _make_radar_chart(
    company_id: str,
    company_name: str,
    peer_group_name: str,
    axes_labels: list[str],
    company_values: list[float | None],
    peer_avg_values: list[float | None],
    output_path: Path,
) -> None:
    """Render a single polar radar chart and save to PNG."""
    n_axes = len(axes_labels)
    angles = np.linspace(0, 2 * np.pi, n_axes, endpoint=False).tolist()
    angles += angles[:1]

    valid_indices = [i for i in range(n_axes) if company_values[i] is not None]
    if not valid_indices:
        logger.warning("No valid data for %s - skipping chart", company_id)
        return

    def _close_poly(vals):
        closed = []
        for i in range(n_axes):
            closed.append(vals[i] if vals[i] is not None else 0.0)
        closed.append(closed[0])
        return closed

    company_closed = _close_poly(company_values)
    peer_closed = _close_poly(peer_avg_values)

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={"projection": "polar"})
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(axes_labels, fontsize=11, fontweight="bold")

    ax.set_ylim(0, 105)
    ax.set_yticks([25, 50, 75, 100])
    ax.set_yticklabels(["25", "50", "75", "100"], fontsize=8, color=GRID_COLOR)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f"))

    ax.grid(True, color=GRID_COLOR, linestyle="--", linewidth=0.5, alpha=0.7)

    ax.fill(
        angles, company_closed,
        color=COMPANY_COLOR, alpha=COMPANY_ALPHA, label=company_id,
    )
    ax.plot(
        angles, company_closed,
        color=COMPANY_COLOR, linewidth=2, marker="o", markersize=5,
    )

    ax.plot(
        angles, peer_closed,
        color=PEER_AVG_COLOR, linewidth=2, linestyle="--",
        marker="s", markersize=5, markerfacecolor=PEER_AVG_COLOR,
        label=f"{peer_group_name} Avg",
    )

    ax.legend(
        loc="upper right", bbox_to_anchor=(1.25, 1.1),
        fontsize=10, frameon=True, facecolor="white", edgecolor=GRID_COLOR,
    )

    plt.title(
        f"{company_name} ({company_id})\nPeer Group: {peer_group_name}",
        fontsize=13, fontweight="bold", pad=20,
    )

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=DPI, facecolor=BG_COLOR, bbox_inches="tight")
    plt.close(fig)
    logger.info("  Saved %s", output_path.name)


def _make_standalone_chart(
    company_id: str,
    company_name: str,
    company_composite: float | None,
    nifty_avg_composite: float | None,
    output_path: Path,
) -> None:
    """Generate a simple bar chart for companies without a peer group.

    Shows company composite score vs Nifty 100 average as a reference.
    """
    comp_valid = company_composite is not None and pd.notna(company_composite)
    avg_valid = nifty_avg_composite is not None and pd.notna(nifty_avg_composite)

    if not comp_valid and not avg_valid:
        logger.warning("No composite score data for %s - skipping standalone chart", company_id)
        return

    fig, ax = plt.subplots(figsize=(6, 4))
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    labels = []
    plot_values = []
    bar_colors = []

    if comp_valid:
        labels.append(f"{company_id}\n(Company)")
        plot_values.append(float(company_composite))
        bar_colors.append(COMPANY_COLOR)
    if avg_valid:
        labels.append("Nifty 100\nAverage")
        plot_values.append(float(nifty_avg_composite))
        bar_colors.append("#2ca02c")

    bars = ax.bar(labels, plot_values, color=bar_colors, edgecolor="white",
                  linewidth=1.2, width=0.5)

    for bar, val in zip(bars, plot_values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 1,
            f"{val:.2f}", ha="center", va="bottom",
            fontsize=11, fontweight="bold",
        )

    ax.set_ylim(0, max(plot_values) * 1.25 if plot_values else 100)
    ax.set_ylabel("Composite Quality Score (0-100)", fontsize=11)
    ax.set_title(
        f"{company_name} ({company_id})\n- No Peer Group Assigned -",
        fontsize=13, fontweight="bold",
    )
    ax.grid(axis="y", color=GRID_COLOR, linestyle="--", linewidth=0.5, alpha=0.7)
    ax.set_axisbelow(True)

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=DPI, facecolor=BG_COLOR, bbox_inches="tight")
    plt.close(fig)
    logger.info("  Saved %s (standalone)", output_path.name)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


def export_all_radar_charts(
    db_path: Path = DB_PATH,
    output_dir: Path = OUTPUT_DIR,
) -> int:
    """Generate radar charts for all companies.

    For each peer group:
      1. Filter companies in that group.
      2. Min-max normalize all 8 metrics to 0-100 within the group.
      3. Compute peer group average normalized values.
      4. For each company generate radar chart (filled polygon + dashed avg).

    For companies without a peer group:
      Generate a standalone bar chart comparing composite score vs Nifty 100 avg.

    Returns the number of charts generated.
    """
    logger.info("Loading data from %s ...", db_path)
    df = load_data(db_path)

    nifty_avg_composite = df["composite_quality_score"].mean()
    if pd.isna(nifty_avg_composite):
        nifty_avg_composite = None

    assigned = df[df["peer_group_name"].notna()].copy()
    unassigned = df[df["peer_group_name"].isna()].copy()

    logger.info(
        "Loaded %d companies (%d with peer groups, %d unassigned)",
        len(df), len(assigned), len(unassigned),
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    chart_count = 0
    axes_labels = [m[0] for m in METRICS]

    # PART 1: Peer-group radar charts
    for group_name, group_df in assigned.groupby("peer_group_name"):
        if group_df.empty:
            continue

        group_norm = normalize_to_0_100(group_df, METRICS)
        norm_cols = [f"{m[1]}_norm" for m in METRICS]
        group_avg = group_norm[norm_cols].mean().to_dict()

        for _, row in group_norm.iterrows():
            cid = row["company_id"]
            cname = row.get("company_name") or cid

            company_vals = [row.get(f"{m[1]}_norm") for m in METRICS]
            peer_avg_vals = [group_avg.get(f"{m[1]}_norm") for m in METRICS]

            out_path = output_dir / f"{cid}_radar.png"
            _make_radar_chart(
                company_id=cid, company_name=cname,
                peer_group_name=group_name, axes_labels=axes_labels,
                company_values=company_vals, peer_avg_values=peer_avg_vals,
                output_path=out_path,
            )
            chart_count += 1

    # PART 2: Standalone charts for unassigned companies
    for _, row in unassigned.iterrows():
        cid = row["company_id"]
        cname = row.get("company_name") or cid
        company_composite = row.get("composite_quality_score")

        out_path = output_dir / f"{cid}_radar.png"
        _make_standalone_chart(
            company_id=cid, company_name=cname,
            company_composite=company_composite,
            nifty_avg_composite=nifty_avg_composite,
            output_path=out_path,
        )
        chart_count += 1

    print()
    print("=" * 55)
    print(f"  Radar Chart Generation Complete")
    print(f"  Total charts exported: {chart_count}")
    print(f"  Directory: {output_dir}")
    print("=" * 55)
    print()

    return chart_count


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    export_all_radar_charts()

