import pandas as pd
from pathlib import Path

SUPP = Path("c:/nifty100_sprint1/data/supporting")

for fname in ["financial_ratios.xlsx", "market_cap.xlsx", "peer_groups.xlsx", "sectors.xlsx"]:
    path = SUPP / fname
    print(f"\n===== {fname} =====")
    df = pd.read_excel(path)
    print("  shape:", df.shape)
    print("  columns:", list(df.columns))
    if "year" in df.columns:
        print("  year dtype:", df["year"].dtype)
        print("  year sample:", df["year"].head(8).tolist())
        print("  year unique count:", df["year"].nunique())
        print("  year unique sample:", sorted(df["year"].astype(str).unique())[:10])
    if "company_id" in df.columns:
        print("  company_id nunique:", df["company_id"].nunique())

