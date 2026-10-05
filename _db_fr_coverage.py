import sqlite3
from pathlib import Path

DB = Path("c:/nifty100_sprint1/nifty100.db")
conn = sqlite3.connect(str(DB))
cur = conn.cursor()

print("== Companies with int row year=2024 vs text 'Mar/Sep/Dec 2024' ==")
int_2024 = cur.execute("SELECT COUNT(DISTINCT company_id) FROM financial_ratios WHERE year = 2024").fetchone()[0]
text_2024 = cur.execute("SELECT COUNT(DISTINCT company_id) FROM financial_ratios WHERE year IN ('Mar 2024','Sep 2024','Dec 2024')").fetchone()[0]
print("  companies with int 2024:", int_2024)
print("  companies with text 2024:", text_2024)

print("\n== Latest fiscal year per company considering ONLY int rows ==")
rows = cur.execute(
    "SELECT company_id, MAX(year) AS latest FROM financial_ratios WHERE typeof(year)='integer' GROUP BY company_id ORDER BY company_id"
).fetchall()
latest_counts = {}
for cid, y in rows:
    latest_counts[y] = latest_counts.get(y, 0) + 1
print("  distribution:", latest_counts)

print("\n== Companies whose latest int year < 2024 ==")
for cid, y in rows:
    if y < 2024:
        print("  ", cid, y)

print("\n== Do text rows have composite_quality_score / CAGR populated? ==")
rows = cur.execute(
    "SELECT COUNT(*) FROM financial_ratios WHERE typeof(year)='text' AND composite_quality_score IS NOT NULL"
).fetchone()[0]
print("  text rows with composite score:", rows)
rows = cur.execute(
    "SELECT COUNT(*) FROM financial_ratios WHERE typeof(year)='text' AND revenue_cagr_5yr IS NOT NULL"
).fetchone()[0]
print("  text rows with revenue_cagr_5yr:", rows)
rows = cur.execute(
    "SELECT COUNT(*) FROM financial_ratios WHERE typeof(year)='text' AND net_profit_margin_pct IS NOT NULL"
).fetchone()[0]
print("  text rows with npm:", rows)
rows = cur.execute(
    "SELECT COUNT(*) FROM financial_ratios WHERE typeof(year)='text' AND free_cash_flow_cr IS NOT NULL"
).fetchone()[0]
print("  text rows with fcf:", rows)

print("\n== For a sample text row (ABB 'Mar 2024'), all columns ==")
row = cur.execute(
    "SELECT * FROM financial_ratios WHERE company_id='ABB' AND year='Mar 2024'"
).fetchone()
cols = [d[0] for d in cur.description]
for c, v in zip(cols, row):
    if v is not None:
        print("    ", c, "=", v)

print("\n== ATGL / SBIN PL/BS/CF availability ==")
for cid in ("ATGL", "SBIN"):
    pl = cur.execute("SELECT COUNT(*) FROM profitandloss WHERE company_id=?", (cid,)).fetchone()[0]
    bs = cur.execute("SELECT COUNT(*) FROM balancesheet WHERE company_id=?", (cid,)).fetchone()[0]
    cf = cur.execute("SELECT COUNT(*) FROM cashflow WHERE company_id=?", (cid,)).fetchone()[0]
    mc = cur.execute("SELECT COUNT(*) FROM market_cap WHERE company_id=?", (cid,)).fetchone()[0]
    sec = cur.execute("SELECT COUNT(*) FROM sectors WHERE company_id=?", (cid,)).fetchone()[0]
    print(f"  {cid}: pl={pl} bs={bs} cf={cf} mc={mc} sectors={sec}")

print("\n== companies with market_cap but last int fr year pre-2024 ==")
for cid, y in rows:
    if y < 2024:
        has_mc = cur.execute("SELECT COUNT(*) FROM market_cap WHERE company_id=? AND year=2024", (cid,)).fetchone()[0]
        has_text = cur.execute("SELECT COUNT(*) FROM financial_ratios WHERE company_id=? AND year LIKE '%2024'", (cid,)).fetchone()[0]
        print(f"  {cid}: latest int={y} mc2024={has_mc} text2024={has_text}")

conn.close()

