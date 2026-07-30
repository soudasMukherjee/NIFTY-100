from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "nifty100.db"
OUTPUT_DIR = ROOT / "output"


def export_capital_allocation_csv(db_path: Path = DB_PATH, out_dir: Path = OUTPUT_DIR) -> Path:
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "capital_allocation.csv"

    conn = sqlite3.connect(db_path)

    # We need company_id/year and signs of CFO/CFI/CFF.
    # CFO <- cashflow.operating_activity
    # CFI <- cashflow.investing_activity
    # CFF <- cashflow.financing_activity
    df = pd.read_sql_query(
        """
        SELECT company_id, year,
               operating_activity as cfo,
               investing_activity as cfi,
               financing_activity as cff
        FROM cashflow
        """,
        conn,
    )

    # Optional: CFO Quality Score requires 5-year sequences, but sprint request only
    # says "(+,-,-) with high CFO/PAT".
    # We compute CFO Quality Score per company for each (company_id, year) using
    # the trailing 5 years ending at that year.
    # This is a best-effort implementation that matches the classifier refinement.
    df = df.sort_values(["company_id", "year"]).reset_index(drop=True)

    # Build quick trailing 5-year PAT from profitandloss.
    pat = pd.read_sql_query(
        """
        SELECT company_id, year, net_profit as pat
        FROM profitandloss
        """,
        conn,
    )
    conn.close()

    merged = df.merge(pat, on=["company_id", "year"], how="left")

    # Compute cfo_quality_score for the trailing window ending at each row.
    # None if any PAT==0 in window.
    def cfo_quality_for_index(g: pd.DataFrame) -> pd.Series:
        years = 5
        g = g.sort_values("year")
        out = []
        cfo_vals = g["cfo"].tolist()
        pat_vals = g["pat"].tolist()
        for i in range(len(g)):
            if i + 1 < years:
                out.append(None)
                continue
            cfo_window = cfo_vals[i + 1 - years : i + 1]
            pat_window = pat_vals[i + 1 - years : i + 1]
            if any(float(p) == 0.0 for p in pat_window):
                out.append(None)
                continue
            ratios = [float(c) / float(p) for c, p in zip(cfo_window, pat_window)]
            out.append(sum(ratios) / float(years))
        return pd.Series(out, index=g.index)

    merged["cfo_quality_score"] = merged.groupby("company_id", group_keys=False).apply(cfo_quality_for_index)

    from src.analytics.capital_allocation import classify_capital_allocation_patterns

    rows = merged.rename(columns={"cfo": "cfo", "cfi": "cfi", "cff": "cff"}).to_dict(orient="records")
    classified = classify_capital_allocation_patterns(
        rows=rows,
    )

    pd.DataFrame(classified).to_csv(out_path, index=False)
    return out_path


if __name__ == "__main__":
    p = export_capital_allocation_csv()
    print(f"Wrote {p}")

