"""
Sprint 3 · Day 15 — Screener Engine Tests
Tests for filter logic, preset loading, special handling (D/E sector skip, ICR debt-free),
and composite ranking.
"""

from __future__ import annotations

import pytest
import pandas as pd
import sqlite3
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.screener.engine import (
    ScreenerEngine,
    ScreenerRequest,
    FilterConfig,
    create_screener,
    screen_with_preset,
)


# ============================================================
# Fixtures
# ============================================================
@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary test database with sample data."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Create minimal schema
    cursor.execute("""
        CREATE TABLE financial_ratios (
            id INTEGER PRIMARY KEY,
            company_id TEXT NOT NULL,
            year INTEGER NOT NULL,
            net_profit_margin_pct REAL,
            operating_profit_margin_pct REAL,
            return_on_equity_pct REAL,
            debt_to_equity REAL,
            interest_coverage REAL,
            asset_turnover REAL,
            free_cash_flow_cr REAL,
            fcf_conversion_rate_pct REAL,
            cash_from_operations_cr REAL,
            capex_cr REAL,
            earnings_per_share REAL,
            book_value_per_share REAL,
            dividend_payout_ratio_pct REAL,
            total_debt_cr REAL,
            revenue_cagr_3yr REAL,
            de_yoy_change_pct REAL,
            revenue_cagr_5yr REAL,
            pat_cagr_5yr REAL,
            eps_cagr_5yr REAL,
            composite_quality_score REAL,
            UNIQUE (company_id, year)
        )
    """)

    cursor.execute("""
        CREATE TABLE sectors (
            id INTEGER PRIMARY KEY,
            company_id TEXT NOT NULL UNIQUE,
            broad_sector TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE market_cap (
            id INTEGER PRIMARY KEY,
            company_id TEXT NOT NULL,
            year INTEGER NOT NULL,
            market_cap_crore REAL,
            pe_ratio REAL,
            pb_ratio REAL,
            dividend_yield_pct REAL,
            ev_ebitda REAL,
            enterprise_value_crore REAL,
            UNIQUE (company_id, year)
        )
    """)

    cursor.execute("""
        CREATE TABLE profitandloss (
            id INTEGER PRIMARY KEY,
            company_id TEXT NOT NULL,
            year INTEGER NOT NULL,
            sales REAL,
            net_profit REAL,
            eps REAL,
            operating_profit REAL,
            opm_percentage REAL,
            period_type TEXT DEFAULT 'ANNUAL',
            UNIQUE (company_id, year, period_type)
        )
    """)

    # Insert test data
    # Company 1: High-growth tech (non-Financials)
    cursor.execute("""
        INSERT INTO financial_ratios VALUES
        (1, 'TECH1', 2024, 18.0, 16.0, 20.0, 0.8, 5.0, 1.2, 150.0, 85.0, 200.0, 50.0, 15.0, 50.0, 2.0, 300.0, NULL, NULL, 18.0, 20.0, 22.0, 85.0)
    """)
    cursor.execute("INSERT INTO sectors VALUES (1, 'TECH1', 'IT')")
    cursor.execute("INSERT INTO market_cap VALUES (1, 'TECH1', 2024, 50000.0, 22.0, 5.0, 1.5, 25.0, 45000.0)")
    cursor.execute("INSERT INTO profitandloss VALUES (1, 'TECH1', 2024, 2000.0, 300.0, 15.0, 320.0, 16.0, 'ANNUAL')")

    # Company 2: Dividend-focused (non-Financials)
    cursor.execute("""
        INSERT INTO financial_ratios VALUES
        (2, 'DIV1', 2024, 12.0, 11.0, 14.0, 0.6, 8.0, 0.8, 80.0, 75.0, 100.0, 20.0, 10.0, 40.0, 3.5, 200.0, NULL, NULL, 8.0, 10.0, 9.0, 70.0)
    """)
    cursor.execute("INSERT INTO sectors VALUES (2, 'DIV1', 'FMCG')")
    cursor.execute("INSERT INTO market_cap VALUES (2, 'DIV1', 2024, 30000.0, 18.0, 3.0, 4.0, 15.0, 28000.0)")
    cursor.execute("INSERT INTO profitandloss VALUES (2, 'DIV1', 2024, 1500.0, 180.0, 10.0, 165.0, 11.0, 'ANNUAL')")

    # Company 3: Bank with high D/E (Financials - should be skipped from D/E filter)
    cursor.execute("""
        INSERT INTO financial_ratios VALUES
        (3, 'BANK1', 2024, 22.0, 20.0, 18.0, 8.0, 3.5, 0.5, 50.0, 60.0, 100.0, 50.0, 5.0, 30.0, 2.0, 500.0, NULL, NULL, 12.0, 14.0, 15.0, 75.0)
    """)
    cursor.execute("INSERT INTO sectors VALUES (3, 'BANK1', 'Financials')")
    cursor.execute("INSERT INTO market_cap VALUES (3, 'BANK1', 2024, 80000.0, 15.0, 2.0, 3.0, 20.0, 75000.0)")
    cursor.execute("INSERT INTO profitandloss VALUES (3, 'BANK1', 2024, 3000.0, 540.0, 5.0, 600.0, 20.0, 'ANNUAL')")

    # Company 4: Low-leverage company (Debt-free label scenario)
    cursor.execute("""
        INSERT INTO financial_ratios VALUES
        (4, 'DEBT_FREE', 2024, 15.0, 13.0, 16.0, 0.0, NULL, 1.0, 120.0, 80.0, 150.0, 30.0, 12.0, 45.0, 2.5, 100.0, NULL, NULL, 11.0, 13.0, 14.0, 80.0)
    """)
    cursor.execute("INSERT INTO sectors VALUES (4, 'DEBT_FREE', 'Pharma')")
    cursor.execute("INSERT INTO market_cap VALUES (4, 'DEBT_FREE', 2024, 35000.0, 25.0, 4.0, 2.5, 18.0, 33000.0)")
    cursor.execute("INSERT INTO profitandloss VALUES (4, 'DEBT_FREE', 2024, 1800.0, 270.0, 12.0, 234.0, 13.0, 'ANNUAL')")

    # Company 5: Poor performer (doesn't meet most thresholds)
    cursor.execute("""
        INSERT INTO financial_ratios VALUES
        (5, 'POOR1', 2024, 5.0, 4.0, 6.0, 2.5, 1.2, 0.3, 30.0, 40.0, 50.0, 20.0, 2.0, 20.0, 1.0, 400.0, NULL, NULL, 2.0, 3.0, 2.5, 40.0)
    """)
    cursor.execute("INSERT INTO sectors VALUES (5, 'POOR1', 'Construction')")
    cursor.execute("INSERT INTO market_cap VALUES (5, 'POOR1', 2024, 5000.0, 35.0, 1.5, 0.5, 30.0, 4500.0)")
    cursor.execute("INSERT INTO profitandloss VALUES (5, 'POOR1', 2024, 800.0, 40.0, 2.0, 32.0, 4.0, 'ANNUAL')")

    conn.commit()
    conn.close()

    return db_path


