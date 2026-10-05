import sqlite3
from pathlib import Path

DB = Path("c:/nifty100_sprint1/nifty100.db")
conn = sqlite3.connect(str(DB))
cur = conn.cursor()

print("== 1. Do ALL int-year rows have composite_quality_score? ==")
missing = cur.execute(
    "SELECT COUNT(*) FROM financial_ratios WHERE typeof(year)='integer' AND composite_quality_score IS NULL"
).fetchone()[0]
total_int = cur.execute("SELECT COUNT(*) FROM financial_ratios WHERE typeof(year)='integer'").fetchone()[0]
print(f"  int rows={total_int}, int rows missing composite={missing}")

print("\n== 2. Text rows with CAGR (should be 0) ==")
for col in ["revenue_cagr_5yr", "pat_cagr_5yr", "eps_cagr_5yr", "composite_quality_score", "revenue_cagr_3yr", "de_yoy_change_pct"]:
    n = cur.execute(f"SELECT COUNT(*) FROM financial_ratios WHERE typeof(year)='text' AND {col} IS NOT NULL").fetchone()[0]
    print(f"  text rows with {col}: {n}")

print("\n== 3. After deleting text rows, distinct (company_id) coverage ==")
n_companies_with_int = cur.execute(
    "SELECT COUNT(DISTINCT company_id) FROM financial_ratios WHERE typeof(year)='integer'"
).fetchone()[0]
print("  companies with int rows:", n_companies_with_int)

print("\n== 4. Year coverage after cleanup (per year, distinct companies) ==")
rows = cur.execute(
    """
    SELECT year, COUNT(DISTINCT company_id) FROM financial_ratios
    WHERE typeof(year)='integer' GROUP BY year ORDER BY year
    """
).fetchall()
for r in rows:
    print("  ", r)

print("\n== 5. Check py deps ==")
for mod in ["matplotlib", "numpy", "openpyxl", "yaml", "plotly"]:
    try:
        __import__(mod)
        print(f"  {mod}: OK")
    except ImportError as e:
        print(f"  {mod}: MISSING ({e})")

conn.close()

