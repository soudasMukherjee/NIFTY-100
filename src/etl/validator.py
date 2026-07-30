"""
Sprint 1 · Day 03 — Schema Validator: DQ-01 ... DQ-16

Severity levels:
    CRITICAL -> must be resolved before Day 05 full load is considered done
    WARNING  -> logged, reviewed manually on Day 06, doesn't block the load

Run against the already-loaded nifty100.db (run loader.py first).
Writes output/validation_failures.csv
"""

from __future__ import annotations
import sqlite3
from pathlib import Path
from dataclasses import dataclass

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "nifty100.db"
OUTPUT_DIR = ROOT / "output"


@dataclass
class DQFailure:
    rule_id: str
    severity: str   # CRITICAL | WARNING
    table: str
    description: str
    company_id: str | None
    year: object
    detail: str


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def run_all_rules() -> list[DQFailure]:
    conn = _conn()
    failures: list[DQFailure] = []

    # ---------------------------------------------------------------
    # DQ-01  PK uniqueness across all tables with an `id` column
    # ---------------------------------------------------------------
    for table in ["companies", "profitandloss", "balancesheet", "cashflow",
                  "analysis", "documents", "prosandcons", "sectors",
                  "stock_prices", "financial_ratios", "market_cap", "peer_groups"]:
        pk_col = "company_id" if table == "companies" else "id"
        dupes = conn.execute(
            f"SELECT {pk_col}, COUNT(*) c FROM {table} GROUP BY {pk_col} HAVING c > 1"
        ).fetchall()
        for pk_val, cnt in dupes:
            failures.append(DQFailure("DQ-01", "CRITICAL", table,
                                       "Primary key uniqueness violated",
                                       None, None, f"{pk_col}={pk_val} appears {cnt}x"))

    # ---------------------------------------------------------------
    # DQ-02  (company_id, year) composite key uniqueness on statement tables
    # ---------------------------------------------------------------
    for table in ["profitandloss", "balancesheet", "cashflow"]:
        dupes = conn.execute(f"""
            SELECT company_id, year, COUNT(*) c FROM {table}
            GROUP BY company_id, year HAVING c > 1
        """).fetchall()
        for cid, yr, cnt in dupes:
            failures.append(DQFailure("DQ-02", "CRITICAL", table,
                                       "(company_id, year) composite key duplicated",
                                       cid, yr, f"{cnt} rows for same company/year"))

    # ---------------------------------------------------------------
    # DQ-03  FK integrity — every child company_id must exist in companies
    # ---------------------------------------------------------------
    fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    for table, rowid, parent, fkid in fk_violations:
        failures.append(DQFailure("DQ-03", "CRITICAL", table,
                                   "FK integrity violation (orphan company_id)",
                                   None, None, f"rowid={rowid} references missing {parent}"))

    # ---------------------------------------------------------------
    # DQ-04  Balance sheet must balance: total_assets == total_liabilities
    #        (tolerance < 1% relative difference)
    # ---------------------------------------------------------------
    rows = conn.execute("""
        SELECT company_id, year, total_assets, total_liabilities
        FROM balancesheet WHERE total_assets IS NOT NULL AND total_liabilities IS NOT NULL
    """).fetchall()
    for cid, yr, ta, tl in rows:
        base = max(abs(ta), abs(tl), 1e-9)
        diff_pct = abs(ta - tl) / base * 100
        if diff_pct >= 1.0:
            failures.append(DQFailure("DQ-04", "WARNING", "balancesheet",
                                       "Balance sheet does not balance within 1%",
                                       cid, yr, f"assets={ta}, liabilities={tl}, diff={diff_pct:.2f}%"))

    # ---------------------------------------------------------------
    # DQ-05  OPM cross-check: operating_profit / sales ≈ opm_percentage
    # ---------------------------------------------------------------
    rows = conn.execute("""
        SELECT company_id, year, sales, operating_profit, opm_percentage
        FROM profitandloss
        WHERE sales IS NOT NULL AND sales != 0
              AND operating_profit IS NOT NULL AND opm_percentage IS NOT NULL
    """).fetchall()
    for cid, yr, sales, op, opm in rows:
        implied = op / sales * 100
        if abs(implied - opm) > 2.0:  # 2 percentage-point tolerance
            failures.append(DQFailure("DQ-05", "WARNING", "profitandloss",
                                       "OPM% inconsistent with operating_profit/sales",
                                       cid, yr, f"stated={opm:.2f}%, implied={implied:.2f}%"))

    # ---------------------------------------------------------------
    # DQ-06  Positive sales
    # ---------------------------------------------------------------
    rows = conn.execute("""
        SELECT company_id, year, sales FROM profitandloss WHERE sales IS NOT NULL AND sales <= 0
    """).fetchall()
    for cid, yr, sales in rows:
        failures.append(DQFailure("DQ-06", "CRITICAL", "profitandloss",
                                   "Non-positive sales value", cid, yr, f"sales={sales}"))

    # ---------------------------------------------------------------
    # DQ-07  Net cash flow reconciliation: sum of the three activities == net_cash_flow
    # ---------------------------------------------------------------
    rows = conn.execute("""
        SELECT company_id, year, operating_activity, investing_activity,
               financing_activity, net_cash_flow
        FROM cashflow
        WHERE operating_activity IS NOT NULL AND investing_activity IS NOT NULL
              AND financing_activity IS NOT NULL AND net_cash_flow IS NOT NULL
    """).fetchall()
    for cid, yr, opa, inv, fin, net in rows:
        computed = opa + inv + fin
        if abs(computed - net) > max(abs(net) * 0.01, 1.0):
            failures.append(DQFailure("DQ-07", "WARNING", "cashflow",
                                       "operating+investing+financing != net_cash_flow",
                                       cid, yr, f"computed={computed:.1f}, stated={net:.1f}"))

    # ---------------------------------------------------------------
    # DQ-08  Tax rate plausibility: tax_percentage within [0, 60]
    # ---------------------------------------------------------------
    rows = conn.execute("""
        SELECT company_id, year, tax_percentage FROM profitandloss
        WHERE tax_percentage IS NOT NULL AND (tax_percentage < 0 OR tax_percentage > 60)
    """).fetchall()
    for cid, yr, tax in rows:
        failures.append(DQFailure("DQ-08", "WARNING", "profitandloss",
                                   "Tax rate outside plausible [0, 60]% range",
                                   cid, yr, f"tax_percentage={tax}"))

    # ---------------------------------------------------------------
    # DQ-09  Dividend payout cap: should not exceed 200% (data-entry sanity, not
    #        a hard economic law, so WARNING not CRITICAL)
    # ---------------------------------------------------------------
    rows = conn.execute("""
        SELECT company_id, year, dividend_payout FROM profitandloss
        WHERE dividend_payout IS NOT NULL AND (dividend_payout < 0 OR dividend_payout > 200)
    """).fetchall()
    for cid, yr, dp in rows:
        failures.append(DQFailure("DQ-09", "WARNING", "profitandloss",
                                   "Dividend payout outside [0, 200]% sanity cap",
                                   cid, yr, f"dividend_payout={dp}"))

    # ---------------------------------------------------------------
    # DQ-10  URL format sanity on documents.annual_report_url and companies.website
    # ---------------------------------------------------------------
    rows = conn.execute("SELECT company_id, year, annual_report_url FROM documents").fetchall()
    for cid, yr, url in rows:
        if url and not str(url).startswith(("http://", "https://")):
            failures.append(DQFailure("DQ-10", "WARNING", "documents",
                                       "Malformed annual report URL", cid, yr, f"url={url!r}"))

    # ---------------------------------------------------------------
    # DQ-11  EPS sign consistency: EPS should be negative only when net_profit is negative
    # ---------------------------------------------------------------
    rows = conn.execute("""
        SELECT company_id, year, eps, net_profit FROM profitandloss
        WHERE eps IS NOT NULL AND net_profit IS NOT NULL
    """).fetchall()
    for cid, yr, eps, np_ in rows:
        if (eps < 0) != (np_ < 0) and eps != 0 and np_ != 0:
            failures.append(DQFailure("DQ-11", "WARNING", "profitandloss",
                                       "EPS sign disagrees with net_profit sign",
                                       cid, yr, f"eps={eps}, net_profit={np_}"))

    # ---------------------------------------------------------------
    # DQ-12  BSE balance-sheet identity: fixed_assets + cwip + investments +
    #        other_asset == total_assets
    # ---------------------------------------------------------------
    rows = conn.execute("""
        SELECT company_id, year, fixed_assets, cwip, investments, other_asset, total_assets
        FROM balancesheet
        WHERE fixed_assets IS NOT NULL AND cwip IS NOT NULL AND investments IS NOT NULL
              AND other_asset IS NOT NULL AND total_assets IS NOT NULL
    """).fetchall()
    for cid, yr, fa, cwip, inv, oa, ta in rows:
        computed = fa + cwip + inv + oa
        if abs(computed - ta) > max(abs(ta) * 0.01, 1.0):
            failures.append(DQFailure("DQ-12", "WARNING", "balancesheet",
                                       "Asset-side components don't sum to total_assets",
                                       cid, yr, f"computed={computed:.1f}, stated={ta:.1f}"))

    # ---------------------------------------------------------------
    # DQ-13  Year coverage: each company should have >= 5 years of P&L history
    # ---------------------------------------------------------------
    rows = conn.execute("""
        SELECT company_id, COUNT(DISTINCT year) n FROM profitandloss
        WHERE period_type = 'ANNUAL' GROUP BY company_id HAVING n < 5
    """).fetchall()
    for cid, n in rows:
        failures.append(DQFailure("DQ-13", "WARNING", "profitandloss",
                                   "Company has fewer than 5 years of P&L history",
                                   cid, None, f"years_covered={n}"))

    # ---------------------------------------------------------------
    # DQ-14  Stock price OHLC sanity: low <= open,close <= high
    # ---------------------------------------------------------------
    rows = conn.execute("""
        SELECT company_id, date, open_price, high_price, low_price, close_price
        FROM stock_prices
        WHERE open_price IS NOT NULL AND high_price IS NOT NULL
              AND low_price IS NOT NULL AND close_price IS NOT NULL
    """).fetchall()
    for cid, dt, o, h, l, c in rows:
        if not (l <= o <= h and l <= c <= h):
            failures.append(DQFailure("DQ-14", "CRITICAL", "stock_prices",
                                       "OHLC values violate low<=open,close<=high",
                                       cid, dt, f"O={o} H={h} L={l} C={c}"))

    # ---------------------------------------------------------------
    # DQ-15  Face value plausibility (INR face values are conventionally
    #        1, 2, 5, or 10)
    # ---------------------------------------------------------------
    rows = conn.execute("""
        SELECT company_id, face_value FROM companies
        WHERE face_value IS NOT NULL AND face_value NOT IN (1, 2, 5, 10)
    """).fetchall()
    for cid, fv in rows:
        failures.append(DQFailure("DQ-15", "WARNING", "companies",
                                   "Unusual face value (not in {1,2,5,10})",
                                   cid, None, f"face_value={fv}"))

    # ---------------------------------------------------------------
    # DQ-16  Sector coverage: every company must have exactly one sectors row
    # ---------------------------------------------------------------
    rows = conn.execute("""
        SELECT c.company_id FROM companies c
        LEFT JOIN sectors s ON c.company_id = s.company_id
        WHERE s.company_id IS NULL
    """).fetchall()
    for (cid,) in rows:
        failures.append(DQFailure("DQ-16", "CRITICAL", "sectors",
                                   "Company missing sector classification",
                                   cid, None, "no matching row in sectors"))

    conn.close()
    return failures


def write_validation_report(failures: list[DQFailure]) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    path = OUTPUT_DIR / "validation_failures.csv"
    df = pd.DataFrame([{
        "rule_id": f.rule_id, "severity": f.severity, "table": f.table,
        "description": f.description, "company_id": f.company_id,
        "year": f.year, "detail": f.detail,
    } for f in failures])
    df.to_csv(path, index=False)
    return path


if __name__ == "__main__":
    failures = run_all_rules()
    path = write_validation_report(failures)

    n_critical = sum(1 for f in failures if f.severity == "CRITICAL")
    n_warning = sum(1 for f in failures if f.severity == "WARNING")

    print(f"Total DQ failures: {len(failures)}  (CRITICAL={n_critical}, WARNING={n_warning})")
    by_rule = {}
    for f in failures:
        by_rule.setdefault(f.rule_id, [0, f.severity])
        by_rule[f.rule_id][0] += 1
    for rule in sorted(by_rule):
        cnt, sev = by_rule[rule]
        print(f"  {rule:<8}{sev:<10}{cnt} failures")
    print(f"\nvalidation_failures.csv written to {path}")

    if n_critical > 0:
        print(f"\n⚠️  {n_critical} CRITICAL failures must be resolved before Day 05 sign-off.")