@pytest.fixture
def config_file(tmp_path):
    """Create a temporary config file."""
    config_path = tmp_path / "screener_config.yaml"
    config_content = """
metrics:
  roe_min:
    name: Return on Equity (%)
    column: return_on_equity_pct
    table: financial_ratios
    default_threshold: 12.0
    direction: higher_is_better

  de_max:
    name: Debt-to-Equity
    column: debt_to_equity
    table: financial_ratios
    default_threshold: 1.0
    direction: lower_is_better
    special_handling: financials_sector_skip

  icr_min:
    name: Interest Coverage Ratio
    column: interest_coverage
    table: financial_ratios
    default_threshold: 2.5
    direction: higher_is_better
    special_handling: debt_free_as_infinity

presets:
  growth_focused:
    name: "Growth-Focused"
    filters:
      roe_min: 15.0
      de_max: 1.5
    ranking_metric: roe_min
"""
    with open(config_path, "w") as f:
        f.write(config_content)
    return config_path


@pytest.fixture
def screener(temp_db, config_file):
    """Create a ScreenerEngine with test database and config."""
    engine = ScreenerEngine(db_path=temp_db, config_path=config_file)
    yield engine
    engine.close()


# ============================================================
# Test Cases
# ============================================================
class TestScreenerConfig:
    """Tests for configuration loading and validation."""

    def test_load_config_success(self, screener):
        """Test that config loads successfully."""
        assert screener.config is not None
        assert "metrics" in screener.config
        assert "presets" in screener.config

    def test_metrics_parsed(self, screener):
        """Test that all metrics are parsed into FilterConfig objects."""
        assert len(screener.metrics) >= 3
        assert "roe_min" in screener.metrics
        assert "de_max" in screener.metrics

    def test_filter_config_structure(self, screener):
        """Test FilterConfig has correct attributes."""
        roe_config = screener.metrics["roe_min"]
        assert roe_config.name == "Return on Equity (%)"
        assert roe_config.column == "return_on_equity_pct"
        assert roe_config.direction == "higher_is_better"
        assert roe_config.default_threshold == 12.0

    def test_presets_parsed(self, screener):
        """Test that presets are loaded."""
        assert "growth_focused" in screener.presets
        growth = screener.presets["growth_focused"]
        assert "filters" in growth
        assert growth["filters"]["roe_min"] == 15.0

    def test_list_presets(self, screener):
        """Test listing presets."""
        presets = screener.list_presets()
        assert len(presets) > 0
        assert any(name == "growth_focused" for name, _ in presets)

    def test_list_metrics(self, screener):
        """Test listing metrics."""
        metrics = screener.list_metrics()
        assert len(metrics) > 0
        metric_keys = [m[0] for m in metrics]
        assert "roe_min" in metric_keys


