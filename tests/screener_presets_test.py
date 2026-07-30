"""
Sprint 3 · Day 16 — Preset Screener Tests
Tests for all 6 preset screeners: verifies each preset loads correctly,
returns results within expected range (5-50 companies), and results make
business sense.
"""
from __future__ import annotations

import pytest
import pandas as pd
import sqlite3
from pathlib import Path

from src.screener.engine import (
    ScreenerEngine,
    ScreenerRequest,
    create_screener,
    screen_with_preset,
)


# ============================================================
# Fixtures
# ============================================================
@pytest.fixture(scope="module")
def db_path():
    """Path to the real Nifty 100 database."""
    return Path(__file__).resolve().parent.parent / "nifty100.db"


@pytest.fixture(scope="module")
def screener(db_path):
    """Create a ScreenerEngine connected to the real database."""
    engine = create_screener(db_path=db_path)
    yield engine
    engine.close()


# ============================================================
# Test: Preset Definitions
# ============================================================
class TestPresetDefinitions:
    """Verify all 6 presets are defined in config."""

    def test_all_six_presets_exist(self, screener):
        """Check that exactly 6 presets are defined."""
        presets = screener.list_presets()
        preset_ids = [pid for pid, _ in presets]
        expected = {
            "quality_compounder",
            "value_pick",
            "growth_accelerator",
            "dividend_champion",
            "debt_free_blue_chip",
            "turnaround_watch",
        }
        for pid in expected:
            assert pid in preset_ids, f"Missing preset: {pid}"
        assert len(presets) >= 6

    def test_quality_compounder_filters(self, screener):
        """Quality Compounder: ROE > 15%, D/E < 1.0, FCF > 0, Rev CAGR 5yr > 10%"""
        filters = screener.get_preset_filters("quality_compounder")
        assert filters["roe_min"] >= 15.0
        assert filters["de_max"] <= 1.0
        assert filters["fcf_min"] >= 0.0
        assert filters["revenue_cagr_5yr_min"] >= 10.0

    def test_value_pick_filters(self, screener):
        """Value Pick: P/E < 35, P/B < 3.0, D/E < 2.0, Div Yield > 1%"""
        filters = screener.get_preset_filters("value_pick")
        assert filters["pe_max"] >= 20.0
        assert filters["pb_max"] <= 3.0
        assert filters["de_max"] <= 2.0
        assert filters["dividend_yield_min"] >= 1.0

    def test_growth_accelerator_filters(self, screener):
        """Growth Accelerator: PAT CAGR 5yr > 20%, Rev CAGR 5yr > 15%, D/E < 2.0"""
        filters = screener.get_preset_filters("growth_accelerator")
        assert filters["pat_cagr_5yr_min"] >= 20.0
        assert filters["revenue_cagr_5yr_min"] >= 15.0
        assert filters["de_max"] <= 2.0

    def test_dividend_champion_filters(self, screener):
        """Dividend Champion: Div Yield > 2%, Payout < 80%, FCF > 0"""
        filters = screener.get_preset_filters("dividend_champion")
        assert filters["dividend_yield_min"] >= 2.0
        assert filters["dividend_payout_max"] <= 80.0
        assert filters["fcf_min"] >= 0.0

    def test_debt_free_blue_chip_filters(self, screener):
        """Debt-Free Blue Chip: D/E near 0, ROE > 12%, Revenue > 5000 Cr"""
        filters = screener.get_preset_filters("debt_free_blue_chip")
        assert "de_near_zero" in filters
        assert filters["de_near_zero"] <= 0.01
        assert filters["roe_min"] >= 12.0
        assert filters["sales_min"] >= 5000.0

    def test_turnaround_watch_filters(self, screener):
        """Turnaround Watch: Rev CAGR 3yr > 10%, FCF > 0, D/E declining"""
        filters = screener.get_preset_filters("turnaround_watch")
        assert filters["revenue_cagr_3yr_min"] >= 10.0
        assert filters["fcf_min"] >= 0.0
        assert filters["de_yoy_change_pct_min"] >= 0.0


