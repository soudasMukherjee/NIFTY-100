import sqlite3
from pathlib import Path

DB = Path("c:/nifty100_sprint1/nifty100.db")
conn = sqlite3.connect(str(DB))
cur = conn.cursor()

print("== companies without any financial_ratios rows ==")
rows = cur.execute(
    """
    SELECT c.company_id FROM companies c
    WHERE NOT EXISTS (SELECT 1 FROM financial_ratios fr WHERE fr.company_id = c.company_id)
    ORDER BY c.company_id
    """
).fetchall()
print("  count:", len(rows))
for r in rows:
    print("  ", r)

print("\n== For ABB fiscal 2024: int row vs text row values ==")
rows = cur.execute(
    """
    SELECT year, typeof(year), return_on_equity_pct, net_profit_margin_pct, debt_to_equity,
           free_cash_flow_cr, composite_quality_score, revenue_cagr_5yr, revenue_cagr_3yr, de_yoy_change_pct
    FROM financial_ratios
    WHERE company_id = 'ABB' AND CAST(year AS INTEGER) IN (2023, 2024)
    """
).fetchall()
for r in rows:
    print("  ", r)

print("\n== Compare text vs int row metric agreement across all (latest year per company) ==")
rows = cur.execute(
    """
    SELECT fr.company_id,
           fr.year, typeof(fr.year) AS ty,
           fr.return_on_equity_pct, fr.composite_quality_score
    FROM financial_ratios fr
    WHERE fr.year IN ('Mar 2024','Sep 2024','Dec 2024') OR fr.year = 2024
    ORDER BY fr.company_id, typeof(fr.year)
    LIMIT 40
    """
).fetchall()
for r in rows:
    print("  ", r)

print("\n== documents distinct companies count ==")
print("  ", cur.execute("SELECT COUNT(DISTINCT company_id) FROM documents").fetchone()[0])

print("\n== prosandcons distinct companies ==")
print("  ", cur.execute("SELECT COUNT(DISTINCT company_id) FROM prosandcons").fetchone()[0])

print("\n== companies with peer group assignment ==")
print("  ", cur.execute("SELECT COUNT(DISTINCT company_id) FROM peer_groups").fetchone()[0])

print("\n== market_cap distinct companies ==")
print("  ", cur.execute("SELECT COUNT(DISTINCT company_id) FROM market_cap").fetchone()[0])

conn.close()