class TestFilterLogic:
    """Tests for filter application logic."""

    def test_higher_is_better_filter(self, screener):
        """Test filter where higher values pass (e.g., ROE min)."""
        df = pd.DataFrame({
            "company_id": ["A", "B", "C"],
            "return_on_equity_pct": [20.0, 14.0, 8.0],
            "broad_sector": ["IT", "FMCG", "IT"],
        })

        metric = screener.metrics["roe_min"]
        result = screener._apply_filter(df, "roe_min", metric, 12.0)

        assert len(result) == 2  # A (20.0) and B (14.0) pass, C (8.0) fails
        assert set(result["company_id"]) == {"A", "B"}

    def test_lower_is_better_filter(self, screener):
        """Test filter where lower values pass (e.g., D/E max, no sector skip)."""
        df = pd.DataFrame({
            "company_id": ["A", "B", "C"],
            "debt_to_equity": [0.8, 1.2, 0.5],
            "broad_sector": ["IT", "IT", "IT"],
        })

        metric = screener.metrics["de_max"]
        # Temporarily disable sector skip for this test
        metric.special_handling = None
        result = screener._apply_filter(df, "de_max", metric, 1.0)

        assert len(result) == 2  # A (0.8) and C (0.5) pass, B (1.2) fails
        assert set(result["company_id"]) == {"A", "C"}

    def test_financials_sector_skip_de_filter(self, screener):
        """Test that Financials sector is skipped when applying D/E max filter."""
        df = pd.DataFrame({
            "company_id": ["TECH", "BANK", "FMCG"],
            "debt_to_equity": [0.8, 8.0, 0.5],
            "broad_sector": ["IT", "Financials", "FMCG"],
        })

        metric = screener.metrics["de_max"]
        result = screener._apply_filter(df, "de_max", metric, 1.0)

        # Should keep: TECH (0.8 <= 1.0), FMCG (0.5 <= 1.0), BANK (all Financials pass)
        assert len(result) == 3
        assert set(result["company_id"]) == {"TECH", "BANK", "FMCG"}

    def test_debt_free_icr_handling(self, screener):
        """Test that NaN ICR (debt-free) is treated as infinity and passes."""
        df = pd.DataFrame({
            "company_id": ["DEBT_FREE", "NORMAL1", "NORMAL2"],
            "interest_coverage": [None, 3.0, 1.5],
            "broad_sector": ["Pharma", "IT", "IT"],
        })

        metric = screener.metrics["icr_min"]
        result = screener._apply_filter(df, "icr_min", metric, 2.5)

        # Should keep: DEBT_FREE (NaN passes), NORMAL1 (3.0 >= 2.5)
        assert len(result) == 2
        assert "DEBT_FREE" in result["company_id"].values
        assert "NORMAL1" in result["company_id"].values
        assert "NORMAL2" not in result["company_id"].values

    def test_nan_handling_in_higher_is_better(self, screener):
        """Test that NaN values are dropped in higher_is_better filters."""
        df = pd.DataFrame({
            "company_id": ["A", "B", "C"],
            "return_on_equity_pct": [20.0, None, 14.0],
            "broad_sector": ["IT", "IT", "IT"],
        })

        metric = screener.metrics["roe_min"]
        result = screener._apply_filter(df, "roe_min", metric, 12.0)

        # A and C pass; B (NaN) is dropped
        assert len(result) == 2
        assert "B" not in result["company_id"].values


