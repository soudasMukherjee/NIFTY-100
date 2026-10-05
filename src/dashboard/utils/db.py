from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

# File lives at src/dashboard/utils/db.py -> project root is 3 levels up.
ROOT = Path(__file__).resolve().parents[3]
DB_PATH = ROOT / "nifty100.db"


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database file not found: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


@st.cache_data(ttl=600)
def get_companies() -> pd.DataFrame:
    query = """
    SELECT
        c.company_id,
        c.company_name,
        c.company_logo,
        c.website,
        c.nse_profile,
        c.bse_profile,
        c.about_company,
        c.roce_percentage,
        c.roe_percentage,
        s.broad_sector,
        s.sub_sector,
        s.index_weight_pct,
        s.market_cap_category
    FROM companies c
    LEFT JOIN sectors s ON c.company_id = s.company_id
    ORDER BY c.company_id
    """
    with _connect() as conn:
        return pd.read_sql_query(query, conn)


@st.cache_data(ttl=600)
def get_ratios(ticker: str, year: int | None = None) -> pd.DataFrame:
    query = "SELECT * FROM financial_ratios WHERE company_id = ?"
    params: tuple[str, ...] = (ticker,)
    if year is not None:
        query += " AND CAST(year AS INTEGER) = ?"
        params = (ticker, str(year))
    query += " ORDER BY CAST(year AS INTEGER) DESC"
    with _connect() as conn:
        return pd.read_sql_query(query, conn, params=params)


@st.cache_data(ttl=600)
def get_pl(ticker: str) -> pd.DataFrame:
    query = """
    SELECT *
    FROM profitandloss
    WHERE company_id = ?
    ORDER BY CAST(year AS INTEGER) DESC, period_type
    """
    with _connect() as conn:
        return pd.read_sql_query(query, conn, params=(ticker,))


@st.cache_data(ttl=600)
def get_bs(ticker: str) -> pd.DataFrame:
    query = """
    SELECT *
    FROM balancesheet
    WHERE company_id = ?
    ORDER BY CAST(year AS INTEGER) DESC, period_type
    """
    with _connect() as conn:
        return pd.read_sql_query(query, conn, params=(ticker,))


@st.cache_data(ttl=600)
def get_cf(ticker: str) -> pd.DataFrame:
    query = """
    SELECT *
    FROM cashflow
    WHERE company_id = ?
    ORDER BY CAST(year AS INTEGER) DESC
    """
    with _connect() as conn:
        return pd.read_sql_query(query, conn, params=(ticker,))


@st.cache_data(ttl=600)
def get_sectors() -> pd.DataFrame:
    query = """
    SELECT
        s.company_id,
        c.company_name,
        s.broad_sector,
        s.sub_sector,
        s.index_weight_pct,
        s.market_cap_category
    FROM sectors s
    LEFT JOIN companies c ON c.company_id = s.company_id
    ORDER BY s.broad_sector, s.company_id
    """
    with _connect() as conn:
        return pd.read_sql_query(query, conn)


@st.cache_data(ttl=600)
def get_peer_groups() -> pd.DataFrame:
    query = """
    SELECT DISTINCT peer_group_name
    FROM peer_groups
    ORDER BY peer_group_name
    """
    with _connect() as conn:
        return pd.read_sql_query(query, conn)


@st.cache_data(ttl=600)
def get_peers(group_name: str) -> pd.DataFrame:
    query = """
    SELECT
        pg.company_id,
        c.company_name,
        pg.is_benchmark,
        s.broad_sector,
        c.roce_percentage AS roce_pct,
        m.market_cap_crore,
        m.pe_ratio,
        m.pb_ratio,
        m.dividend_yield_pct,
        fr.return_on_equity_pct,
        fr.net_profit_margin_pct,
        fr.debt_to_equity,
        fr.free_cash_flow_cr,
        fr.revenue_cagr_5yr,
        fr.pat_cagr_5yr,
        fr.composite_quality_score
    FROM peer_groups pg
    LEFT JOIN companies c ON c.company_id = pg.company_id
    LEFT JOIN sectors s ON s.company_id = pg.company_id
    LEFT JOIN financial_ratios fr ON fr.company_id = pg.company_id
        AND fr.year = (
            SELECT MAX(year) FROM financial_ratios fr2
            WHERE fr2.company_id = fr.company_id
              AND typeof(fr2.year) = 'integer'
        )
    LEFT JOIN market_cap m ON m.company_id = pg.company_id
        AND m.year = (
            SELECT MAX(year) FROM market_cap m2 WHERE m2.company_id = m.company_id
        )
    WHERE pg.peer_group_name = ?
    ORDER BY pg.is_benchmark DESC, pg.company_id
    """
    with _connect() as conn:
        return pd.read_sql_query(query, conn, params=(group_name,))


