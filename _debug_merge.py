import sqlite3
import pandas as pd

conn = sqlite3.connect('nifty100.db')

# Test the exact query from the engine
query = """
    SELECT
        fr.company_id,
        fr.year,
        fr.net_profit_margin_pct,
        fr.operating_profit_margin_pct,
        fr.return_on_equity_pct,
        fr.debt_to_equity,
        fr.interest_coverage,
        fr.asset_turnover,
        fr.free_cash_flow_cr,
        fr.fcf_conversion_rate_pct,
        fr.cash_from_operations_cr,
        fr.capex_cr,
        fr.earnings_per_share,
        fr.book_value_per_share,
        fr.dividend_payout_ratio_pct,
        fr.total_debt_cr,
        fr.revenue_cagr_5yr,
        fr.pat_cagr_5yr,
        fr.eps_cagr_5yr,
        fr.composite_quality_score,
        s.broad_sector
    FROM financial_ratios fr
    LEFT JOIN sectors s ON fr.company_id = s.company_id
    WHERE fr.year = (
        SELECT MAX(year) FROM financial_ratios fr2
        WHERE fr2.company_id = fr.company_id
    )
    ORDER BY fr.company_id, fr.year DESC
"""

df = pd.read_sql_query(query, conn)
print("Loaded financial_ratios data:")
print(f"  Shape: {df.shape}")
print(f"  Columns: {list(df.columns)}")
print(f"  year dtype: {df['year'].dtype}")
print(f"  Sample year values: {df['year'].unique()[:5]}")
print(f"  Sample year types: {[type(v).__name__ for v in df['year'].unique()[:5]]}")

# Now load market_cap data
query2 = """
    SELECT
        company_id,
        year,
        market_cap_crore,
        pe_ratio,
        pb_ratio,
        dividend_yield_pct,
        ev_ebitda,
        enterprise_value_crore
    FROM market_cap
    WHERE year = (
        SELECT MAX(year) FROM market_cap mc2
        WHERE mc2.company_id = market_cap.company_id
    )
    ORDER BY company_id, year DESC
"""

df_mc = pd.read_sql_query(query2, conn)
print("\nLoaded market_cap data:")
print(f"  Shape: {df_mc.shape}")
print(f"  year dtype: {df_mc['year'].dtype}")
print(f"  Sample year values: {df_mc['year'].unique()[:5]}")

# Try merging
print("\nAttempting merge...")
try:
    result = df.merge(df_mc, on=["company_id", "year"], how="left")
    print(f"Merge successful! Result shape: {result.shape}")
except Exception as e:
    print(f"Merge failed: {e}")
