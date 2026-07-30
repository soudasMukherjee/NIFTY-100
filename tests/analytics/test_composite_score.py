"""Comprehensive tests for Composite Quality Score Engine.

Tests cover:
  1. All 10 sub-score helper functions — edge cases, boundaries, None handling
  2. The weighted category aggregation logic
  3. The full composite_quality_score_v2 — known-value calculations
  4. The legacy composite_quality_score backward compatibility
  5. FCF CAGR functions
  6. The export module (basic smoke test)
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make `src/` importable when running tests from repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import pandas as pd
import pytest

from src.analytics.ratio_engine import (
    _score_roe,
    _score_roce,
    _score_npm,
    _score_fcf_cagr,
    _score_cfo_pat_ratio,
    _score_fcf_positive,
    _score_revenue_cagr,
    _score_pat_cagr,
    _score_debt_to_equity,
    _score_interest_coverage,
    _weighted_category,
    composite_quality_score_v2,
    composite_quality_score,
    winsorise_value,
    compute_winsorisation_bounds,
    sector_percentile_score,
    compute_sector_percentile_scores,
)
from src.analytics.cagr import free_cash_flow_cagr, free_cash_flow_cagr_windows


# ============================================================
# 1. Scoring Helper Tests
# ============================================================

class TestScoreROE:
    def test_returns_none_for_none(self):
        assert _score_roe(None) is None

    def test_score_100_at_25_plus(self):
        assert _score_roe(25.0) == 100.0
        assert _score_roe(30.0) == 100.0

    def test_score_80_at_20_24(self):
        assert _score_roe(20.0) == 80.0
        assert _score_roe(24.0) == 80.0

    def test_score_60_at_15_19(self):
        assert _score_roe(15.0) == 60.0
        assert _score_roe(19.0) == 60.0

    def test_score_40_at_10_14(self):
        assert _score_roe(10.0) == 40.0
        assert _score_roe(14.0) == 40.0

    def test_score_20_at_5_9(self):
        assert _score_roe(5.0) == 20.0
        assert _score_roe(9.0) == 20.0

    def test_score_below_5_linear(self):
        assert _score_roe(2.5) == 10.0
        assert _score_roe(0) == 0.0
        assert _score_roe(-5) == 0.0  # negative => 0


class TestScoreROCE:
    def test_returns_none_for_none(self):
        assert _score_roce(None) is None

    def test_score_100_at_30_plus(self):
        assert _score_roce(30.0) == 100.0
        assert _score_roce(35.0) == 100.0

    def test_score_80_at_20_29(self):
        assert _score_roce(20.0) == 80.0

    def test_score_60_at_15_19(self):
        assert _score_roce(15.0) == 60.0

    def test_score_40_at_10_14(self):
        assert _score_roce(10.0) == 40.0

    def test_score_20_at_5_9(self):
        assert _score_roce(5.0) == 20.0

    def test_score_below_5_linear(self):
        assert _score_roce(2.5) == 10.0
        assert _score_roce(0) == 0.0


class TestScoreNPM:
    def test_returns_none_for_none(self):
        assert _score_npm(None) is None

    def test_score_100_at_20_plus(self):
        assert _score_npm(20.0) == 100.0
        assert _score_npm(25.0) == 100.0

    def test_score_80_at_15_19(self):
        assert _score_npm(15.0) == 80.0

    def test_score_60_at_10_14(self):
        assert _score_npm(10.0) == 60.0

    def test_score_40_at_5_9(self):
        assert _score_npm(5.0) == 40.0

    def test_score_20_at_2_4(self):
        assert _score_npm(2.0) == 20.0
        assert _score_npm(4.0) == 20.0

    def test_score_below_2_linear(self):
        assert _score_npm(1.0) == 10.0
        assert _score_npm(0) == 0.0


class TestScoreFCFCAGR:
    def test_returns_none_for_none(self):
        assert _score_fcf_cagr(None) is None

    def test_score_100_at_20_plus(self):
        assert _score_fcf_cagr(20.0) == 100.0
        assert _score_fcf_cagr(25.0) == 100.0

    def test_score_80_at_15_19(self):
        assert _score_fcf_cagr(15.0) == 80.0

    def test_score_60_at_10_14(self):
        assert _score_fcf_cagr(10.0) == 60.0

    def test_score_40_at_5_9(self):
        assert _score_fcf_cagr(5.0) == 40.0

    def test_score_20_at_0_4(self):
        assert _score_fcf_cagr(0.0) == 20.0
        assert _score_fcf_cagr(4.0) == 20.0

    def test_score_0_for_negative(self):
        assert _score_fcf_cagr(-1.0) == 0.0
        assert _score_fcf_cagr(-10.0) == 0.0


class TestScoreCFOPATRatio:
    def test_returns_none_for_none(self):
        assert _score_cfo_pat_ratio(None) is None

    def test_score_100_at_1_5_plus(self):
        assert _score_cfo_pat_ratio(1.5) == 100.0
        assert _score_cfo_pat_ratio(2.0) == 100.0

    def test_score_80_at_1_0_1_49(self):
        assert _score_cfo_pat_ratio(1.0) == 80.0

    def test_score_60_at_0_7_0_99(self):
        assert _score_cfo_pat_ratio(0.7) == 60.0

    def test_score_40_at_0_5_0_69(self):
        assert _score_cfo_pat_ratio(0.5) == 40.0

    def test_score_20_at_0_25_0_49(self):
        assert _score_cfo_pat_ratio(0.25) == 20.0

    def test_score_0_below_0_25(self):
        assert _score_cfo_pat_ratio(0.24) == 0.0
        assert _score_cfo_pat_ratio(-1.0) == 0.0


class TestScoreFCFPositive:
    def test_returns_none_for_none(self):
        assert _score_fcf_positive(None) is None

    def test_score_100_for_positive(self):
        assert _score_fcf_positive(100.0) == 100.0
        assert _score_fcf_positive(0.01) == 100.0

    def test_score_0_for_zero_or_negative(self):
        assert _score_fcf_positive(0.0) == 0.0
        assert _score_fcf_positive(-10.0) == 0.0


class TestScoreRevenueCAGR:
    def test_returns_none_for_none(self):
        assert _score_revenue_cagr(None) is None

    def test_score_100_at_25_plus(self):
        assert _score_revenue_cagr(25.0) == 100.0

    def test_score_80_at_20_24(self):
        assert _score_revenue_cagr(20.0) == 80.0

    def test_score_60_at_15_19(self):
        assert _score_revenue_cagr(15.0) == 60.0

    def test_score_40_at_10_14(self):
        assert _score_revenue_cagr(10.0) == 40.0

    def test_score_20_at_5_9(self):
        assert _score_revenue_cagr(5.0) == 20.0

    def test_score_below_5_linear(self):
        assert _score_revenue_cagr(2.5) == 10.0
        assert _score_revenue_cagr(0) == 0.0


class TestScorePATCAGR:
    def test_returns_none_for_none(self):
        assert _score_pat_cagr(None) is None

    def test_score_100_at_25_plus(self):
        assert _score_pat_cagr(25.0) == 100.0

    def test_score_80_at_20_24(self):
        assert _score_pat_cagr(20.0) == 80.0

    def test_score_60_at_15_19(self):
        assert _score_pat_cagr(15.0) == 60.0

    def test_score_40_at_10_14(self):
        assert _score_pat_cagr(10.0) == 40.0

    def test_score_20_at_5_9(self):
        assert _score_pat_cagr(5.0) == 20.0

    def test_score_below_5_linear(self):
        assert _score_pat_cagr(2.5) == 10.0
        assert _score_pat_cagr(0) == 0.0


class TestScoreDebtToEquity:
    def test_returns_none_for_none(self):
        assert _score_debt_to_equity(None) is None

    def test_score_100_at_zero(self):
        assert _score_debt_to_equity(0.0) == 100.0

    def test_score_80_at_up_to_0_3(self):
        assert _score_debt_to_equity(0.3) == 80.0
        assert _score_debt_to_equity(0.1) == 80.0

    def test_score_60_at_0_31_0_5(self):
        assert _score_debt_to_equity(0.5) == 60.0

    def test_score_40_at_0_51_1_0(self):
        assert _score_debt_to_equity(1.0) == 40.0

    def test_score_20_at_1_01_2_0(self):
        assert _score_debt_to_equity(2.0) == 20.0

    def test_score_0_above_2(self):
        assert _score_debt_to_equity(2.1) == 0.0
        assert _score_debt_to_equity(10.0) == 0.0


class TestScoreInterestCoverage:
    def test_returns_none_for_none(self):
        assert _score_interest_coverage(None) is None

    def test_score_100_at_10_plus(self):
        assert _score_interest_coverage(10.0) == 100.0
        assert _score_interest_coverage(15.0) == 100.0

    def test_score_80_at_5_9(self):
        assert _score_interest_coverage(5.0) == 80.0

    def test_score_60_at_3_4(self):
        assert _score_interest_coverage(3.0) == 60.0

    def test_score_40_at_2_2_9(self):
        assert _score_interest_coverage(2.0) == 40.0

    def test_score_20_at_1_1_9(self):
        assert _score_interest_coverage(1.0) == 20.0

    def test_score_0_below_1(self):
        assert _score_interest_coverage(0.5) == 0.0
        assert _score_interest_coverage(0) == 0.0


# ============================================================
# 2. Weighted Category Tests
# ============================================================

class TestWeightedCategory:
    def test_all_available(self):
        """All scores present → full weight used."""
        scores: list[tuple[float | None, float]] = [
            (100.0, 15.0),
            (80.0, 10.0),
            (60.0, 10.0),
        ]
        result = _weighted_category(scores, total_weight=35.0)
        # (100*15/35 + 80*10/35 + 60*10/35) * 35/100
        # = (1500/35 + 800/35 + 600/35) * 0.35
        # = (2900/35) * 0.35 = 29.0
        assert result == pytest.approx(29.0, rel=1e-9)

    def test_one_missing(self):
        """One score missing → weight redistributed."""
        scores: list[tuple[float | None, float]] = [
            (100.0, 15.0),
            (None, 10.0),  # missing
            (60.0, 10.0),
        ]
        result = _weighted_category(scores, total_weight=35.0)
        # Available: 15 + 10 = 25
        # Contribution = (100*15/25 + 60*10/25) * 35/100
        # = (1500/25 + 600/25) * 0.35
        # = (2100/25) * 0.35 = 29.4
        assert result == pytest.approx(29.4, rel=1e-9)

    def test_all_missing(self):
        """All scores missing → 0 contribution."""
        scores: list[tuple[float | None, float]] = [
            (None, 15.0),
            (None, 10.0),
        ]
        result = _weighted_category(scores, total_weight=25.0)
        assert result == 0.0

    def test_empty_scores(self):
        """Empty list → 0 contribution."""
        result = _weighted_category([], total_weight=25.0)
        assert result == 0.0


# ============================================================
# 3. Composite Quality Score v2 Tests
# ============================================================

class TestCompositeQualityScoreV2:
    def test_all_inputs_none_returns_none(self):
        result = composite_quality_score_v2()
        assert result is None

    def test_perfect_scores(self):
        """All inputs at max threshold → 100."""
        result = composite_quality_score_v2(
            roe_pct=25.0,       # 100
            roce_pct=30.0,      # 100
            npm_pct=20.0,       # 100
            fcf_cagr_5yr=20.0,  # 100
            cfo_pat_ratio=1.5,  # 100
            fcf_value=100.0,    # 100
            revenue_cagr_5yr=25.0,  # 100
            pat_cagr_5yr=25.0,      # 100
            debt_to_equity=0.0,     # 100
            interest_coverage=10.0, # 100
        )
        # All 100s → 100
        assert result == 100.0

    def test_zero_scores(self):
        """All inputs at worst → 0."""
        result = composite_quality_score_v2(
            roe_pct=0.0,         # 0
            roce_pct=0.0,        # 0
            npm_pct=0.0,         # 0
            fcf_cagr_5yr=-10.0,  # 0
            cfo_pat_ratio=0.0,   # 0
            fcf_value=0.0,       # 0
            revenue_cagr_5yr=0.0,    # 0
            pat_cagr_5yr=0.0,        # 0
            debt_to_equity=3.0,      # 0
            interest_coverage=0.0,   # 0
        )
        assert result == 0.0

    def test_mid_range_scores(self):
        """Known values for verification."""
        result = composite_quality_score_v2(
            roe_pct=18.0,       # score = 60 (15-19 bucket)
            roce_pct=18.0,      # score = 60 (15-19 bucket)
            npm_pct=12.0,       # score = 60 (10-14 bucket)
            fcf_cagr_5yr=12.0,  # score = 60 (10-14 bucket)
            cfo_pat_ratio=1.2,  # score = 80 (1.0-1.49 bucket)
            fcf_value=50.0,     # score = 100 (positive)
            revenue_cagr_5yr=18.0,  # score = 60 (15-19 bucket)
            pat_cagr_5yr=18.0,      # score = 60 (15-19 bucket)
            debt_to_equity=0.4,     # score = 60 (0.31-0.5 bucket)
            interest_coverage=4.0,  # score = 60 (3-4 bucket)
        )

        # Profitability (35%): all 3 available, weight 15+10+10=35
        # = (60*15/35 + 60*10/35 + 60*10/35) * 0.35 = 60 * 0.35 = 21.0

        # Cash Quality (30%): all 3 available, weight 15+10+5=30
        # = (60*15/30 + 80*10/30 + 100*5/30) * 0.30
        # = (30 + 26.67 + 16.67) * 0.30 = 73.34 * 0.30 = 22.0
        # Let me compute precisely:
        cash_val = (60.0 * 15.0 / 30.0 + 80.0 * 10.0 / 30.0 + 100.0 * 5.0 / 30.0) * 0.30
        # = (30.0 + 26.666.. + 16.666..) * 0.30 = 73.333.. * 0.30 = 22.0

        # Growth (20%): both available, weight 10+10=20
        # = (60*10/20 + 60*10/20) * 0.20 = 60 * 0.20 = 12.0

        # Leverage (15%): both available, weight 10+5=15
        # = (60*10/15 + 60*5/15) * 0.15 = 60 * 0.15 = 9.0

        expected = 21.0 + 22.0 + 12.0 + 9.0  # = 64.0
        assert result == pytest.approx(expected, rel=1e-2)

    def test_partial_missing_values(self):
        """None values should be redistributed within categories."""
        # Only ROE and ROCE present in Profitability (NPM missing)
        result = composite_quality_score_v2(
            roe_pct=25.0,       # 100 → weight 15
            roce_pct=30.0,      # 100 → weight 10
            npm_pct=None,       # missing → redistributed
            fcf_cagr_5yr=None,  # missing
            cfo_pat_ratio=None, # missing
            fcf_value=100.0,    # 100 → weight 5
            revenue_cagr_5yr=25.0,  # 100
            pat_cagr_5yr=25.0,      # 100
            debt_to_equity=0.0,     # 100
            interest_coverage=None, # missing
        )
        assert result is not None
        assert result > 0  # Should have some score

    def test_returns_float_between_0_and_100(self):
        """Validate range for random inputs."""
        result = composite_quality_score_v2(
            roe_pct=12.0,
            roce_pct=8.0,
            npm_pct=6.0,
            fcf_cagr_5yr=7.0,
            cfo_pat_ratio=0.6,
            fcf_value=10.0,
            revenue_cagr_5yr=12.0,
            pat_cagr_5yr=15.0,
            debt_to_equity=0.8,
            interest_coverage=2.5,
        )
        assert 0 <= result <= 100


# ============================================================
# 4. Legacy Backward Compatibility Test
# ============================================================

class TestCompositeQualityScoreLegacy:
    def test_legacy_normal_case(self):
        result = composite_quality_score(
            cfo_quality_score=1.2,
            fcf_conversion_rate_pct=80.0,
        )
        # (1.2 + 80/100) / 2 = (1.2 + 0.8) / 2 = 1.0
        assert result == 1.0

    def test_legacy_none_input_returns_none(self):
        assert composite_quality_score(cfo_quality_score=None, fcf_conversion_rate_pct=80.0) is None
        assert composite_quality_score(cfo_quality_score=1.2, fcf_conversion_rate_pct=None) is None


# ============================================================
# 5. FCF CAGR Tests
# ============================================================

class TestFreeCashFlowCAGR:
    def test_normal_positive_growth(self):
        """FCF growing from 100 to 161.05 over 5 years → ~10% CAGR."""
        fcf_values = [100.0, 110.0, 121.0, 133.1, 146.41]
        result = free_cash_flow_cagr(fcf_values, window_years=5)
        # CAGR = (146.41/100)^(1/4) - 1 ≈ 0.10 = 10%
        assert result is not None
        assert result == pytest.approx(10.0, rel=0.5)

    def test_negative_fcf_start_returns_none(self):
        """FCF starting negative → CAGR undefined → None."""
        fcf_values = [-100.0, -50.0, 0.0, 50.0, 100.0]
        result = free_cash_flow_cagr(fcf_values, window_years=5)
        assert result is None

    def test_insufficient_data_returns_none(self):
        result = free_cash_flow_cagr([100.0, 110.0], window_years=5)
        assert result is None

    def test_windows_dict_contains_all_windows(self):
        fcf_values = [100.0, 105.0, 110.0, 115.0, 120.0, 125.0, 130.0]
        windows = free_cash_flow_cagr_windows(fcf_values)
        assert 3 in windows
        assert 5 in windows
        assert 10 in windows
        # 10-year window should be None (insufficient data)
        assert windows[10] is None


# ============================================================
# 6. Export Smoke Test (using mocked data)
# ============================================================

class TestCompositeScoreExport:
    def test_export_module_imports(self):
        """Verify the export module can be imported."""
        from src.etl.composite_score_export import export_composite_scores_csv
        assert callable(export_composite_scores_csv)

    def test_scoring_function_coverage(self):
        """Verify all _score_* functions are importable from ratio_engine."""
        names = [
            "_score_roe", "_score_roce", "_score_npm",
            "_score_fcf_cagr", "_score_cfo_pat_ratio", "_score_fcf_positive",
            "_score_revenue_cagr", "_score_pat_cagr",
            "_score_debt_to_equity", "_score_interest_coverage",
        ]
        for name in names:
            assert hasattr(__import__("src.analytics.ratio_engine", fromlist=[name]), name)


# ============================================================
# 7. Winsorisation Tests
# ============================================================

class TestWinsoriseValue:
    def test_value_within_bounds_unchanged(self):
        assert winsorise_value(50.0, 10.0, 90.0) == 50.0

    def test_value_below_p10_capped(self):
        assert winsorise_value(5.0, 10.0, 90.0) == 10.0

    def test_value_above_p90_capped(self):
        assert winsorise_value(95.0, 10.0, 90.0) == 90.0

    def test_none_value_returns_none(self):
        assert winsorise_value(None, 10.0, 90.0) is None

    def test_none_bounds_returns_original(self):
        assert winsorise_value(50.0, None, 90.0) == 50.0
        assert winsorise_value(50.0, 10.0, None) == 50.0

    def test_value_at_boundary_unchanged(self):
        assert winsorise_value(10.0, 10.0, 90.0) == 10.0
        assert winsorise_value(90.0, 10.0, 90.0) == 90.0


class TestComputeWinsorisationBounds:
    def test_normal_case(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        p10, p90 = compute_winsorisation_bounds(values)
        assert p10 is not None
        assert p90 is not None
        assert p10 <= p90

    def test_insufficient_data_returns_none(self):
        p10, p90 = compute_winsorisation_bounds([1.0, 2.0, 3.0])
        assert p10 is None
        assert p90 is None

    def test_all_none_returns_none(self):
        p10, p90 = compute_winsorisation_bounds([None, None, None, None])
        assert p10 is None
        assert p90 is None

    def test_mixed_none_and_values(self):
        values = [1.0, None, 2.0, None, 3.0, 4.0, 5.0, 6.0]
        p10, p90 = compute_winsorisation_bounds(values)
        assert p10 is not None
        assert p90 is not None
        assert p10 <= p90

    def test_empty_list_returns_none(self):
        p10, p90 = compute_winsorisation_bounds([])
        assert p10 is None
        assert p90 is None


# ============================================================
# 8. Sector-Relative Percentile Scoring Tests
# ============================================================

class TestSectorPercentileScore:
    def test_value_at_median_returns_50(self):
        """Median value → ~50th percentile."""
        score = sector_percentile_score(50.0, [0.0, 25.0, 50.0, 75.0, 100.0])
        assert score == 50.0

    def test_value_higher_than_all_returns_100(self):
        score = sector_percentile_score(100.0, [0.0, 25.0, 50.0, 75.0])
        assert score == 100.0

    def test_value_lower_than_all_returns_0(self):
        score = sector_percentile_score(-10.0, [0.0, 25.0, 50.0, 75.0])
        assert score == 0.0

    def test_none_value_returns_none(self):
        score = sector_percentile_score(None, [0.0, 25.0, 50.0])
        assert score is None

    def test_empty_sector_returns_none(self):
        score = sector_percentile_score(50.0, [])
        assert score is None

    def test_single_company_returns_50(self):
        """Single company in sector → median."""
        score = sector_percentile_score(50.0, [50.0])
        assert score == 50.0

    def test_inverted_lower_is_better(self):
        """For D/E (lower is better), we invert externally."""
        # Higher D/E → low raw percentile, then we do 100 - percentile
        raw_de_values = [0.1, 0.5, 1.0, 2.0, 5.0]
        raw_score = sector_percentile_score(5.0, raw_de_values)  # worst
        assert raw_score == 100.0  # highest D/E = highest percentile
        inverted = 100.0 - raw_score
        assert inverted == 0.0  # worst D/E → 0


class TestComputeSectorPercentileScores:
    def test_compute_for_multiple_sectors(self):
        company_values = {
            "A": 50.0, "B": 30.0, "C": 10.0,  # Sector X
            "D": 90.0, "E": 50.0,              # Sector Y
        }
        sector_map = {"A": "X", "B": "X", "C": "X", "D": "Y", "E": "Y"}
        result = compute_sector_percentile_scores(
            company_values=company_values,
            sector_map=sector_map,
        )
        assert len(result) == 5
        # Sector X values sorted: [10, 30, 50]
        # C(10) = 0th percentile, B(30) = 50th, A(50) = 100th
        assert result["A"] == 100.0  # highest in X
        assert result["B"] == 50.0   # middle in X
        assert result["C"] == 0.0    # lowest in X
        # Sector Y values sorted: [50, 90]
        # E(50) = 0th percentile, D(90) = 100th
        assert result["D"] == 100.0
        assert result["E"] == 0.0

    def test_company_with_unknown_sector(self):
        company_values = {"A": 50.0, "B": 30.0}
        sector_map = {"A": "X"}  # B has no sector → assigned "Unknown"
        result = compute_sector_percentile_scores(
            company_values=company_values,
            sector_map=sector_map,
        )
        assert "A" in result
        assert "B" in result
        assert result["B"] is not None  # scored within its own "Unknown" sector group

    def test_empty_values(self):
        result = compute_sector_percentile_scores(
            company_values={},
            sector_map={},
        )
        assert result == {}

