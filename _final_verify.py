import sqlite3
from pathlib import Path

DB = Path("c:/nifty100_sprint1/nifty100.db")
conn = sqlite3.connect(str(DB))
cur = conn.cursor()

print("== cashflow null activity values ==")
for col in ["operating_activity", "investing_activity", "financing_activity"]:
    n = cur.execute(f"SELECT COUNT(*) FROM cashflow WHERE {col} IS NULL").fetchone()[0]
    print(f"  {col} NULL count: {n}")

print("\n== cashflow sample for SBIN (has cf but no bs) ==")
for r in cur.execute("SELECT company_id, year, operating_activity, investing_activity, financing_activity FROM cashflow WHERE company_id='SBIN' LIMIT 5").fetchall():
    print("  ", r)

print("\n== ATGL / SBIN financial_ratios ==")
for cid in ("ATGL", "SBIN"):
    n = cur.execute("SELECT COUNT(*) FROM financial_ratios WHERE company_id=?", (cid,)).fetchone()[0]
    print(f"  {cid}: {n} rows")

print("\n== valuation summary flag distribution ==")
import pandas as pd
try:
    v = pd.read_excel("c:/nifty100_sprint1/output/valuation_summary.xlsx")
    print("  columns:", list(v.columns))
    print("  rows:", len(v))
    print("  flag counts:", v["flag"].value_counts().to_dict())
    print("  companies covered:", v["company_id"].nunique())
    print(v[["company_id", "sector", "P/E", "FCF_yield_pct", "flag"]].head(8))
except Exception as e:
    print("  ERROR reading valuation:", e)

conn.close()

