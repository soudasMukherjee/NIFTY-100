from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from src.analytics.cagr import (
    eps_cagr_windows,
    free_cash_flow_cagr,
    free_cash_flow_cagr_windows,
    pat_cagr_windows,
    revenue_cagr_windows,
)
from src.analytics.ratio_engine import composite_quality_score_v2
from src.analytics.ratios import (
    asset_turnover,
    capex_intensity,
    cfo_quality_score,
    debt_to_equity,
    free_cash_flow,
    fcf_conversion_rate,
    interest_coverage_ratio,
    net_profit_margin,
    operating_profit_margin,
    return_on_capital_employed,
    return_on_equity,
)



ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "nifty100.db"
OUTPUT_DIR = ROOT / "output"
EDGE_CASE_LOG_PATH = OUTPUT_DIR / "ratio_edge_cases.log"



def _safe_float(x):
    if x is None:
        return None
    try:
        return float(x)
    except Exception:
        return None


def populate_financial_ratios(db_path: Path = DB_PATH) -> Path:
    """Populate financial_ratios with the KPIs supported by db/schema.sql.

    Note: This is designed to be tolerant to schema drift (it inserts only
    columns that currently exist in the target DB).
    """

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    companies = pd.read_sql_query("SELECT company_id FROM companies", conn)
    pl = pd.read_sql_query(
        """
        SELECT company_id, year, period_type, sales, operating_profit, net_profit,
               other_income, interest, eps, dividend_payout
        FROM profitandloss
        WHERE period_type='ANNUAL'
        """,
        conn,
    )
    bs = pd.read_sql_query(
        """
        SELECT company_id, year, period_type, equity_capital, reserves, borrowings,
               total_assets, investments
        FROM balancesheet
        WHERE period_type='ANNUAL'
        """,
        conn,
    )
    cf = pd.read_sql_query(
        """
        SELECT company_id, year, operating_activity, investing_activity, financing_activity
        FROM cashflow
        """,
        conn,
    )

    # Preload for CAGR sequences (ordered oldest -> newest)
    pl_all = pd.read_sql_query(
        """
        SELECT company_id, year, period_type, sales, net_profit, eps
        FROM profitandloss
        """,
        conn,
    )
    conn.close()

    # Separate connection for any additional reads (e.g. company-level roce_percentage)
    conn2 = sqlite3.connect(db_path)
    conn2.execute("PRAGMA foreign_keys = ON")

    ratios_rows: list[dict] = []


    companies_list = companies["company_id"].tolist()

    for cid in companies_list:
        pl_c = pl[(pl["company_id"] == cid)].copy()


        bs_c = bs[(bs["company_id"] == cid)].copy()
        cf_c = cf[(cf["company_id"] == cid)].copy()

        if pl_c.empty or bs_c.empty or cf_c.empty:
            continue

        df = pl_c.merge(bs_c, on=["company_id", "year"], how="left").merge(
            cf_c, on=["company_id", "year"], how="left"
        )
        df = df.sort_values("year")

        sales_seq = (
            pl_all[(pl_all["company_id"] == cid) & (pl_all["period_type"] == "ANNUAL")]
            .sort_values("year")["sales"]
            .tolist()
        )
        pat_seq = (
            pl_all[(pl_all["company_id"] == cid) & (pl_all["period_type"] == "ANNUAL")]
            .sort_values("year")["net_profit"]
            .tolist()
        )
        eps_seq = (
            pl_all[(pl_all["company_id"] == cid) & (pl_all["period_type"] == "ANNUAL")]
            .sort_values("year")["eps"]
            .tolist()
        )
        cfo_seq = cf_c.sort_values("year")["operating_activity"].tolist()
        investing_seq = cf_c.sort_values("year")["investing_activity"].tolist()

        # Build FCF sequence: FCF = operating_activity + investing_activity (per year)
        fcf_seq = None
        if len(cfo_seq) == len(investing_seq):
            fcf_seq = [float(cfo) + float(inv) for cfo, inv in zip(cfo_seq, investing_seq)]

        cagr_revenue_windows = None
        cagr_pat_windows = None
        cagr_eps_windows = None
        cagr_revenue_5yr = None
        cagr_revenue_3yr = None
        cagr_pat_5yr = None
        cagr_eps_5yr = None
        cagr_fcf_5yr = None
        if len(sales_seq) >= 5 and len(pat_seq) >= 5 and len(eps_seq) >= 5:
            # These helpers may return None for invalid windows.
            rev_windows = revenue_cagr_windows(revenues=sales_seq)
            cagr_revenue_5yr = rev_windows.get(5) if rev_windows else None
            cagr_revenue_3yr = rev_windows.get(3) if rev_windows else None
            pat_windows = pat_cagr_windows(pats=pat_seq)
            cagr_pat_5yr = pat_windows.get(5) if pat_windows else None
            eps_windows = eps_cagr_windows(eps_by_year=eps_seq)
            cagr_eps_5yr = eps_windows.get(5)[0] if eps_windows and eps_windows.get(5) else None
            if fcf_seq is not None and len(fcf_seq) >= 5:
                fcf_windows = free_cash_flow_cagr_windows(fcf_values=fcf_seq)
                cagr_fcf_5yr = fcf_windows.get(5) if fcf_windows else None
        elif len(sales_seq) >= 3:
            # At least 3 years — compute 3yr CAGR
            rev_windows = revenue_cagr_windows(revenues=sales_seq)
            cagr_revenue_3yr = rev_windows.get(3) if rev_windows else None

        cfo_quality = None
        if len(cfo_seq) >= 5 and len(pat_seq) >= 5:
            cfo_quality = cfo_quality_score(
                cfo_by_year=cfo_seq,
                pat_by_year=pat_seq,
                years=5,
            )

        # Compute per-row and reuse already computed window stats when possible.
        for _, row in df.iterrows():
            year = int(row["year"])

            sales = _safe_float(row.get("sales"))
            operating_profit = _safe_float(row.get("operating_profit"))
            net_profit = _safe_float(row.get("net_profit"))

            equity_capital = _safe_float(row.get("equity_capital"))
            reserves = _safe_float(row.get("reserves"))
            borrowings = _safe_float(row.get("borrowings"))
            total_assets = _safe_float(row.get("total_assets"))

            interest = _safe_float(row.get("interest"))
            other_income = _safe_float(row.get("other_income"))

            eps = _safe_float(row.get("eps"))
            dividend_payout = _safe_float(row.get("dividend_payout"))

            investing_activity = _safe_float(row.get("investing_activity"))
            operating_activity = _safe_float(row.get("operating_activity"))
            financing_activity = _safe_float(row.get("financing_activity"))

            dividend_payout_ratio_pct = None
            if net_profit is not None and net_profit != 0 and dividend_payout is not None:
                dividend_payout_ratio_pct = (dividend_payout / net_profit) * 100.0

            # FCF and conversion rate
            free_cash_flow_cr = None
            fcf_conversion_rate_pct = None
            if operating_activity is not None and investing_activity is not None:
                free_cash_flow_cr = free_cash_flow(
                    operating_activity=operating_activity,
                    investing_activity=investing_activity,
                )
                if operating_profit is not None and operating_profit != 0:
                    fcf_conversion_rate_pct = (free_cash_flow_cr / operating_profit) * 100.0

            # Other straightforward KPIs
            free_cash_flow_cr = free_cash_flow_cr
            capex_cr = investing_activity

            # ---- ROCE edge-case logging (computed vs precomputed) ----
            # Computed ROCE uses EBIT as operating_profit.
            # Precomputed/stated ROCE comes from companies.roce_percentage.
            try:
                stated_row = pd.read_sql_query(
                    "SELECT roce_percentage FROM companies WHERE company_id = ?", conn2, params=[cid]
                )
                roce_stated = None if stated_row.empty else _safe_float(stated_row.iloc[0].get("roce_percentage"))
            except Exception:
                roce_stated = None

            roce_computed = None
            if roce_stated is not None:
                if operating_profit is not None:
                    roce_computed = return_on_capital_employed(
                        ebit=float(operating_profit),
                        equity_capital=float(equity_capital or 0),
                        reserves=float(reserves or 0),
                        borrowings=float(borrowings or 0),
                    )

            if roce_stated is not None and roce_computed is not None:
                diff_abs = abs(float(roce_computed) - float(roce_stated))
                if diff_abs > 5.0:
                    EDGE_CASE_LOG_PATH.parent.mkdir(exist_ok=True)
                    with EDGE_CASE_LOG_PATH.open("a", encoding="utf-8") as f:
                        f.write(
                            f"{cid},{year},{roce_stated:.6f},{roce_computed:.6f},{diff_abs:.6f}\n"
                        )

            # D/E YoY change: positive means D/E improved (declined)
            de_yoy_change_pct = None
            if borrowings is not None:
                # Find previous year's D/E for this company
                prev_row = df[df["year"] < year].sort_values("year")
                if not prev_row.empty:
                    prev_de = debt_to_equity(
                        borrowings=float(prev_row.iloc[-1].get("borrowings") or 0),
                        equity_capital=float(prev_row.iloc[-1].get("equity_capital") or 0),
                        reserves=float(prev_row.iloc[-1].get("reserves") or 0),
                    )
                    curr_de = debt_to_equity(
                        borrowings=float(borrowings or 0),
                        equity_capital=float(equity_capital or 0),
                        reserves=float(reserves or 0),
                    )
                    if prev_de is not None and curr_de is not None and prev_de != 0:
                        de_yoy_change_pct = ((prev_de - curr_de) / prev_de) * 100.0

            row_out = {
                "company_id": cid,
                "year": year,

                "net_profit_margin_pct": net_profit_margin(net_profit=float(net_profit), sales=float(sales))
                if sales not in (None, 0) and net_profit is not None
                else None,
                "operating_profit_margin_pct": operating_profit_margin(
                    operating_profit=float(operating_profit), sales=float(sales)
                )
                if sales not in (None, 0) and operating_profit is not None
                else None,
                "return_on_equity_pct": return_on_equity(
                    net_profit=float(net_profit),
                    equity_capital=float(equity_capital or 0),
                    reserves=float(reserves or 0),
                )
                if net_profit is not None
                else None,
                "debt_to_equity": debt_to_equity(
                    borrowings=float(borrowings or 0),
                    equity_capital=float(equity_capital or 0),
                    reserves=float(reserves or 0),
                )
                if borrowings is not None
                else None,
                "interest_coverage": interest_coverage_ratio(
                    operating_profit=float(operating_profit or 0),
                    other_income=float(other_income or 0),
                    interest=float(interest or 0),
                )
                if interest is not None
                else None,
                "asset_turnover": asset_turnover(
                    sales=float(sales or 0),
                    total_assets=float(total_assets or 0),
                )
                if sales is not None
                else None,
                "free_cash_flow_cr": free_cash_flow_cr,
                "fcf_conversion_rate_pct": fcf_conversion_rate_pct,
                "cash_from_operations_cr": operating_activity,
                "capex_cr": capex_cr,
                "earnings_per_share": eps,
                "book_value_per_share": None,
                "dividend_payout_ratio_pct": dividend_payout_ratio_pct,
                "total_debt_cr": borrowings,
                "revenue_cagr_3yr": cagr_revenue_3yr,
                "de_yoy_change_pct": de_yoy_change_pct,
                "revenue_cagr_5yr": cagr_revenue_5yr,
                "pat_cagr_5yr": cagr_pat_5yr,
                "eps_cagr_5yr": cagr_eps_5yr,
                "fcf_cagr_5yr": cagr_fcf_5yr,
                "composite_quality_score": composite_quality_score_v2(
                    roe_pct=return_on_equity(
                        net_profit=float(net_profit),
                        equity_capital=float(equity_capital or 0),
                        reserves=float(reserves or 0),
                    ) if net_profit is not None else None,
                    roce_pct=roce_computed,
                    npm_pct=net_profit_margin(net_profit=float(net_profit), sales=float(sales))
                    if sales not in (None, 0) and net_profit is not None else None,
                    fcf_cagr_5yr=cagr_fcf_5yr,
                    cfo_pat_ratio=cfo_quality,
                    fcf_value=free_cash_flow_cr,
                    revenue_cagr_5yr=cagr_revenue_5yr,
                    pat_cagr_5yr=cagr_pat_5yr,
                    debt_to_equity=debt_to_equity(
                        borrowings=float(borrowings or 0),
                        equity_capital=float(equity_capital or 0),
                        reserves=float(reserves or 0),
                    ) if borrowings is not None else None,
                    interest_coverage=interest_coverage_ratio(
                        operating_profit=float(operating_profit or 0),
                        other_income=float(other_income or 0),
                        interest=float(interest or 0),
                    ) if interest is not None else None,
                ),
            }

            ratios_rows.append(row_out)

    out_df = pd.DataFrame(ratios_rows)

    conn2 = sqlite3.connect(db_path)
    if not out_df.empty:
        conn2.execute("PRAGMA foreign_keys = ON")
        cols_existing = {r[1] for r in conn2.execute("PRAGMA table_info(financial_ratios)")}
        cols = [c for c in out_df.columns if c in cols_existing and c not in ("company_id", "year")]

        for _, r in out_df.iterrows():
            values = [r.get(c) for c in cols]
            placeholders = ",".join(["?"] * (len(cols) + 2))
            sql = f"""
                INSERT OR REPLACE INTO financial_ratios (company_id, year, {','.join(cols)})
                VALUES ({placeholders})
            """
            conn2.execute(sql, [r["company_id"], int(r["year"]), *values])
        conn2.commit()

    conn2.close()
    return db_path