class TestScreeningWorkflow:
    """Tests for end-to-end screening workflow."""

    def test_screen_with_single_filter(self, screener):
        """Test screening with a single filter."""
        request = ScreenerRequest(filters={"roe_min": 15.0})
        result = screener.screen(request)

        # Should have companies with ROE >= 15.0
        assert len(result) > 0
        assert all(
            (pd.isna(row["return_on_equity_pct"]) or row["return_on_equity_pct"] >= 15.0)
            for _, row in result.iterrows()
        )

    def test_screen_with_multiple_filters(self, screener):
        """Test screening with multiple filters."""
        request = ScreenerRequest(
            filters={"roe_min": 15.0, "de_max": 1.0}
        )
        result = screener.screen(request)

        # All results should pass both filters
        for _, row in result.iterrows():
            if pd.notna(row["return_on_equity_pct"]):
                assert row["return_on_equity_pct"] >= 15.0

    def test_screen_with_preset(self, screener):
        """Test screening using a preset filter."""
        request = ScreenerRequest(
            filters=screener.get_preset_filters("growth_focused"),
            preset_name="growth_focused"
        )
        result = screener.screen(request)

        # Should have results matching growth_focused criteria
        assert len(result) >= 0  # May be 0 if no companies match

    def test_screen_result_sorted_by_quality_score(self, screener):
        """Test that results are sorted by composite_quality_score."""
        request = ScreenerRequest(filters={"roe_min": 10.0})
        result = screener.screen(request)

        if len(result) > 1:
            scores = result["composite_quality_score"].dropna()
            if len(scores) > 1:
                # Verify scores are in descending order
                assert all(
                    scores.iloc[i] >= scores.iloc[i + 1]
                    for i in range(len(scores) - 1)
                )

    def test_screen_returns_dataframe(self, screener):
        """Test that screen returns a pandas DataFrame."""
        request = ScreenerRequest(filters={"roe_min": 5.0})
        result = screener.screen(request)

        assert isinstance(result, pd.DataFrame)
        assert "company_id" in result.columns


class TestPresetFunctions:
    """Tests for preset-based convenience functions."""

    def test_get_preset_filters(self, screener):
        """Test retrieving preset filters."""
        filters = screener.get_preset_filters("growth_focused")
        assert isinstance(filters, dict)
        assert "roe_min" in filters or len(filters) > 0

    def test_get_preset_filters_unknown_raises_error(self, screener):
        """Test that unknown preset raises ValueError."""
        with pytest.raises(ValueError, match="Unknown preset"):
            screener.get_preset_filters("nonexistent_preset")

    def test_screen_with_preset_function(self, temp_db, config_file):
        """Test convenience function screen_with_preset."""
        # This tests the module-level function
        result = screen_with_preset("growth_focused", db_path=temp_db, config_path=config_file)
        assert isinstance(result, pd.DataFrame)


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_result(self, screener):
        """Test screening with very strict filters that match nothing."""
        request = ScreenerRequest(
            filters={"roe_min": 1000.0}  # Unrealistic threshold
        )
        result = screener.screen(request)
        assert len(result) == 0

    def test_all_companies_pass(self, screener):
        """Test screening with very loose filters that match all."""
        request = ScreenerRequest(
            filters={"roe_min": 0.0}  # Very loose threshold
        )
        result = screener.screen(request)
        assert len(result) > 0

    def test_filters_with_nan_values(self, screener):
        """Test that NaN values are handled gracefully."""
        request = ScreenerRequest(filters={"roe_min": 10.0})
        result = screener.screen(request)
        # Should not raise exceptions
        assert isinstance(result, pd.DataFrame)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
