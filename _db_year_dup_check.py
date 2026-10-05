import sqlite3
from pathlib import Path

DB = Path("c:/nifty100_sprint1/nifty100.db")
conn = sqlite3.connect(str(DB))
cur = conn.cursor()

print("-- ABB all years (mixed) --")
rows = cur.execute(
    "SELECT year, typeof(year), COUNT(*) FROM financial_ratios WHERE company_id='ABB' GROUP BY year, typeof(year) ORDER BY CAST(year AS INTEGER)"
).fetchall()
for r in rows:
    print("  ", r)

print("\n-- Companies having BOTH int and text year for same fiscal year --")
rows = cur.execute(
    """
    SELECT a.company_id, a.fy
    FROM (
        SELECT company_id, CAST(year AS INTEGER) AS fy FROM financial_ratios
        GROUP BY company_id, CAST(year AS INTEGER)
    ) a
    GROUP BY a.company_id, a.fy
    HAVING COUNT(*) > 1
    LIMIT 20
    """
).fetchall()
for r in rows:
    print("  ", r)
print("  total companies with dup fiscal year:", len(rows))

print("\n-- overall: total rows, int rows, text rows --")
print("  total:", cur.execute("SELECT COUNT(*) FROM financial_ratios").fetchone()[0])
print("  int rows:", cur.execute("SELECT COUNT(*) FROM financial_ratios WHERE typeof(year)='integer'").fetchone()[0])
print("  text rows:", cur.execute("SELECT COUNT(*) FROM financial_ratios WHERE typeof(year)='text'").fetchone()[0])

print("\n-- companies with ONLY text years (no int rows at all) --")
rows = cur.execute(
    """
    SELECT c.company_id,
           (SELECT COUNT(*) FROM financial_ratios fr WHERE fr.company_id=c.company_id AND typeof(fr.year)='text') AS text_cnt,
           (SELECT COUNT(*) FROM financial_ratios fr WHERE fr.company_id=c.company_id AND typeof(fr.year)='integer') AS int_cnt
    FROM companies c
    WHERE (SELECT COUNT(*) FROM financial_ratios fr WHERE fr.company_id=c.company_id AND typeof(fr.year)='integer') = 0
      AND (SELECT COUNT(*) FROM financial_ratios fr WHERE fr.company_id=c.company_id) > 0
    ORDER BY c.company_id
    """
).fetchall()
print("  count:", len(rows))
for r in rows:
    print("  ", r)

print("\n-- companies having int rows (any) --")
rows = cur.execute(
    """
    SELECT COUNT(DISTINCT company_id) FROM financial_ratios WHERE typeof(year)='integer'
    """
).fetchone()
print("  ", rows)

conn.close()

