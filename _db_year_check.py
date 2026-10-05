import sqlite3
from pathlib import Path

DB = Path("c:/nifty100_sprint1/nifty100.db")
conn = sqlite3.connect(str(DB))
cur = conn.cursor()

print("-- companies with string-type years in financial_ratios --")
rows = cur.execute(
    "SELECT company_id, year FROM financial_ratios WHERE typeof(year) = 'text' ORDER BY company_id LIMIT 30"
).fetchall()
print(rows, "count:", len(rows))
companies_with_str = [r[0] for r in rows]

print("\n-- distinct textual year values --")
for r in cur.execute("SELECT DISTINCT year FROM financial_ratios WHERE typeof(year) = 'text' ORDER BY year").fetchall():
    print("  ", repr(r[0]))

print("\n-- For each company with a text year: latest year (MAX by CAST) --")
for cid in companies_with_str[:10]:
    latest = cur.execute(
        "SELECT year FROM financial_ratios WHERE company_id = ? ORDER BY CAST(year AS INTEGER) DESC LIMIT 1",
        (cid,),
    ).fetchone()
    print("  ", cid, "latest:", latest)

print("\n-- Check MAX(year) on the whole table vs CAST MAX --")
print("  MAX(year):", cur.execute("SELECT MAX(year) FROM financial_ratios").fetchone())
print("  CAST MAX:", cur.execute("SELECT MAX(CAST(year AS INTEGER)) FROM financial_ratios").fetchone())

print("\n-- profitandloss year types sample --")
for r in cur.execute("SELECT company_id, year, typeof(year) FROM profitandloss WHERE typeof(year)='text' LIMIT 5").fetchall():
    print("  ", r)

print("\n-- cashflow year types sample --")
for r in cur.execute("SELECT company_id, year, typeof(year) FROM cashflow WHERE typeof(year)='text' LIMIT 5").fetchall():
    print("  ", r)

print("\n-- balancesheet year types sample --")
for r in cur.execute("SELECT company_id, year, typeof(year) FROM balancesheet WHERE typeof(year)='text' LIMIT 5").fetchall():
    print("  ", r)

print("\n-- market_cap year types sample --")
for r in cur.execute("SELECT DISTINCT typeof(year), COUNT(*) FROM market_cap GROUP BY typeof(year)").fetchall():
    print("  ", r)

print("\n-- documents year types sample --")
for r in cur.execute("SELECT DISTINCT typeof(year), COUNT(*) FROM documents GROUP BY typeof(year)").fetchall():
    print("  ", r)

conn.close()

