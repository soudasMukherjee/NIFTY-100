"""Comprehensive tests for Peer Percentile Rankings (Day 18)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import pandas as pd
import pytest

from src.analytics.peer import (
    _percent_rank,
    METRICS,
    load_peer_groups,
    compute_peer_percentile_rankings,
    load_all_companies,
    populate_peer_percentiles_table,
)


# ============================================================
# 1. _percent_rank unit tests
# ============================================================

class TestPercentRank:
    def test_none_value_returns_none(self):
        assert _percent_rank(None, [1.0, 2.0, 3.0]) is None

    def test_empty_series_returns_none(self):
        assert _percent_rank(50.0, []) is None

    def test_all_none_series_returns_none(self):
        assert _percent_rank(50.0, [None, None, None]) is None

    def test_single_element_returns_50(self):
        assert _percent_rank(50.0, [50.0]) == 50.0

    def test_higher_than_all_returns_100(self):
        assert _percent_rank(100.0, [10.0, 20.0, 30.0, 40.0]) == 100.0

    def test_lower_than_all_returns_0(self):
        assert _percent_rank(5.0, [10.0, 20.0, 30.0, 40.0]) == 0.0

    def test_median_returns_50(self):
        """Value exactly at median → ~50th percentile."""
        rank = _percent_rank(50.0, [0.0, 25.0, 50.0, 75.0, 100.0])
        assert rank == 50.0

    def test_second_quartile(self):
        """Value above median but not max."""
        rank = _percent_rank(60.0, [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0])
        # 5 values less than 60 (10,20,30,40,50) out of 10 → 5/9 * 100 ≈ 55.56
        assert rank == pytest.approx(55.56, rel=0.1)

    def test_clamps_to_100(self):
        rank = _percent_rank(100.0, [10.0, 20.0, 30.0, 40.0, 50.0])
        assert rank == 100.0

    def test_clamps_to_0(self):
        rank = _percent_rank(-10.0, [10.0, 20.0, 30.0, 40.0, 50.0])
        assert rank == 0.0

    def test_inverted_metric(self):
        """For lower-is-better, we invert externally."""
        raw = _percent_rank(5.0, [1.0, 2.0, 3.0, 4.0, 5.0])
        assert raw is not None
        assert raw == 100.0  # highest value = worst for lower-is-better
        inverted = round(100.0 - raw, 2)
        assert inverted == 0.0


# ============================================================
# 2. METRICS configuration tests
# ============================================================

class TestMetricsConfig:
    def test_exactly_10_metrics(self):
        assert len(METRICS) == 10

    def test_all_metrics_have_valid_structure(self):
        for item in METRICS:
            assert len(item) == 3
            col, label, higher_better = item
            assert isinstance(col, str)
            assert isinstance(label, str)
            assert isinstance(higher_better, bool)

    def test_debt_to_equity_is_lower_better(self):
        de_metric = [m for m in METRICS if m[1] == "D/E"]
        assert len(de_metric) == 1
        assert de_metric[0][2] is False  # lower is better

    def test_all_other_metrics_are_higher_better(self):
        higher_better = [m for m in METRICS if m[2]]
        assert len(higher_better) == 9  # 9 out of 10 are higher-is-better

    def test_roce_is_present(self):
        roce_metric = [m for m in METRICS if m[1] == "ROCE"]
        assert len(roce_metric) == 1
        assert roce_metric[0][0] == "roce_pct"

    def test_net_profit_margin_label(self):
        npm_metric = [m for m in METRICS if m[0] == "net_profit_margin_pct"]
        assert len(npm_metric) == 1
        assert npm_metric[0][1] == "Net Profit Margin"

    def test_interest_coverage_label(self):
        icr_metric = [m for m in METRICS if m[0] == "interest_coverage"]
        assert len(icr_metric) == 1
        assert icr_metric[0][1] == "Interest Coverage"

    def test_column_names_are_valid(self):
        """Column names should look like SQL columns."""
        cols = [m[0] for m in METRICS]
        for col in cols:
            assert "_" in col


# ============================================================
# 3. load_peer_groups tests
# ============================================================

class TestLoadPeerGroups:
    def test_returns_dataframe(self):
        pg_df = load_peer_groups()
        assert isinstance(pg_df, pd.DataFrame)

    def test_has_expected_columns(self):
        pg_df = load_peer_groups()
        expected = {"id", "peer_group_name", "company_id", "is_benchmark"}
        assert expected.issubset(set(pg_df.columns))

    def test_has_11_peer_groups(self):
        pg_df = load_peer_groups()
        assert pg_df["peer_group_name"].nunique() == 11

    def test_has_expected_group_names(self):
        pg_df = load_peer_groups()
        expected_groups = {
            "Private Banks", "Public Sector Banks", "IT Services",
            "Pharmaceuticals", "Automobiles", "Life Insurance",
            "Oil & Gas", "Power & Utilities", "Steel", "FMCG",
            "Consumer Finance",
        }
        assert set(pg_df["peer_group_name"].unique()) == expected_groups

    def test_is_benchmark_is_boolean(self):
        pg_df = load_peer_groups()
        assert pg_df["is_benchmark"].dtype == bool

    def test_each_group_has_at_least_one_benchmark(self):
        pg_df = load_peer_groups()
        for group, df in pg_df.groupby("peer_group_name"):
            assert df["is_benchmark"].any(), f"{group} has no benchmark"


# ============================================================
# 4. compute_peer_percentile_rankings tests (with mock data)
# ============================================================

class TestComputePeerPercentileRankings:
    def _make_mock_peer_groups(self) -> pd.DataFrame:
        """3 companies in GroupA, 2 in GroupB."""
        return pd.DataFrame({
            "id": [1, 2, 3, 4, 5],
            "peer_group_name": ["GroupA", "GroupA", "GroupA", "GroupB", "GroupB"],
            "company_id": ["A1", "A2", "A3", "B1", "B2"],
            "is_benchmark": [True, False, False, True, False],
        })

    def _make_mock_ratios(self) -> pd.DataFrame:
        return pd.DataFrame({
            "company_id": ["A1", "A2", "A3", "B1", "B2"],
            "year": [2024, 2024, 2024, 2024, 2024],
            "return_on_equity_pct": [25.0, 15.0, 5.0, 30.0, 10.0],
            "roce_pct": [30.0, 20.0, 10.0, 35.0, 15.0],
            "net_profit_margin_pct": [20.0, 10.0, 2.0, 25.0, 5.0],
            "debt_to_equity": [0.0, 1.0, 3.0, 0.5, 2.0],
            "interest_coverage": [10.0, 5.0, 1.0, 15.0, 3.0],
            "asset_turnover": [2.0, 1.5, 1.0, 3.0, 0.5],
            "free_cash_flow_cr": [1000.0, 500.0, -100.0, 2000.0, 100.0],
            "revenue_cagr_5yr": [20.0, 10.0, 5.0, 25.0, 8.0],
            "pat_cagr_5yr": [25.0, 12.0, 3.0, 30.0, 6.0],
            "eps_cagr_5yr": [20.0, 8.0, -5.0, 22.0, 4.0],
        })

    def test_returns_dataframe(self):
        pg = self._make_mock_peer_groups()
        ratios = self._make_mock_ratios()
        result = compute_peer_percentile_rankings(pg, ratios)
        assert isinstance(result, pd.DataFrame)

    def test_returns_all_companies(self):
        pg = self._make_mock_peer_groups()
        ratios = self._make_mock_ratios()
        result = compute_peer_percentile_rankings(pg, ratios)
        assert len(result) == 5  # all 5 companies

    def test_has_expected_columns(self):
        pg = self._make_mock_peer_groups()
        ratios = self._make_mock_ratios()
        result = compute_peer_percentile_rankings(pg, ratios)

        assert "company_id" in result.columns
        assert "peer_group_name" in result.columns
        assert "is_benchmark" in result.columns
        assert "avg_percentile_rank" in result.columns

        # Should have raw + pctl columns for each metric
        for _, label, _ in METRICS:
            assert f"{label} (raw)" in result.columns
            assert f"{label} (pctl)" in result.columns

    def test_group_a_rankings(self):
        """A1 has highest ROE (25) in GroupA → 100th percentile."""
        pg = self._make_mock_peer_groups()
        ratios = self._make_mock_ratios()
        result = compute_peer_percentile_rankings(pg, ratios)

        a1 = result[result["company_id"] == "A1"]
        assert len(a1) == 1
        assert a1.iloc[0]["ROE (pctl)"] == 100.0

    def test_group_a_lowest_roe(self):
        """A3 has lowest ROE (5) in GroupA → 0th percentile."""
        pg = self._make_mock_peer_groups()
        ratios = self._make_mock_ratios()
        result = compute_peer_percentile_rankings(pg, ratios)

        a3 = result[result["company_id"] == "A3"]
        assert len(a3) == 1
        assert a3.iloc[0]["ROE (pctl)"] == 0.0

    def test_group_a_middle_roe(self):
        """A2 has middle ROE (15) in GroupA → 50th percentile."""
        pg = self._make_mock_peer_groups()
        ratios = self._make_mock_ratios()
        result = compute_peer_percentile_rankings(pg, ratios)

        a2 = result[result["company_id"] == "A2"]
        assert len(a2) == 1
        assert a2.iloc[0]["ROE (pctl)"] == 50.0

    def test_de_inverted(self):
        """A1 has D/E=0 (lowest), so inverted rank = 100 (best)."""
        pg = self._make_mock_peer_groups()
        ratios = self._make_mock_ratios()
        result = compute_peer_percentile_rankings(pg, ratios)

        a1 = result[result["company_id"] == "A1"]
        assert a1.iloc[0]["D/E (pctl)"] == 100.0

        a3 = result[result["company_id"] == "A3"]
        assert a3.iloc[0]["D/E (pctl)"] == 0.0

    def test_avg_percentile_rank_computed(self):
        """A1 should have high average rank."""
        pg = self._make_mock_peer_groups()
        ratios = self._make_mock_ratios()
        result = compute_peer_percentile_rankings(pg, ratios)

        a1 = result[result["company_id"] == "A1"]
        assert a1.iloc[0]["avg_percentile_rank"] is not None
        assert a1.iloc[0]["avg_percentile_rank"] > 50.0  # should be high

    def test_group_b_two_companies(self):
        """GroupB has 2 companies: B1 (all high), B2 (low)."""
        pg = self._make_mock_peer_groups()
        ratios = self._make_mock_ratios()
        result = compute_peer_percentile_rankings(pg, ratios)

        b1 = result[result["company_id"] == "B1"]
        b2 = result[result["company_id"] == "B2"]
        assert len(b1) == 1
        assert len(b2) == 1
        assert b1.iloc[0]["ROE (pctl)"] == 100.0  # B1 higher
        assert b2.iloc[0]["ROE (pctl)"] == 0.0    # B2 lower

    def test_is_benchmark_preserved(self):
        pg = self._make_mock_peer_groups()
        ratios = self._make_mock_ratios()
        result = compute_peer_percentile_rankings(pg, ratios)

        a1 = result[result["company_id"] == "A1"]
        assert bool(a1.iloc[0]["is_benchmark"]) is True

        a2 = result[result["company_id"] == "A2"]
        assert bool(a2.iloc[0]["is_benchmark"]) is False

    def test_empty_peer_group(self):
        """A peer group with no matching companies should be skipped."""
        pg = pd.DataFrame({
            "id": [1],
            "peer_group_name": ["Empty"],
            "company_id": ["NONEXIST"],
            "is_benchmark": [True],
        })
        ratios = self._make_mock_ratios()
        result = compute_peer_percentile_rankings(pg, ratios)
        # The NonExist company won't match any ratio rows → empty group, skipped
        assert len(result) == 0

    def test_missing_metric_values(self):
        """Company with None for some metrics should still get ranks for others."""
        pg = pd.DataFrame({
            "id": [1, 2],
            "peer_group_name": ["Test", "Test"],
            "company_id": ["T1", "T2"],
            "is_benchmark": [True, False],
        })
        ratios = pd.DataFrame({
            "company_id": ["T1", "T2"],
            "year": [2024, 2024],
            "return_on_equity_pct": [25.0, 15.0],
            "roce_pct": [30.0, 20.0],
            "net_profit_margin_pct": [20.0, None],  # T2 has None NPM
            "debt_to_equity": [0.0, 1.0],
            "interest_coverage": [10.0, 5.0],
            "asset_turnover": [2.0, 1.5],
            "free_cash_flow_cr": [1000.0, 500.0],
            "revenue_cagr_5yr": [20.0, 10.0],
            "pat_cagr_5yr": [25.0, 12.0],
            "eps_cagr_5yr": [20.0, 8.0],
        })
        result = compute_peer_percentile_rankings(pg, ratios)
        assert len(result) == 2
        t2 = result[result["company_id"] == "T2"]
        # Pandas converts None to np.nan in float columns
        # When raw value is NaN, _percent_rank gets np.nan (not None)
        # and computes rank=0 since NaN comparisons all yield False
        assert pd.isna(t2.iloc[0]["Net Profit Margin (raw)"])
        # But other metrics should have valid non-NaN ranks
        assert not pd.isna(t2.iloc[0]["ROE (pctl)"])

    def test_roce_rankings(self):
        """A1 has highest ROCE (30) in GroupA → 100th percentile."""
        pg = self._make_mock_peer_groups()
        ratios = self._make_mock_ratios()
        result = compute_peer_percentile_rankings(pg, ratios)

        a1 = result[result["company_id"] == "A1"]
        assert a1.iloc[0]["ROCE (pctl)"] == 100.0

        a3 = result[result["company_id"] == "A3"]
        assert a3.iloc[0]["ROCE (pctl)"] == 0.0


# ============================================================
# 5. Export module smoke test
# ============================================================

class TestPeerExport:
    def test_export_module_imports(self):
        from src.analytics.peer import export_peer_percentile_rankings
        assert callable(export_peer_percentile_rankings)

    def test_all_function_imports(self):
        names = [
            "_percent_rank",
            "load_peer_groups",
            "load_financial_ratios",
            "compute_peer_percentile_rankings",
            "export_peer_percentile_rankings",
            "load_all_companies",
            "populate_peer_percentiles_table",
        ]
        module = __import__("src.analytics.peer", fromlist=names)
        for name in names:
            assert hasattr(module, name)
