"""
Sprint 1 · Day 02 & Day 05 — Excel Loader
Loads all 12 source files (7 core + 5 supplementary) into nifty100.db,
applying normaliser.py transforms, and writes output/load_audit.csv.

Load order matters because of FK constraints:
    1. companies            (no dependencies — must load first)
    2. profitandloss
    3. balancesheet
    4. cashflow
    5. analysis
    6. documents
    7. prosandcons
    8. sectors
    9. stock_prices
    10. financial_ratios
    11. market_cap
    12. peer_groups
"""

from __future__ import annotations
import sqlite3
import sys
from pathlib import Path
from dataclasses import dataclass, field

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from normaliser import (
    normalize_year,
    normalize_ticker,
    parse_horizon_metric,
    NormalisationError,
)

ROOT = Path(__file__).resolve().parents[2]
CORE_DIR = ROOT / "data" / "core"
SUPP_DIR = ROOT / "data" / "supporting"
DB_PATH = ROOT / "nifty100.db"
SCHEMA_PATH = ROOT / "db" / "schema.sql"
OUTPUT_DIR = ROOT / "output"


@dataclass
class LoadResult:
    table: str
    source_file: str
    rows_in_source: int = 0
    rows_loaded: int = 0
    rows_rejected: int = 0
    rejection_reasons: list = field(default_factory=list)

    @property
    def status(self) -> str:
        return "OK" if self.rows_rejected == 0 else "REVIEW"


def build_schema(conn: sqlite3.Connection) -> None:
    sql = SCHEMA_PATH.read_text()
    conn.executescript(sql)
    conn.commit()


