"""
Day 26 — Valuation Module

Generates valuation summaries and flags using the market_cap and
financial_ratios source data loaded into nifty100.db.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "nifty100.db"
OUTPUT_DIR = ROOT / "output"
SUMMARY_PATH = OUTPUT_DIR / "valuation_summary.xlsx"
FLAGS_PATH = OUTPUT_DIR / "valuation_flags.csv"


def _safe_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_sql(query: str, params: tuple = (), db_path: Path = DB_PATH) -> pd.DataFrame:
    with sqlite3.connect(str(db_path)) as conn:
        return pd.read_sql_query(query, conn, params=params)


def load_valuation_base_data(db_path: Path = DB_PATH) -> pd.DataFrame:
    query = """
    SELECT
        c.company_id,
        c.company_name,
        s.broad_sector,
        m.market_cap_crore,
        m.pe_ratio,
        m.pb_ratio,
        m.ev_ebitda,
        fr.free_cash_flow_cr
    FROM companies c
    LEFT JOIN sectors s ON s.company_id = c.company_id
    LEFT JOIN market_cap m ON m.company_id = c.company_id
        AND m.year = (
            SELECT MAX(year) FROM market_cap m2 WHERE m2.company_id = m.company_id
        )
    LEFT JOIN financial_ratios fr ON fr.company_id = c.company_id
        AND fr.year = (
            SELECT MAX(year) FROM financial_ratios fr2 WHERE fr2.company_id = fr.company_id
        )
    """
    df = _load_sql(query, db_path=db_path)
    for col in ["market_cap_crore", "pe_ratio", "pb_ratio", "ev_ebitda", "free_cash_flow_cr"]:
        if col in df.columns:
            df[col] = df[col].apply(_safe_float)
    return df


def load_market_cap_history(db_path: Path = DB_PATH) -> pd.DataFrame:
    query = "SELECT company_id, year, pe_ratio FROM market_cap"
    df = _load_sql(query, db_path=db_path)
    df["pe_ratio"] = df["pe_ratio"].apply(_safe_float)
    return df


def compute_5yr_median_pe(market_cap_history: pd.DataFrame) -> pd.Series:
    if market_cap_history.empty:
        return pd.Series(dtype=float)

    history = market_cap_history.copy()
    history = history.sort_values(["company_id", "year"], ascending=[True, False])
    latest_five = history.groupby("company_id", group_keys=False).head(5)
    median_pe = latest_five.groupby("company_id")["pe_ratio"].median()
    return median_pe


def build_valuation_summary(
    valuation_base: pd.DataFrame,
    market_cap_history: pd.DataFrame,
) -> pd.DataFrame:
    if valuation_base.empty:
        return pd.DataFrame(
            columns=[
                "company_id",
                "company_name",
                "sector",
                "P/E",
                "P/B",
                "EV/EBITDA",
                "FCF_yield_pct",
                "5yr_median_PE",
                "PE_vs_sector_median_pct",
                "flag",
            ]
        )

    df = valuation_base.copy()
    df["sector_median_pe"] = df.groupby("broad_sector")["pe_ratio"].transform("median")
    df["5yr_median_PE"] = df["company_id"].map(compute_5yr_median_pe(market_cap_history))

    def _calc_fcf_yield(row: pd.Series) -> float | None:
        market_cap = row["market_cap_crore"]
        fcf = row["free_cash_flow_cr"]
        if market_cap is None or market_cap == 0 or fcf is None:
            return None
        return float(fcf) / float(market_cap) * 100.0

    def _calc_pe_vs_sector_med(row: pd.Series) -> float | None:
        pe = row["pe_ratio"]
        sector_pe = row["sector_median_pe"]
        if pe is None or sector_pe is None or sector_pe == 0:
            return None
        return float(pe) / float(sector_pe) * 100.0

    def _flag_pe(row: pd.Series) -> str | None:
        pe = row["pe_ratio"]
        sector_pe = row["sector_median_pe"]
        if pe is None or sector_pe is None:
            return None
        if pe > sector_pe * 1.5:
            return "Caution"
        if pe < sector_pe * 0.7:
            return "Discount"
        return "Fair"

    df["FCF_yield_pct"] = df.apply(_calc_fcf_yield, axis=1)
    df["PE_vs_sector_median_pct"] = df.apply(_calc_pe_vs_sector_med, axis=1)
    df["flag"] = df.apply(_flag_pe, axis=1)

    output = df.rename(
        columns={
            "broad_sector": "sector",
            "pe_ratio": "P/E",
            "pb_ratio": "P/B",
            "ev_ebitda": "EV/EBITDA",
        }
    )

    output = output[
        [
            "company_id",
            "company_name",
            "sector",
            "P/E",
            "P/B",
            "EV/EBITDA",
            "FCF_yield_pct",
            "5yr_median_PE",
            "PE_vs_sector_median_pct",
            "flag",
        ]
    ]

    for column in ["P/E", "P/B", "EV/EBITDA", "FCF_yield_pct", "5yr_median_PE", "PE_vs_sector_median_pct"]:
        if column in output.columns:
            output[column] = output[column].apply(lambda x: round(x, 2) if x is not None else None)

    return output


def export_valuation_summary(
    output_path: Path = SUMMARY_PATH,
    flags_path: Path = FLAGS_PATH,
    db_path: Path = DB_PATH,
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    base_data = load_valuation_base_data(db_path=db_path)
    market_cap_history = load_market_cap_history(db_path=db_path)
    summary = build_valuation_summary(base_data, market_cap_history)

    summary.to_excel(output_path, index=False)

    flags = summary[summary["flag"].isin(["Caution", "Discount"])].copy()
    flags.to_csv(flags_path, index=False)

    return output_path, flags_path


if __name__ == "__main__":
    export_valuation_summary()