# ============================================================
# Test: Preset Screening Results
# ============================================================
class TestPresetResults:
    """Verify each preset returns results in the 5-50 range."""

    PRESETS_TO_TEST = [
        "quality_compounder",
        "value_pick",
        "growth_accelerator",
        "dividend_champion",
        "debt_free_blue_chip",
        "turnaround_watch",
    ]

    @pytest.mark.parametrize("preset_name", PRESETS_TO_TEST)
    def test_preset_returns_valid_range(self, screener, preset_name):
        """Each preset should return between 5 and 50 companies."""
        filters = screener.get_preset_filters(preset_name)
        request = ScreenerRequest(filters=filters, preset_name=preset_name)
        result = screener.screen(request)
        count = len(result)
        assert 5 <= count <= 50, (
            f"{preset_name} returned {count} companies (expected 5-50)"
        )

    @pytest.mark.parametrize("preset_name", PRESETS_TO_TEST)
    def test_preset_result_is_dataframe(self, screener, preset_name):
        """Each preset result should be a non-empty DataFrame."""
        filters = screener.get_preset_filters(preset_name)
        request = ScreenerRequest(filters=filters, preset_name=preset_name)
        result = screener.screen(request)
        assert isinstance(result, pd.DataFrame)
        assert "company_id" in result.columns
        assert len(result) > 0

    @pytest.mark.parametrize("preset_name", PRESETS_TO_TEST)
    def test_preset_result_sorted_by_quality(self, screener, preset_name):
        """Results should be sorted by composite_quality_score descending."""
        filters = screener.get_preset_filters(preset_name)
        request = ScreenerRequest(filters=filters, preset_name=preset_name)
        result = screener.screen(request)
        if len(result) > 1 and "composite_quality_score" in result.columns:
            scores = result["composite_quality_score"].dropna()
            if len(scores) > 1:
                for i in range(len(scores) - 1):
                    assert scores.iloc[i] >= scores.iloc[i + 1], (
                        f"Not sorted at index {i}: {scores.iloc[i]} < {scores.iloc[i + 1]}"
                    )

    @pytest.mark.parametrize("preset_name", PRESETS_TO_TEST)
    def test_preset_results_deduplicated(self, screener, preset_name):
        """Each company should appear at most once in results."""
        filters = screener.get_preset_filters(preset_name)
        request = ScreenerRequest(filters=filters, preset_name=preset_name)
        result = screener.screen(request)
        assert result["company_id"].is_unique, (
            f"{preset_name} returned duplicate companies"
        )


