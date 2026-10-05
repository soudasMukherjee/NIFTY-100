"""
Quick DB checks for Day 16 planning.
"""
import sqlite3

c = sqlite3.connect('nifty100.db')

# Check P&L years per company
res = c.execute("""
    SELECT company_id, COUNT(*) as cnt, MIN(year), MAX(year) 
    FROM profitandloss WHERE period_type='ANNUAL' 
    GROUP BY company_id ORDER BY cnt
""").fetchall()
print('P&L years per company:')
for r in res[:5]:
    print(r)
print('...')
print('Total with >=3 years:', sum(1 for r in res if r[1] >= 3))
print('Total with >=5 years:', sum(1 for r in res if r[1] >= 5))

# Check distinct years
print('\nP&L distinct years:', c.execute("SELECT DISTINCT year FROM profitandloss WHERE period_type='ANNUAL' ORDER BY year").fetchall())

# Check CAGR data
print('\nCAGR sample:', c.execute("""
    SELECT company_id, year, revenue_cagr_5yr, pat_cagr_5yr 
    FROM financial_ratios WHERE revenue_cagr_5yr IS NOT NULL LIMIT 3
""").fetchall())

# Check DE sample for year-over-year
print('\nDE data for a company:', c.execute("""
    SELECT company_id, year, debt_to_equity, return_on_equity_pct, free_cash_flow_cr
    FROM financial_ratios WHERE company_id='RELIANCE' ORDER BY year
""").fetchall())

# Check what revenue CAGR 3yr we could compute from sales data
print('\nSales data sample:', c.execute("""
    SELECT company_id, year, sales FROM profitandloss 
    WHERE company_id='RELIANCE' AND period_type='ANNUAL' ORDER BY year
""").fetchall())

# Check sectors broad distribution
print('\nBroad sectors:', c.execute("SELECT broad_sector, COUNT(*) FROM sectors GROUP BY broad_sector ORDER BY COUNT(*) DESC").fetchall())

# Count companies with ratio data
print('\nCompanies with ratio data:', c.execute("SELECT COUNT(DISTINCT company_id) FROM financial_ratios").fetchone()[0])

# Check dividend_yield data
print('\nDividend yield sample:', c.execute("""
    SELECT company_id, year, dividend_yield_pct 
    FROM market_cap WHERE dividend_yield_pct IS NOT NULL AND dividend_yield_pct > 1 
    LIMIT 5
""").fetchall())

c.close()
print("\nDone.")

