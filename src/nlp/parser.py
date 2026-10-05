"""
Sprint 5 · Day 29 — NLP · Analysis Text Parser

Parses the embedded horizon/percentage text fields in ``analysis.xlsx`` into a
structured long-format CSV, logging any entries that fail the regex pattern.

Target fields (per the sprint ticket):
    compounded_sales_growth   -> sales_growth
    compounded_profit_growth  -> profit_growth
    stock_price_cagr          -> stock_cagr
    roe                       -> roe

The source text is a single string that embeds both a horizon and a value, e.g.::

    10 Years: 21%
    5 Years:       24%
    3 Years:       17%
    TTM:            43%
    Last Year:      12%
    1 Year:         -2%

The spec regex is ``(\\d+)\\s*Years?:?\\s*([\\d.]+)%`` which captures ``(period, value)``.
We retain that structure but widen the value capture to ``-?(\\d+(?:\\.\\d+)?)`` so that
negative values (e.g. ``-2%``) and decimals parse correctly. Non-numeric horizons
(``TTM``, ``Last Year``) map to sentinel period values.

Outputs (written to ``output/``):
    analysis_parsed.csv              long-format rows: company_id, metric_type,
                                     period_years, value_pct
    parse_failures.csv               any text entries that did not match the pattern
    cagr_cross_validation.csv        parsed 5y sales/profit CAGR vs the Ratio Engine
                                     (financial_ratios.revenue_cagr_5yr /
                                      pat_cagr_5yr), flagging divergence > 5%.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Optional

import pandas as pd

try:
    from src.etl.normaliser import normalize_ticker
except Exception:  # pragma: no cover - defensive import fallback
    normalize_ticker = None


ROOT = Path(__file__).resolve().parents[2]
CORE_DIR = ROOT / "data" / "core"
DB_PATH = ROOT / "nifty100.db"
OUTPUT_DIR = ROOT / "output"

# Embedded metric columns (source column name -> emitted metric_type)
TARGET_FIELDS = {
    "compounded_sales_growth": "sales_growth",
    "compounded_profit_growth": "profit_growth",
    "stock_price_cagr": "stock_cagr",
    "roe": "roe",
}

# Primary spec pattern: (period) Years [optional :] (signed value) %
#   "10 Years: 21%"   -> ("10", "21")
#   "5 Years:  -2%"   -> ("5", "-2")
#   "3 Years: 14.5%"  -> ("3", "14.5")
HORIZON_RE = re.compile(r"(\d+)\s*Years?:?\s*(-?\d+(?:\.\d+)?)\s*%", re.IGNORECASE)

# Fallback for horizon labels that are not plain numbers (TTM / Last Year).
# We still want the numeric value, and map the non-numeric horizon to sentinels.
_NON_NUMERIC_HORIZON_RE = re.compile(r"^(TTM|Last\s+Year|YTD|Total)\s*:?\s*(-?\d+(?:\.\d+)?)\s*%$", re.IGNORECASE)

# Sentinel period values for non-integer horizons (documented in the CSV).
PERIOD_TTM = 0
PERIOD_LAST_YEAR = 1

_DIVERGENCE_THRESHOLD = 5.0  # percentage points


def _period_sentinel(label: str) -> Optional[int]:
    """Map a non-numeric horizon label to a sentinel period value."""
    key = re.sub(r"\s+", " ", label or "").strip().lower()
    if key == "ttm":
        return PERIOD_TTM
    if key in ("last year", "lastyear"):
        return PERIOD_LAST_YEAR
    return None


def parse_metric_text(raw_text) -> tuple[Optional[int], Optional[float]]:
    """Parse an embedded horizon/pct string into ``(period_years, value_pct)``.

    Returns ``(None, None)`` when the text cannot be parsed.
    """
    if raw_text is None:
        return None, None
    s = str(raw_text).strip()
    if not s:
        return None, None

    # Primary: "<N> Years: <value>%" (with optional colon / spaces)
    m = HORIZON_RE.search(s)
    if m:
        period = int(m.group(1))
        value = float(m.group(2))
        return period, value

    # Fallback: non-numeric horizons like "TTM: 43%" / "Last Year: 12%"
    nm = _NON_NUMERIC_HORIZON_RE.search(s)
    if nm:
        label = nm.group(1)
        value = float(nm.group(2))
        period = _period_sentinel(label)
        return period, value

    return None, None


def _coerce_company_id(value) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip().upper()
    s = re.sub(r"\s+", "", s)
    return s or None


def parse_analysis_xlsx(
    xlsx_path: Path = CORE_DIR / "analysis.xlsx",
    out_dir: Path = OUTPUT_DIR,
) -> tuple[Path, Path]:
    """Parse analysis.xlsx into ``analysis_parsed.csv`` + ``parse_failures.csv``.

    Returns ``(parsed_path, failures_path)``.
    """
    out_dir.mkdir(exist_ok=True, parents=True)
    parsed_path = out_dir / "analysis_parsed.csv"
    failures_path = out_dir / "parse_failures.csv"

    df = pd.read_excel(xlsx_path, header=1)

    parsed_rows: list[dict] = []
    failure_rows: list[dict] = []

    for _, r in df.iterrows():
        cid = _coerce_company_id(r.get("company_id"))
        if cid is None:
            continue

        for src_col, metric_type in TARGET_FIELDS.items():
            raw = r.get(src_col)
            period, value = parse_metric_text(raw)

            if period is None or value is None:
                failure_rows.append({
                    "company_id": cid,
                    "metric_type": metric_type,
                    "source_column": src_col,
                    "raw_text": raw,
                    "reason": "no match for pattern",
                })
                continue

            parsed_rows.append({
                "company_id": cid,
                "metric_type": metric_type,
                "period_years": period,
                "value_pct": value,
            })

    parsed_df = pd.DataFrame(parsed_rows, columns=[
        "company_id", "metric_type", "period_years", "value_pct",
    ])
    parsed_df = parsed_df.sort_values(["company_id", "metric_type", "period_years"])
    parsed_df.to_csv(parsed_path, index=False, float_format="%.4f")

    failure_df = pd.DataFrame(failure_rows, columns=[
        "company_id", "metric_type", "source_column", "raw_text", "reason",
    ])
    failure_df.to_csv(failures_path, index=False)

    return parsed_path, failures_path


def _load_ratio_engine_cagr(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Load latest-year revenue_cagr_5yr / pat_cagr_5yr from financial_ratios."""
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        """
        SELECT company_id, revenue_cagr_5yr, pat_cagr_5yr
        FROM financial_ratios
        WHERE year = (
            SELECT MAX(year) FROM financial_ratios fr2
            WHERE fr2.company_id = financial_ratios.company_id
        )
        """,
        conn,
    )
    conn.close()
    return df