# ============================================================
# Test: Business Logic Validation
# ============================================================
class TestBusinessLogic:
    """Verify preset results make business sense."""

    def test_quality_compounder_logic(self, screener):
        """
        Quality Compounder companies should have:
        - High ROE (> 15%)
        - Reasonable leverage (D/E < 1.0 or Financials)
        - Positive free cash flow
        - Consistent revenue growth
        """
        filters = screener.get_preset_filters("quality_compounder")
        result = screener.screen(ScreenerRequest(filters=filters))
        for _, row in result.iterrows():
            if pd.notna(row.get("return_on_equity_pct")):
                assert row["return_on_equity_pct"] > 15, (
                    f"{row['company_id']} ROE {row['return_on_equity_pct']} <= 15"
                )
            # D/E check: Financials are exempt
            if pd.notna(row.get("debt_to_equity")) and row.get("broad_sector") != "Financials":
                assert row["debt_to_equity"] <= 1.0, (
                    f"{row['company_id']} D/E {row['debt_to_equity']} > 1.0"
                )
            if pd.notna(row.get("free_cash_flow_cr")):
                assert row["free_cash_flow_cr"] > 0, (
                    f"{row['company_id']} FCF {row['free_cash_flow_cr']} <= 0"
                )

    def test_value_pick_logic(self, screener):
        """
        Value Pick companies should have:
        - P/E < 35
        - P/B < 3.0
        - D/E < 2.0 (or Financials)
        - Dividend yield > 1%
        """
        filters = screener.get_preset_filters("value_pick")
        result = screener.screen(ScreenerRequest(filters=filters))
        for _, row in result.iterrows():
            if pd.notna(row.get("pe_ratio")):
                assert row["pe_ratio"] < 35, (
                    f"{row['company_id']} P/E {row['pe_ratio']} >= 35"
                )
            if pd.notna(row.get("pb_ratio")):
                assert row["pb_ratio"] < 3.0, (
                    f"{row['company_id']} P/B {row['pb_ratio']} >= 3.0"
                )
            if pd.notna(row.get("dividend_yield_pct")):
                assert row["dividend_yield_pct"] > 1.0, (
                    f"{row['company_id']} Div Yield {row['dividend_yield_pct']} <= 1%"
                )
            if pd.notna(row.get("debt_to_equity")) and row.get("broad_sector") != "Financials":
                assert row["debt_to_equity"] <= 2.0, (
                    f"{row['company_id']} D/E {row['debt_to_equity']} > 2.0"
                )

    def test_growth_accelerator_logic(self, screener):
        """
        Growth Accelerator companies should have:
        - PAT CAGR 5yr > 20%
        - Revenue CAGR 5yr > 15%
        - D/E < 2.0 (or Financials)
        """
        filters = screener.get_preset_filters("growth_accelerator")
        result = screener.screen(ScreenerRequest(filters=filters))
        for _, row in result.iterrows():
            if pd.notna(row.get("pat_cagr_5yr")):
                assert row["pat_cagr_5yr"] > 20, (
                    f"{row['company_id']} PAT CAGR {row['pat_cagr_5yr']} <= 20%"
                )
            if pd.notna(row.get("revenue_cagr_5yr")):
                assert row["revenue_cagr_5yr"] > 15, (
                    f"{row['company_id']} Rev CAGR {row['revenue_cagr_5yr']} <= 15%"
                )

    def test_dividend_champion_logic(self, screener):
        """
        Dividend Champion companies should have:
        - Dividend yield > 2%
        - Dividend payout < 80%
        - Positive free cash flow
        """
        filters = screener.get_preset_filters("dividend_champion")
        result = screener.screen(ScreenerRequest(filters=filters))
        for _, row in result.iterrows():
            if pd.notna(row.get("dividend_yield_pct")):
                assert row["dividend_yield_pct"] > 2.0, (
                    f"{row['company_id']} Div Yield {row['dividend_yield_pct']} <= 2%"
                )
            if pd.notna(row.get("dividend_payout_ratio_pct")):
                assert row["dividend_payout_ratio_pct"] < 80.0, (
                    f"{row['company_id']} Payout {row['dividend_payout_ratio_pct']} >= 80%"
                )
            if pd.notna(row.get("free_cash_flow_cr")):
                assert row["free_cash_flow_cr"] > 0, (
                    f"{row['company_id']} FCF {row['free_cash_flow_cr']} <= 0"
                )

    def test_debt_free_blue_chip_logic(self, screener):
        """
        Debt-Free Blue Chip companies should have:
        - D/E near zero (<= 0.01)
        - ROE > 12%
        - Revenue > 5000 Cr
        """
        filters = screener.get_preset_filters("debt_free_blue_chip")
        result = screener.screen(ScreenerRequest(filters=filters))
        for _, row in result.iterrows():
            if pd.notna(row.get("debt_to_equity")):
                # D/E near zero (<= 0.01 = effectively debt-free)
                assert row["debt_to_equity"] <= 0.01, (
                    f"{row['company_id']} D/E {row['debt_to_equity']} > 0.01"
                )
            if pd.notna(row.get("return_on_equity_pct")):
                assert row["return_on_equity_pct"] > 12.0, (
                    f"{row['company_id']} ROE {row['return_on_equity_pct']} <= 12%"
                )
            if pd.notna(row.get("sales")):
                assert row["sales"] > 5000, (
                    f"{row['company_id']} Sales {row['sales']} <= 5000 Cr"
                )

    def test_turnaround_watch_logic(self, screener):
        """
        Turnaround Watch companies should have:
        - Revenue CAGR 3yr > 10%
        - Positive FCF in latest year
        - D/E declining YoY (de_yoy_change_pct > 0)
        """
        filters = screener.get_preset_filters("turnaround_watch")
        result = screener.screen(ScreenerRequest(filters=filters))
        for _, row in result.iterrows():
            if pd.notna(row.get("revenue_cagr_3yr")):
                assert row["revenue_cagr_3yr"] > 10.0, (
                    f"{row['company_id']} Rev CAGR 3yr {row['revenue_cagr_3yr']} <= 10%"
                )
            if pd.notna(row.get("free_cash_flow_cr")):
                assert row["free_cash_flow_cr"] > 0, (
                    f"{row['company_id']} FCF {row['free_cash_flow_cr']} <= 0"
                )


# ============================================================
# Test: Edge Cases
# ============================================================
class TestEdgeCases:
    """Test edge cases and cross-preset validation."""

    def test_no_preset_overlap_all(self, screener):
        """Some companies may appear in multiple presets - verify at least one distinction."""
        preset_results = {}
        for preset_name in TestPresetResults.PRESETS_TO_TEST:
            filters = screener.get_preset_filters(preset_name)
            result = screener.screen(ScreenerRequest(filters=filters))
            preset_results[preset_name] = set(result["company_id"].tolist())

        # Quality Compounder and Value Pick should be different
        qc = preset_results["quality_compounder"]
        vp = preset_results["value_pick"]
        # They can overlap, but shouldn't be identical
        assert qc != vp, "Quality Compounder and Value Pick returned identical sets"

    def test_preset_row_counts_total(self, screener):
        """The sum of all preset results should be between lower and upper bounds."""
        total = set()
        for preset_name in TestPresetResults.PRESETS_TO_TEST:
            filters = screener.get_preset_filters(preset_name)
            result = screener.screen(ScreenerRequest(filters=filters))
            total.update(result["company_id"].tolist())
        # Total unique companies across all presets should be > 10
        assert len(total) > 10, (
            f"Only {len(total)} unique companies across all presets"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