@st.cache_data(ttl=600)
def get_financial_ratios_by_year(year: int) -> pd.DataFrame:
    query = """
    SELECT *
    FROM financial_ratios
    WHERE CAST(year AS INTEGER) = ?
    ORDER BY company_id
    """
    with _connect() as conn:
        return pd.read_sql_query(query, conn, params=(year,))


@st.cache_data(ttl=600)
def get_market_cap_by_year(year: int) -> pd.DataFrame:
    query = """
    SELECT *
    FROM market_cap
    WHERE year = ?
    ORDER BY company_id
    """
    with _connect() as conn:
        return pd.read_sql_query(query, conn, params=(year,))


@st.cache_data(ttl=600)
def get_prosandcons(ticker: str) -> pd.DataFrame:
    query = """
    SELECT *
    FROM prosandcons
    WHERE company_id = ?
    """
    with _connect() as conn:
        return pd.read_sql_query(query, conn, params=(ticker,))


@st.cache_data(ttl=600)
def get_returns_history(ticker: str) -> pd.DataFrame:
    query = """
    SELECT
        fr.year,
        fr.return_on_equity_pct AS roe_pct,
        pl.operating_profit,
        bs.equity_capital,
        bs.reserves,
        bs.borrowings
    FROM financial_ratios fr
    LEFT JOIN profitandloss pl
        ON fr.company_id = pl.company_id
        AND fr.year = pl.year
        AND pl.period_type = 'ANNUAL'
    LEFT JOIN balancesheet bs
        ON fr.company_id = bs.company_id
        AND fr.year = bs.year
        AND bs.period_type = 'ANNUAL'
    WHERE fr.company_id = ?
    ORDER BY CAST(fr.year AS INTEGER) ASC
    """
    with _connect() as conn:
        df = pd.read_sql_query(query, conn, params=(ticker,))

    def _calc_roce(row: dict[str, object]) -> float | None:
        try:
            op = float(row["operating_profit"]) if row["operating_profit"] is not None else None
            eq = float(row["equity_capital"]) if row["equity_capital"] is not None else 0.0
            rv = float(row["reserves"]) if row["reserves"] is not None else 0.0
            br = float(row["borrowings"]) if row["borrowings"] is not None else 0.0
        except (ValueError, TypeError):
            return None
        if op is None or (eq + rv + br) <= 0:
            return None
        return (op / (eq + rv + br)) * 100.0

    if not df.empty:
        df["roce_pct"] = df.apply(_calc_roce, axis=1)
    return df[["year", "roe_pct", "roce_pct"]]


@st.cache_data(ttl=600)
def get_valuation(ticker: str) -> pd.DataFrame:
    query = """
    SELECT
        fr.company_id,
        fr.year AS ratio_year,
        fr.free_cash_flow_cr,
        m.market_cap_crore,
        m.pe_ratio,
        m.pb_ratio,
        s.broad_sector,
        s.sub_sector
    FROM financial_ratios fr
    LEFT JOIN market_cap m ON m.company_id = fr.company_id
        AND m.year = (
            SELECT MAX(year) FROM market_cap m2 WHERE m2.company_id = m.company_id
        )
    LEFT JOIN sectors s ON s.company_id = fr.company_id
    WHERE fr.company_id = ?
      AND fr.year = (
            SELECT MAX(year) FROM financial_ratios fr2
            WHERE fr2.company_id = fr.company_id
              AND typeof(fr2.year) = 'integer'
        )
    LIMIT 1
    """
    with _connect() as conn:
        valuation = pd.read_sql_query(query, conn, params=(ticker,))

    if valuation.empty:
        return valuation

    row = valuation.iloc[0].to_dict()
    fcf = row.get("free_cash_flow_cr")
    market_cap = row.get("market_cap_crore")
    pe_ratio = row.get("pe_ratio")

    fcf_yield = None
    if fcf is not None and market_cap not in (None, 0):
        try:
            fcf_yield = float(fcf) / float(market_cap) * 100.0
        except (ValueError, ZeroDivisionError):
            fcf_yield = None

    pe_flag = None
    if pe_ratio is not None:
        pe_flag = (
            "Attractive" if pe_ratio <= 18
            else "Neutral" if pe_ratio <= 28
            else "High"
        )

    if fcf_yield is None or pe_ratio is None:
        valuation_label = "Insufficient data"
    elif fcf_yield >= 8.0 and pe_ratio <= 20.0:
        valuation_label = "Discount"
    elif fcf_yield < 4.0 or pe_ratio >= 30.0:
        valuation_label = "Overvalued"
    else:
        valuation_label = "Fair Value"

    valuation = valuation.assign(
        fcf_yield_pct=[fcf_yield],
        pe_flag=[pe_flag],
        valuation_label=[valuation_label],
    )
    return valuation