# ------------------------------------------------------------------
# 1. companies
# ------------------------------------------------------------------
def load_companies(conn) -> LoadResult:
    df = pd.read_excel(CORE_DIR / "companies.xlsx", header=1)
    res = LoadResult("companies", "companies.xlsx", rows_in_source=len(df))

    rows = []
    for _, r in df.iterrows():
        try:
            cid = normalize_ticker(r["id"])
        except NormalisationError as e:
            res.rows_rejected += 1
            res.rejection_reasons.append(f"row id={r['id']!r}: {e}")
            continue
        rows.append((
            cid, r["company_name"], r.get("company_logo"), r.get("chart_link"),
            r.get("about_company"), r.get("website"), r.get("nse_profile"),
            r.get("bse_profile"), r.get("face_value"), r.get("book_value"),
            r.get("roce_percentage"), r.get("roe_percentage"),
        ))

    conn.executemany(
        """INSERT OR REPLACE INTO companies
           (company_id, company_name, company_logo, chart_link, about_company,
            website, nse_profile, bse_profile, face_value, book_value,
            roce_percentage, roe_percentage)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    res.rows_loaded = len(rows)
    return res


# ------------------------------------------------------------------
# 2-4. profitandloss / balancesheet / cashflow (share the same shape of logic)
# ------------------------------------------------------------------
_STATEMENT_COLS = {
    "profitandloss": [
        "sales", "expenses", "operating_profit", "opm_percentage", "other_income",
        "interest", "depreciation", "profit_before_tax", "tax_percentage",
        "net_profit", "eps", "dividend_payout",
    ],
    "balancesheet": [
        "equity_capital", "reserves", "borrowings", "other_liabilities",
        "total_liabilities", "fixed_assets", "cwip", "investments",
        "other_asset", "total_assets",
    ],
    "cashflow": [
        "operating_activity", "investing_activity", "financing_activity",
        "net_cash_flow",
    ],
}

_FILE_MAP = {
    "profitandloss": "profitandloss.xlsx",
    "balancesheet": "balancesheet.xlsx",
    "cashflow": "cashflow.xlsx",
}


def load_statement_table(conn, table: str, valid_company_ids: set[str]) -> LoadResult:
    fname = _FILE_MAP[table]
    df = pd.read_excel(CORE_DIR / fname, header=1)
    res = LoadResult(table, fname, rows_in_source=len(df))

    value_cols = _STATEMENT_COLS[table]
    has_period_type = table != "cashflow"

    rows = []
    for _, r in df.iterrows():
        try:
            cid = normalize_ticker(r["company_id"])
        except NormalisationError as e:
            res.rows_rejected += 1
            res.rejection_reasons.append(f"id={r.get('id')}: bad ticker {r['company_id']!r}: {e}")
            continue

        if cid not in valid_company_ids:
            res.rows_rejected += 1
            res.rejection_reasons.append(f"id={r.get('id')}: FK violation, company_id={cid} not in companies")
            continue

        try:
            year, period_type = normalize_year(r["year"])
        except NormalisationError as e:
            res.rows_rejected += 1
            res.rejection_reasons.append(f"id={r.get('id')}: bad year {r['year']!r}: {e}")
            continue

        values = tuple(r.get(c) for c in value_cols)
        if has_period_type:
            rows.append((int(r["id"]), cid, str(r["year"]), year, period_type, *values))
        else:
            rows.append((int(r["id"]), cid, str(r["year"]), year, *values))

    if has_period_type:
        placeholders = ",".join(["?"] * (5 + len(value_cols)))
        conn.executemany(
            f"""INSERT OR REPLACE INTO {table}
                (id, company_id, year_raw, year, period_type, {",".join(value_cols)})
                VALUES ({placeholders})""",
            rows,
        )
    else:
        placeholders = ",".join(["?"] * (4 + len(value_cols)))
        conn.executemany(
            f"""INSERT OR REPLACE INTO {table}
                (id, company_id, year_raw, year, {",".join(value_cols)})
                VALUES ({placeholders})""",
            rows,
        )

    res.rows_loaded = len(rows)
    return res


# ------------------------------------------------------------------
# 5. analysis  (embedded-text horizon/pct columns)
# ------------------------------------------------------------------
def load_analysis(conn, valid_company_ids: set[str]) -> LoadResult:
    df = pd.read_excel(CORE_DIR / "analysis.xlsx", header=1)
    res = LoadResult("analysis", "analysis.xlsx", rows_in_source=len(df))

    rows = []
    for _, r in df.iterrows():
        try:
            cid = normalize_ticker(r["company_id"])
        except NormalisationError as e:
            res.rows_rejected += 1
            res.rejection_reasons.append(f"id={r.get('id')}: bad ticker: {e}")
            continue
        if cid not in valid_company_ids:
            res.rows_rejected += 1
            res.rejection_reasons.append(f"id={r.get('id')}: FK violation, company_id={cid}")
            continue

        sg_y, sg_p = parse_horizon_metric(r.get("compounded_sales_growth"))
        pg_y, pg_p = parse_horizon_metric(r.get("compounded_profit_growth"))
        sc_y, sc_p = parse_horizon_metric(r.get("stock_price_cagr"))
        roe_y, roe_p = parse_horizon_metric(r.get("roe"))

        rows.append((int(r["id"]), cid, sg_y, sg_p, pg_y, pg_p, sc_y, sc_p, roe_y, roe_p))

    conn.executemany(
        """INSERT OR REPLACE INTO analysis
           (id, company_id, sales_growth_years, sales_growth_pct,
            profit_growth_years, profit_growth_pct, stock_cagr_years,
            stock_cagr_pct, roe_years, roe_pct)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    res.rows_loaded = len(rows)
    return res


# ------------------------------------------------------------------
# 6. documents
# ------------------------------------------------------------------
def load_documents(conn, valid_company_ids: set[str]) -> LoadResult:
    df = pd.read_excel(CORE_DIR / "documents.xlsx", header=1)
    res = LoadResult("documents", "documents.xlsx", rows_in_source=len(df))

    rows = []
    for _, r in df.iterrows():
        try:
            cid = normalize_ticker(r["company_id"])
        except NormalisationError as e:
            res.rows_rejected += 1
            res.rejection_reasons.append(f"id={r.get('id')}: bad ticker: {e}")
            continue
        if cid not in valid_company_ids:
            res.rows_rejected += 1
            res.rejection_reasons.append(f"id={r.get('id')}: FK violation, company_id={cid}")
            continue
        try:
            year = int(r["Year"])
        except (ValueError, TypeError):
            res.rows_rejected += 1
            res.rejection_reasons.append(f"id={r.get('id')}: bad year {r.get('Year')!r}")
            continue

        rows.append((int(r["id"]), cid, year, r.get("Annual_Report")))

    conn.executemany(
        "INSERT OR REPLACE INTO documents (id, company_id, year, annual_report_url) VALUES (?,?,?,?)",
        rows,
    )
    res.rows_loaded = len(rows)
    return res


# ------------------------------------------------------------------
# 7. prosandcons
# ------------------------------------------------------------------
def load_prosandcons(conn, valid_company_ids: set[str]) -> LoadResult:
    df = pd.read_excel(CORE_DIR / "prosandcons.xlsx", header=1)
    res = LoadResult("prosandcons", "prosandcons.xlsx", rows_in_source=len(df))

    rows = []
    for _, r in df.iterrows():
        try:
            cid = normalize_ticker(r["company_id"])
        except NormalisationError as e:
            res.rows_rejected += 1
            res.rejection_reasons.append(f"id={r.get('id')}: bad ticker: {e}")
            continue
        if cid not in valid_company_ids:
            res.rows_rejected += 1
            res.rejection_reasons.append(f"id={r.get('id')}: FK violation, company_id={cid}")
            continue
        rows.append((int(r["id"]), cid, r.get("pros"), r.get("cons")))

    conn.executemany(
        "INSERT OR REPLACE INTO prosandcons (id, company_id, pros, cons) VALUES (?,?,?,?)",
        rows,
    )
    res.rows_loaded = len(rows)
    return res


# ------------------------------------------------------------------
# 8-12. supplementary datasets (already clean id/company_id/year columns)
# ------------------------------------------------------------------
def load_simple_supplementary(conn, table: str, fname: str, cols: list[str],
                               valid_company_ids: set[str]) -> LoadResult:
    df = pd.read_excel(SUPP_DIR / fname)
    res = LoadResult(table, fname, rows_in_source=len(df))

    rows = []
    for _, r in df.iterrows():
        try:
            cid = normalize_ticker(r["company_id"])
        except NormalisationError as e:
            res.rows_rejected += 1
            res.rejection_reasons.append(f"id={r.get('id')}: bad ticker: {e}")
            continue
        if cid not in valid_company_ids:
            res.rows_rejected += 1
            res.rejection_reasons.append(f"id={r.get('id')}: FK violation, company_id={cid}")
            continue
        values = [r.get(c) for c in cols]
        rows.append((int(r["id"]), cid, *values))

    placeholders = ",".join(["?"] * (2 + len(cols)))
    conn.executemany(
        f"INSERT OR REPLACE INTO {table} (id, company_id, {','.join(cols)}) VALUES ({placeholders})",
        rows,
    )
    res.rows_loaded = len(rows)
    return res


def load_peer_groups(conn, valid_company_ids: set[str]) -> LoadResult:
    df = pd.read_excel(SUPP_DIR / "peer_groups.xlsx")
    res = LoadResult("peer_groups", "peer_groups.xlsx", rows_in_source=len(df))

    rows = []
    for _, r in df.iterrows():
        try:
            cid = normalize_ticker(r["company_id"])
        except NormalisationError as e:
            res.rows_rejected += 1
            res.rejection_reasons.append(f"id={r.get('id')}: bad ticker: {e}")
            continue
        if cid not in valid_company_ids:
            res.rows_rejected += 1
            res.rejection_reasons.append(f"id={r.get('id')}: FK violation, company_id={cid}")
            continue
        rows.append((int(r["id"]), r["peer_group_name"], cid, int(bool(r.get("is_benchmark", 0)))))

    conn.executemany(
        "INSERT OR REPLACE INTO peer_groups (id, peer_group_name, company_id, is_benchmark) VALUES (?,?,?,?)",
        rows,
    )
    res.rows_loaded = len(rows)
    return res


# ------------------------------------------------------------------
# Orchestration
# ------------------------------------------------------------------
def run_full_load() -> list[LoadResult]:
    OUTPUT_DIR.mkdir(exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    build_schema(conn)

    results = []

    r = load_companies(conn); results.append(r); conn.commit()
    valid_ids = {row[0] for row in conn.execute("SELECT company_id FROM companies")}

    for table in ("profitandloss", "balancesheet", "cashflow"):
        r = load_statement_table(conn, table, valid_ids); results.append(r); conn.commit()

    results.append(load_analysis(conn, valid_ids)); conn.commit()
    results.append(load_documents(conn, valid_ids)); conn.commit()
    results.append(load_prosandcons(conn, valid_ids)); conn.commit()

    results.append(load_simple_supplementary(
        conn, "sectors", "sectors.xlsx",
        ["broad_sector", "sub_sector", "index_weight_pct", "market_cap_category"],
        valid_ids)); conn.commit()

    results.append(load_simple_supplementary(
        conn, "stock_prices", "stock_prices.xlsx",
        ["date", "open_price", "high_price", "low_price", "close_price",
         "volume", "adjusted_close"],
        valid_ids)); conn.commit()

    results.append(load_simple_supplementary(
        conn, "financial_ratios", "financial_ratios.xlsx",
        ["year", "net_profit_margin_pct", "operating_profit_margin_pct",
         "return_on_equity_pct", "debt_to_equity", "interest_coverage",
         "asset_turnover", "free_cash_flow_cr", "capex_cr",
         "earnings_per_share", "book_value_per_share",
         "dividend_payout_ratio_pct", "total_debt_cr"],
        valid_ids)); conn.commit()

    results.append(load_simple_supplementary(
        conn, "market_cap", "market_cap.xlsx",
        ["year", "market_cap_crore", "enterprise_value_crore", "pe_ratio",
         "pb_ratio", "ev_ebitda", "dividend_yield_pct"],
        valid_ids)); conn.commit()

    results.append(load_peer_groups(conn, valid_ids)); conn.commit()

    conn.close()
    return results


def write_load_audit(results: list[LoadResult]) -> Path:
    audit_path = OUTPUT_DIR / "load_audit.csv"
    df = pd.DataFrame([{
        "table": r.table,
        "source_file": r.source_file,
        "rows_in_source": r.rows_in_source,
        "rows_loaded": r.rows_loaded,
        "rows_rejected": r.rows_rejected,
        "status": r.status,
        "rejection_sample": " | ".join(r.rejection_reasons[:3]),
    } for r in results])
    df.to_csv(audit_path, index=False)
    return audit_path


def fk_check(db_path: Path = DB_PATH) -> list:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    rows = conn.execute("PRAGMA foreign_key_check").fetchall()
    conn.close()
    return rows


if __name__ == "__main__":
    results = run_full_load()
    audit_path = write_load_audit(results)

    print(f"{'table':<18}{'source':<16}{'in':>7}{'loaded':>9}{'rejected':>10}  status")
    for r in results:
        print(f"{r.table:<18}{r.rows_in_source:>7}{r.rows_loaded:>9}{r.rows_rejected:>10}  {r.status}")

    fk_violations = fk_check()
    print(f"\nPRAGMA foreign_key_check -> {len(fk_violations)} violations")
    print(f"load_audit.csv written to {audit_path}")
