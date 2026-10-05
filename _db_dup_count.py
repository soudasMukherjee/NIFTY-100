import sqlite3
from pathlib import Path

DB = Path("c:/nifty100_sprint1/nifty100.db")
conn = sqlite3.connect(str(DB))
cur = conn.cursor()

print("-- distinct (company_id, fiscal_year) pairs --")
distinct_pairs = cur.execute(
    "SELECT COUNT(*) FROM (SELECT DISTINCT company_id, CAST(year AS INTEGER) FROM financial_ratios)"
).fetchone()[0]
print("  distinct pairs:", distinct_pairs)
print("  total rows:", cur.execute("SELECT COUNT(*) FROM financial_ratios").fetchone()[0])

print("\n-- companies with duplicate fiscal years (count of years repeated) --")
dup = cur.execute(
    """
    SELECT company_id, fy, COUNT(*) AS cnt
    FROM (SELECT company_id, CAST(year AS INTEGER) AS fy FROM financial_ratios)
    GROUP BY company_id, fy
    HAVING COUNT(*) > 1
    ORDER BY company_id, fy
    """
).fetchall()
print("  duplicate rows total:", len(dup))
print("  sample:", dup[:15])

print("\n-- how many companies affected --")
affected = cur.execute(
    """
    SELECT COUNT(*) FROM (
        SELECT company_id FROM (SELECT company_id, CAST(year AS INTEGER) AS fy FROM financial_ratios)
        GROUP BY company_id, fy HAVING COUNT(*) > 1
    )
    """
).fetchone()[0]
print("  companies with any duplicate fiscal year:", affected)

print("\n-- latest year (fiscal) distribution per company using int rows --")
rows = cur.execute(
    """
    SELECT company_id, MAX(CAST(year AS INTEGER)) AS latest
    FROM financial_ratios
    GROUP BY company_id
    ORDER BY latest DESC
    LIMIT 15
    """
).fetchall()
for r in rows:
    print("  ", r)

conn.close()

