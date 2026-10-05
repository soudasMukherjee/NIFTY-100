import sys
from pathlib import Path

ROOT = Path("c:/nifty100_sprint1")
sys.path.insert(0, str(ROOT))

try:
    from src.dashboard.utils import db

    print("DB_PATH:", db.DB_PATH)
    print("DB_PATH exists:", db.DB_PATH.exists())
    try:
        companies = db.get_companies()
        print("get_companies OK, rows:", len(companies))
    except Exception as exc:
        print("get_companies FAILED:", type(exc).__name__, exc)
except Exception as exc:
    print("IMPORT FAILED:", type(exc).__name__, exc)

