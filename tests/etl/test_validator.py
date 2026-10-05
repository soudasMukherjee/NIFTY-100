"""
Sprint 3 · Day 21 — DQ Rule Unit Tests (DQ-01 .. DQ-16)

Unit tests for `src/etl/validator.py` covering all 14 DQ rules (DQ-01..DQ-14)
plus DQ-15/DQ-16. Each test builds an in-memory SQLite database with a clean
baseline, then mutates it to trigger a specific data-quality violation and
asserts `run_all_rules()` flags the correct rule id.

Because `run_all_rules()` is hard-wired to the real `nifty100.db`, the
`validator._conn` factory is monkeypatched to return the in-memory connection.

Run: pytest tests/etl/test_validator.py -v
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest

# Make `src/` importable when running tests from repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from src.etl import validator
from src.etl.validator import DQFailure, run_all_rules, write_validation_report


# ============================================================
# In-memory database factory
# ============================================================
def _build_clean_db(db_path: Path | None = None) -> sqlite3.Connection:
    """
    Build a clean SQLite DB mirroring the production schema.

    Tables are created WITHOUT primary-key/unique constraints so that
    duplicate-row violations can be inserted for DQ-01 / DQ-02 tests.
    Foreign-key clauses ARE declared so PRAGMA foreign_key_check (DQ-03)
    is meaningful.  Foreign keys are left OFF at insert time (matching the
    default) and only enabled by the monkeypatched `_conn`.

    If `db_path` is given, a file-backed DB is created there (so multiple
    connections can be opened to the same data); otherwise an in-memory DB
    is created.
    """
    conn = sqlite3.connect(str(db_path) if db_path is not None else ":memory:")
    cur = conn.cursor()

    # --- companies (master) ---
    # company_id must be PRIMARY KEY so child-table FKs are valid in SQLite.
    cur.execute("""
        CREATE TABLE companies (
            company_id TEXT PRIMARY KEY, company_name TEXT, website TEXT,
            face_value REAL, book_value REAL,
            roce_percentage REAL, roe_percentage REAL
        )
    """)

    # --- profitandloss ---
    cur.execute("""
        CREATE TABLE profitandloss (
            id INTEGER, company_id TEXT, year_raw TEXT, year INTEGER,
            period_type TEXT, sales REAL, expenses REAL, operating_profit REAL,
            opm_percentage REAL, other_income REAL, interest REAL,
            depreciation REAL, profit_before_tax REAL, tax_percentage REAL,
            net_profit REAL, eps REAL, dividend_payout REAL,
            FOREIGN KEY (company_id) REFERENCES companies(company_id)
        )
    """)

    # --- balancesheet ---
    cur.execute("""
        CREATE TABLE balancesheet (
            id INTEGER, company_id TEXT, year_raw TEXT, year INTEGER,
            period_type TEXT, equity_capital REAL, reserves REAL,
            borrowings REAL, other_liabilities REAL, total_liabilities REAL,
            fixed_assets REAL, cwip REAL, investments REAL, other_asset REAL,
            total_assets REAL,
            FOREIGN KEY (company_id) REFERENCES companies(company_id)
        )
    """)

    # --- cashflow ---
    cur.execute("""
        CREATE TABLE cashflow (
            id INTEGER, company_id TEXT, year_raw TEXT, year INTEGER,
            operating_activity REAL, investing_activity REAL,
            financing_activity REAL, net_cash_flow REAL,
            FOREIGN KEY (company_id) REFERENCES companies(company_id)
        )
    """)

    # --- analysis ---
    cur.execute("""
        CREATE TABLE analysis (
            id INTEGER, company_id TEXT, sales_growth_years INTEGER,
            sales_growth_pct REAL, profit_growth_years INTEGER,
            profit_growth_pct REAL, stock_cagr_years INTEGER,
            stock_cagr_pct REAL, roe_years INTEGER, roe_pct REAL,
            FOREIGN KEY (company_id) REFERENCES companies(company_id)
        )
    """)

    # --- documents ---
    cur.execute("""
        CREATE TABLE documents (
            id INTEGER, company_id TEXT, year INTEGER, annual_report_url TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(company_id)
        )
    """)

    # --- prosandcons ---
    cur.execute("""
        CREATE TABLE prosandcons (
            id INTEGER, company_id TEXT, pros TEXT, cons TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(company_id)
        )
    """)

    # --- sectors ---
    cur.execute("""
        CREATE TABLE sectors (
            id INTEGER, company_id TEXT, broad_sector TEXT, sub_sector TEXT,
            index_weight_pct REAL, market_cap_category TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(company_id)
        )
    """)

    # --- stock_prices ---
    cur.execute("""
        CREATE TABLE stock_prices (
            id INTEGER, company_id TEXT, date TEXT, open_price REAL,
            high_price REAL, low_price REAL, close_price REAL,
            volume INTEGER, adjusted_close REAL,
            FOREIGN KEY (company_id) REFERENCES companies(company_id)
        )
    """)

    # --- financial_ratios ---
    cur.execute("""
        CREATE TABLE financial_ratios (
            id INTEGER, company_id TEXT, year INTEGER,
            net_profit_margin_pct REAL, operating_profit_margin_pct REAL,
            return_on_equity_pct REAL, debt_to_equity REAL,
            interest_coverage REAL, asset_turnover REAL,
            free_cash_flow_cr REAL, fcf_conversion_rate_pct REAL,
            cash_from_operations_cr REAL, capex_cr REAL,
            earnings_per_share REAL, book_value_per_share REAL,
            dividend_payout_ratio_pct REAL, total_debt_cr REAL,
            revenue_cagr_3yr REAL, de_yoy_change_pct REAL,
            revenue_cagr_5yr REAL, pat_cagr_5yr REAL, eps_cagr_5yr REAL,
            fcf_cagr_5yr REAL, composite_quality_score REAL,
            FOREIGN KEY (company_id) REFERENCES companies(company_id)
        )
    """)

    # --- market_cap ---
    cur.execute("""
        CREATE TABLE market_cap (
            id INTEGER, company_id TEXT, year INTEGER,
            market_cap_crore REAL, enterprise_value_crore REAL,
            pe_ratio REAL, pb_ratio REAL, ev_ebitda REAL,
            dividend_yield_pct REAL,
            FOREIGN KEY (company_id) REFERENCES companies(company_id)
        )
    """)

    # --- peer_groups ---
    cur.execute("""
        CREATE TABLE peer_groups (
            id INTEGER, peer_group_name TEXT, company_id TEXT,
            is_benchmark INTEGER,
            FOREIGN KEY (company_id) REFERENCES companies(company_id)
        )
    """)

    # ---- Clean baseline data ----
    cur.execute(
        "INSERT INTO companies (company_id, company_name, website, face_value) "
        "VALUES ('C1', 'Clean Co', 'https://www.cleanco.com', 10)"
    )

    # 5 years of P&L (satisfies DQ-13), all internally consistent.
    for yr in range(2020, 2025):
        cur.execute(
            "INSERT INTO profitandloss (id, company_id, year_raw, year, period_type, "
            "sales, expenses, operating_profit, opm_percentage, other_income, "
            "interest, depreciation, profit_before_tax, tax_percentage, "
            "net_profit, eps, dividend_payout) "
            "VALUES (?, 'C1', ?, ?, 'ANNUAL', 1000, 700, 300, 30.0, 10, 5, 10, "
            "295, 25, 200, 20, 50)",
            (yr - 2019, f"Mar {yr}", yr),
        )

    cur.execute(
        "INSERT INTO balancesheet (id, company_id, year_raw, year, period_type, "
        "equity_capital, reserves, borrowings, other_liabilities, "
        "total_liabilities, fixed_assets, cwip, investments, other_asset, "
        "total_assets) VALUES (1, 'C1', 'Mar 2024', 2024, 'ANNUAL', "
        "100, 200, 50, 0, 350, 200, 50, 50, 50, 350)"
    )

    cur.execute(
        "INSERT INTO cashflow (id, company_id, year_raw, year, operating_activity, "
        "investing_activity, financing_activity, net_cash_flow) "
        "VALUES (1, 'C1', 'Mar 2024', 2024, 100, -30, -20, 50)"
    )

    cur.execute(
        "INSERT INTO analysis (id, company_id, sales_growth_years, sales_growth_pct) "
        "VALUES (1, 'C1', 5, 12.5)"
    )

    cur.execute(
        "INSERT INTO documents (id, company_id, year, annual_report_url) "
        "VALUES (1, 'C1', 2024, 'https://www.cleanco.com/ar-2024.pdf')"
    )

    cur.execute(
        "INSERT INTO prosandcons (id, company_id, pros, cons) "
        "VALUES (1, 'C1', 'good fundamentals', 'none')"
    )

    cur.execute(
        "INSERT INTO sectors (id, company_id, broad_sector, sub_sector) "
        "VALUES (1, 'C1', 'IT', 'Software')"
    )

    cur.execute(
        "INSERT INTO stock_prices (id, company_id, date, open_price, high_price, "
        "low_price, close_price, volume, adjusted_close) "
        "VALUES (1, 'C1', '2024-01-01', 100, 110, 95, 105, 100000, 105)"
    )

    cur.execute(
        "INSERT INTO financial_ratios (id, company_id, year, return_on_equity_pct, "
        "debt_to_equity, composite_quality_score) "
        "VALUES (1, 'C1', 2024, 18.0, 0.5, 75.0)"
    )

    cur.execute(
        "INSERT INTO market_cap (id, company_id, year, market_cap_crore, pe_ratio) "
        "VALUES (1, 'C1', 2024, 50000, 22.0)"
    )

    cur.execute(
        "INSERT INTO peer_groups (id, peer_group_name, company_id, is_benchmark) "
        "VALUES (1, 'IT Services', 'C1', 1)"
    )

    conn.commit()
    return conn


# ============================================================
# Fixture: monkeypatch validator._conn to return a fresh connection
# to a file-backed temp DB.  `run_all_rules()` closes the connection
# it opens, so the factory must return a NEW connection each call.
# ============================================================
@pytest.fixture
def db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_dq.db"
    _build_clean_db(db_file)

    def _fake_conn():
        conn = sqlite3.connect(str(db_file))
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    monkeypatch.setattr(validator, "_conn", _fake_conn)

    # Yield an open connection for direct mutation in the tests.
    conn = sqlite3.connect(str(db_file))
    yield conn
    conn.close()


def _rule_ids(failures: list[DQFailure]) -> set[str]:
    return {f.rule_id for f in failures}


# ============================================================
# Meta / structural tests
# ============================================================
class TestValidatorStructure:
    def test_all_16_dq_rules_are_defined_in_source(self):
        """Every DQ-01..DQ-16 rule id appears in the validator source."""
        src = Path(validator.__file__).read_text(encoding="utf-8")
        for i in range(1, 17):
            rule = f"DQ-{i:02d}"
            assert rule in src, f"{rule} missing from validator source"

    def test_dqfailure_dataclass_fields(self):
        f = DQFailure("DQ-01", "CRITICAL", "companies", "desc", "C1", 2024, "detail")
        assert f.rule_id == "DQ-01"
        assert f.severity == "CRITICAL"
        assert f.table == "companies"
        assert f.description == "desc"
        assert f.company_id == "C1"
        assert f.year == 2024
        assert f.detail == "detail"

    def test_run_all_rules_returns_dqfailure_list(self, db):
        failures = run_all_rules()
        assert isinstance(failures, list)
        for f in failures:
            assert isinstance(f, DQFailure)

    def test_clean_db_has_no_failures(self, db):
        """A clean, internally-consistent DB should pass every rule."""
        failures = run_all_rules()
        assert failures == [], f"Expected no failures, got: {failures}"

    def test_write_validation_report_creates_csv(self, db, tmp_path, monkeypatch):
        monkeypatch.setattr(validator, "OUTPUT_DIR", tmp_path)
        failures = [DQFailure("DQ-01", "CRITICAL", "companies", "dup", "C1", None, "x")]
        path = write_validation_report(failures)
        assert path.exists()
        assert path.name == "validation_failures.csv"
        df = pd.read_csv(path)
        assert len(df) == 1
        assert df.iloc[0]["rule_id"] == "DQ-01"


# ============================================================
# DQ-01  PK uniqueness
# ============================================================
class TestDQ01:
    def test_detects_duplicate_id(self, db):
        db.execute(
            "INSERT INTO profitandloss (id, company_id, year_raw, year, period_type, "
            "sales, operating_profit, opm_percentage, net_profit, eps, tax_percentage, "
            "dividend_payout) VALUES (1, 'C1', 'Mar 2025', 2025, 'ANNUAL', "
            "1000, 300, 30, 200, 20, 25, 50)"
        )
        db.commit()
        failures = run_all_rules()
        assert "DQ-01" in _rule_ids(failures)

    def test_duplicate_pk_is_critical(self, db):
        db.execute(
            "INSERT INTO profitandloss (id, company_id, year, period_type, "
            "sales, net_profit) VALUES (1, 'C1', 2025, 'ANNUAL', 1000, 200)"
        )
        db.commit()
        dq01 = [f for f in run_all_rules() if f.rule_id == "DQ-01"]
        assert dq01
        assert all(f.severity == "CRITICAL" for f in dq01)


# ============================================================
# DQ-02  (company_id, year) composite key uniqueness
# ============================================================
class TestDQ02:
    def test_detects_duplicate_company_year(self, db):
        db.execute(
            "INSERT INTO profitandloss (id, company_id, year_raw, year, period_type, "
            "sales, net_profit) VALUES (99, 'C1', 'Mar 2024', 2024, 'ANNUAL', "
            "1000, 200)"
        )
        db.commit()
        failures = run_all_rules()
        assert "DQ-02" in _rule_ids(failures)


# ============================================================
# DQ-03  FK integrity
# ============================================================
class TestDQ03:
    def test_detects_orphan_company_id(self, db):
        # Orphan inserted while FKs are OFF (sqlite default); _conn enables
        # FKs before run_all_rules runs PRAGMA foreign_key_check.
        db.execute(
            "INSERT INTO cashflow (id, company_id, year, operating_activity) "
            "VALUES (99, 'GHOST', 2024, 10)"
        )
        db.commit()
        failures = run_all_rules()
        assert "DQ-03" in _rule_ids(failures)


# ============================================================
# DQ-04  Balance sheet balances within 1%
# ============================================================
class TestDQ04:
    def test_detects_imbalanced_balance_sheet(self, db):
        db.execute(
            "UPDATE balancesheet SET total_liabilities = 100 WHERE company_id = 'C1'"
        )
        db.commit()
        failures = run_all_rules()
        assert "DQ-04" in _rule_ids(failures)

    def test_imbalance_is_warning(self, db):
        db.execute(
            "UPDATE balancesheet SET total_liabilities = 100 WHERE company_id = 'C1'"
        )
        db.commit()
        dq04 = [f for f in run_all_rules() if f.rule_id == "DQ-04"]
        assert dq04 and all(f.severity == "WARNING" for f in dq04)


# ============================================================
# DQ-05  OPM cross-check (operating_profit / sales vs opm_percentage)
# ============================================================
class TestDQ05:
    def test_detects_opm_drift(self, db):
        db.execute(
            "UPDATE profitandloss SET opm_percentage = 10 "
            "WHERE company_id = 'C1' AND year = 2024"
        )
        db.commit()
        failures = run_all_rules()
        assert "DQ-05" in _rule_ids(failures)

    def test_opm_within_tolerance_not_flagged(self, db):
        db.execute(
            "UPDATE profitandloss SET opm_percentage = 31.0 "  # implied 30, diff 1.0 <= 2.0
            "WHERE company_id = 'C1' AND year = 2024"
        )
        db.commit()
        failures = run_all_rules()
        assert "DQ-05" not in _rule_ids(failures)


# ============================================================
# DQ-06  Positive sales
# ============================================================
class TestDQ06:
    def test_detects_non_positive_sales(self, db):
        db.execute(
            "UPDATE profitandloss SET sales = -100 WHERE company_id = 'C1' AND year = 2024"
        )
        db.commit()
        failures = run_all_rules()
        assert "DQ-06" in _rule_ids(failures)

    def test_non_positive_sales_is_critical(self, db):
        db.execute(
            "UPDATE profitandloss SET sales = 0 WHERE company_id = 'C1' AND year = 2024"
        )
        db.commit()
        dq06 = [f for f in run_all_rules() if f.rule_id == "DQ-06"]
        assert dq06 and all(f.severity == "CRITICAL" for f in dq06)


# ============================================================
# DQ-07  Cash flow reconciliation
# ============================================================
class TestDQ07:
    def test_detects_cashflow_mismatch(self, db):
        db.execute(
            "UPDATE cashflow SET financing_activity = -10 WHERE company_id = 'C1'"
        )  # 100 - 30 - 10 = 60 != 50
        db.commit()
        failures = run_all_rules()
        assert "DQ-07" in _rule_ids(failures)

    def test_reconciled_cashflow_not_flagged(self, db):
        db.execute(
            "UPDATE cashflow SET financing_activity = -20 WHERE company_id = 'C1'"
        )  # 100 - 30 - 20 = 50 == 50
        db.commit()
        failures = run_all_rules()
        assert "DQ-07" not in _rule_ids(failures)


# ============================================================
# DQ-08  Tax rate within [0, 60]
# ============================================================
class TestDQ08:
    def test_detects_tax_above_range(self, db):
        db.execute(
            "UPDATE profitandloss SET tax_percentage = 75 WHERE company_id = 'C1' AND year = 2024"
        )
        db.commit()
        failures = run_all_rules()
        assert "DQ-08" in _rule_ids(failures)

    def test_detects_tax_below_range(self, db):
        db.execute(
            "UPDATE profitandloss SET tax_percentage = -5 WHERE company_id = 'C1' AND year = 2024"
        )
        db.commit()
        failures = run_all_rules()
        assert "DQ-08" in _rule_ids(failures)

    def test_tax_in_range_not_flagged(self, db):
        db.execute(
            "UPDATE profitandloss SET tax_percentage = 30 WHERE company_id = 'C1' AND year = 2024"
        )
        db.commit()
        failures = run_all_rules()
        assert "DQ-08" not in _rule_ids(failures)


# ============================================================
# DQ-09  Dividend payout within [0, 200]
# ============================================================
class TestDQ09:
    def test_detects_dividend_above_cap(self, db):
        db.execute(
            "UPDATE profitandloss SET dividend_payout = 250 WHERE company_id = 'C1' AND year = 2024"
        )
        db.commit()
        failures = run_all_rules()
        assert "DQ-09" in _rule_ids(failures)

    def test_detects_dividend_negative(self, db):
        db.execute(
            "UPDATE profitandloss SET dividend_payout = -10 WHERE company_id = 'C1' AND year = 2024"
        )
        db.commit()
        failures = run_all_rules()
        assert "DQ-09" in _rule_ids(failures)


# ============================================================
# DQ-10  URL format sanity
# ============================================================
class TestDQ10:
    def test_detects_malformed_url(self, db):
        db.execute(
            "UPDATE documents SET annual_report_url = 'not-a-valid-url' "
            "WHERE company_id = 'C1'"
        )
        db.commit()
        failures = run_all_rules()
        assert "DQ-10" in _rule_ids(failures)

    def test_http_and_https_urls_accepted(self, db):
        for url in ("http://example.com/ar.pdf", "https://example.com/ar.pdf"):
            db.execute(
                "UPDATE documents SET annual_report_url = ? WHERE company_id = 'C1'",
                (url,),
            )
            db.commit()
            failures = run_all_rules()
            assert "DQ-10" not in _rule_ids(failures)


# ============================================================
# DQ-11  EPS sign consistency with net_profit
# ============================================================
class TestDQ11:
    def test_detects_eps_sign_mismatch(self, db):
        # net_profit positive, eps negative → inconsistent
        db.execute(
            "UPDATE profitandloss SET eps = -20 WHERE company_id = 'C1' AND year = 2024"
        )
        db.commit()
        failures = run_all_rules()
        assert "DQ-11" in _rule_ids(failures)

    def test_consistent_signs_not_flagged(self, db):
        db.execute(
            "UPDATE profitandloss SET eps = 20, net_profit = 200 "
            "WHERE company_id = 'C1' AND year = 2024"
        )
        db.commit()
        failures = run_all_rules()
        assert "DQ-11" not in _rule_ids(failures)


# ============================================================
# DQ-12  Asset-side components sum to total_assets
# ============================================================
class TestDQ12:
    def test_detects_asset_side_mismatch(self, db):
        db.execute(
            "UPDATE balancesheet SET cwip = 10 WHERE company_id = 'C1'"
        )  # 200+10+50+50 = 310 != 350
        db.commit()
        failures = run_all_rules()
        assert "DQ-12" in _rule_ids(failures)

    def test_asset_side_matches_not_flagged(self, db):
        db.execute(
            "UPDATE balancesheet SET cwip = 50 WHERE company_id = 'C1'"
        )  # 200+50+50+50 = 350 == 350
        db.commit()
        failures = run_all_rules()
        assert "DQ-12" not in _rule_ids(failures)


# ============================================================
# DQ-13  Each company has >= 5 years of P&L history
# ============================================================
class TestDQ13:
    def test_detects_few_years_of_history(self, db):
        # Add C2 with only 2 years of P&L history (and a sector row so DQ-16
        # doesn't fire and confuse the assertion).
        db.execute(
            "INSERT INTO companies (company_id, company_name, face_value) "
            "VALUES ('C2', 'Young Co', 10)"
        )
        db.execute(
            "INSERT INTO sectors (id, company_id, broad_sector) VALUES (2, 'C2', 'FMCG')"
        )
        for i, yr in enumerate((2023, 2024), start=10):
            db.execute(
                "INSERT INTO profitandloss (id, company_id, year_raw, year, period_type, "
                "sales, operating_profit, opm_percentage, net_profit, eps, "
                "tax_percentage, dividend_payout) VALUES (?, 'C2', ?, ?, 'ANNUAL', "
                "500, 100, 20, 50, 5, 25, 30)",
                (i, f"Mar {yr}", yr),
            )
        db.commit()
        failures = run_all_rules()
        assert "DQ-13" in _rule_ids(failures)

    def test_company_with_5_years_not_flagged(self, db):
        failures = run_all_rules()
        assert "DQ-13" not in _rule_ids(failures)


# ============================================================
# DQ-14  Stock price OHLC sanity (low <= open,close <= high)
# ============================================================
class TestDQ14:
    def test_detects_open_above_high(self, db):
        db.execute(
            "UPDATE stock_prices SET open_price = 120 WHERE company_id = 'C1'"
        )  # 120 > high 110
        db.commit()
        failures = run_all_rules()
        assert "DQ-14" in _rule_ids(failures)

    def test_detects_close_below_low(self, db):
        db.execute(
            "UPDATE stock_prices SET close_price = 90 WHERE company_id = 'C1'"
        )  # 90 < low 95
        db.commit()
        failures = run_all_rules()
        assert "DQ-14" in _rule_ids(failures)

    def test_ohlc_violation_is_critical(self, db):
        db.execute(
            "UPDATE stock_prices SET open_price = 120 WHERE company_id = 'C1'"
        )
        db.commit()
        dq14 = [f for f in run_all_rules() if f.rule_id == "DQ-14"]
        assert dq14 and all(f.severity == "CRITICAL" for f in dq14)


# ============================================================
# DQ-15  Face value plausibility {1, 2, 5, 10}
# ============================================================
class TestDQ15:
    def test_detects_unusual_face_value(self, db):
        db.execute("UPDATE companies SET face_value = 7 WHERE company_id = 'C1'")
        db.commit()
        failures = run_all_rules()
        assert "DQ-15" in _rule_ids(failures)

    def test_common_face_values_not_flagged(self, db):
        for fv in (1, 2, 5, 10):
            db.execute("UPDATE companies SET face_value = ? WHERE company_id = 'C1'", (fv,))
            db.commit()
            failures = run_all_rules()
            assert "DQ-15" not in _rule_ids(failures)


# ============================================================
# DQ-16  Sector coverage — every company has exactly one sector
# ============================================================
class TestDQ16:
    def test_detects_missing_sector(self, db):
        db.execute(
            "INSERT INTO companies (company_id, company_name, face_value) "
            "VALUES ('C3', 'No Sector Co', 10)"
        )
        db.commit()
        failures = run_all_rules()
        assert "DQ-16" in _rule_ids(failures)

    def test_sector_coverage_ok_not_flagged(self, db):
        failures = run_all_rules()
        assert "DQ-16" not in _rule_ids(failures)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

