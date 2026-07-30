"""
Sprint 1 · Day 06 — Data Quality Manual Review
Pulls 5 random companies and prints their P&L year coverage so a human
can eyeball correctness against the source Excel before Day 07 sign-off.
"""
import random
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "nifty100.db"


def main(seed: int = 42, n: int = 5):
    conn = sqlite3.connect(DB_PATH)
    all_ids = [r[0] for r in conn.execute("SELECT company_id FROM companies")]
    random.seed(seed)
    sample = random.sample(all_ids, n)

    print(f"Manual review sample (seed={seed}): {sample}\n")
    for cid in sample:
        name = conn.execute(
            "SELECT company_name FROM companies WHERE company_id = ?", (cid,)
        ).fetchone()[0]
        years = [r[0] for r in conn.execute(
            "SELECT DISTINCT year FROM profitandloss WHERE company_id = ? AND period_type='ANNUAL' ORDER BY year",
            (cid,),
        )]
        n_bs = conn.execute(
            "SELECT COUNT(*) FROM balancesheet WHERE company_id = ?", (cid,)
        ).fetchone()[0]
        n_cf = conn.execute(
            "SELECT COUNT(*) FROM cashflow WHERE company_id = ?", (cid,)
        ).fetchone()[0]
        flag = "  <-- fewer than 5 years, review loader" if len(years) < 5 else ""
        print(f"{cid:<14}{name:<35}P&L years: {years}{flag}")
        print(f"{'':<14}{'':<35}BS rows: {n_bs}  CF rows: {n_cf}\n")

    conn.close()


if __name__ == "__main__":
    main()