def cross_validate_cagr(
    parsed_df: Optional[pd.DataFrame] = None,
    db_path: Path = DB_PATH,
    out_dir: Path = OUTPUT_DIR,
    divergence_threshold: float = _DIVERGENCE_THRESHOLD,
) -> Path:
    """Cross-validate parsed 5-year CAGR vs the Ratio Engine.

    Compares:
        sales_growth (period 5)  vs financial_ratios.revenue_cagr_5yr
        profit_growth (period 5) vs financial_ratios.pat_cagr_5yr

    Flags a row when ``abs(parsed - engine) > divergence_threshold``.

    Returns the path to ``cagr_cross_validation.csv``.
    """
    out_dir.mkdir(exist_ok=True, parents=True)
    out_path = out_dir / "cagr_cross_validation.csv"

    if parsed_df is None:
        parsed_df = pd.read_csv(out_dir / "analysis_parsed.csv")

    engine = _load_ratio_engine_cagr(db_path)

    # Pivot parsed 5-year values per company.
    five = parsed_df[parsed_df["period_years"] == 5].copy()
    pivot = five.pivot_table(
        index="company_id",
        columns="metric_type",
        values="value_pct",
        aggfunc="first",
    ).reset_index()

    metric_map = {
        "sales_growth": ("revenue_cagr_5yr", "Ratio Engine revenue CAGR 5y"),
        "profit_growth": ("pat_cagr_5yr", "Ratio Engine PAT CAGR 5y"),
    }

    rows: list[dict] = []
    for _, erow in engine.iterrows():
        cid = erow["company_id"]
        p = pivot[pivot["company_id"] == cid]
        if p.empty:
            continue
        p = p.iloc[0]
        for parsed_metric, (engine_col, engine_label) in metric_map.items():
            parsed_val = p.get(parsed_metric)
            engine_val = erow.get(engine_col)
            if parsed_val is None or engine_val is None:
                continue
            diff = float(parsed_val) - float(engine_val)
            flag = abs(diff) > divergence_threshold
            rows.append({
                "company_id": cid,
                "metric_type": parsed_metric,
                "parsed_value_pct": round(float(parsed_val), 4),
                "ratio_engine_value_pct": round(float(engine_val), 4),
                "divergence_pct": round(diff, 4),
                "flag_review": flag,
                "engine_metric": engine_label,
            })

    out_df = pd.DataFrame(rows, columns=[
        "company_id", "metric_type", "parsed_value_pct",
        "ratio_engine_value_pct", "divergence_pct", "flag_review",
        "engine_metric",
    ])
    out_df.to_csv(out_path, index=False, float_format="%.4f")
    return out_path


def run_parser(
    xlsx_path: Path = CORE_DIR / "analysis.xlsx",
    db_path: Path = DB_PATH,
    out_dir: Path = OUTPUT_DIR,
) -> dict:
    """Run the full Day 29 pipeline and return a summary dict."""
    parsed_path, failures_path = parse_analysis_xlsx(xlsx_path, out_dir)

    parsed_df = pd.read_csv(parsed_path)
    failure_df = pd.read_csv(failures_path) if failures_path.exists() else pd.DataFrame()

    cross_path = cross_validate_cagr(parsed_df, db_path, out_dir)
    cross_df = pd.read_csv(cross_path)

    summary = {
        "analysis_parsed": parsed_path,
        "parse_failures": failures_path,
        "cagr_cross_validation": cross_path,
        "parsed_rows": len(parsed_df),
        "failure_rows": len(failure_df),
        "cross_validation_rows": len(cross_df),
        "flagged_rows": int(cross_df["flag_review"].sum()) if "flag_review" in cross_df.columns and len(cross_df) else 0,
    }
    return summary


if __name__ == "__main__":
    s = run_parser()
    print("=== Day 29 — Analysis Text Parser ===")
    print(f"analysis_parsed.csv      -> {s['analysis_parsed']}  ({s['parsed_rows']} rows)")
    print(f"parse_failures.csv       -> {s['parse_failures']}   ({s['failure_rows']} rows)")
    print(f"cagr_cross_validation.csv-> {s['cagr_cross_validation']}  ({s['cross_validation_rows']} rows, {s['flagged_rows']} flagged)")
