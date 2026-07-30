from __future__ import annotations

import sys
from pathlib import Path

# Make `src/` importable when running tests from repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from src.analytics.ratios import (
    capex_intensity,
    cfo_quality_score,
    fcf_conversion_rate,
    free_cash_flow,
)



def test_free_cash_flow_allows_negative():
    # 10 + (-30) = -20
    assert free_cash_flow(operating_activity=10.0, investing_activity=-30.0) == -20.0


def test_cfo_quality_score_high_quality_average_gt_1():
    # Ratios: 1.2, 1.1, 1.3, 1.0, 1.5 => avg = 1.22
    assert (
        cfo_quality_score(
            cfo_by_year=[120, 110, 130, 100, 150],
            pat_by_year=[100, 100, 100, 100, 100],
            years=5,
        )
        == 1.22
    )


def test_cfo_quality_score_moderate_between_0_5_and_1():
    # Ratios: 0.6, 0.8, 0.7, 0.9, 0.5 => avg = 0.7
    assert (
        cfo_quality_score(
            cfo_by_year=[60, 80, 70, 90, 50],
            pat_by_year=[100, 100, 100, 100, 100],
            years=5,
        )
        == 0.7
    )


def test_cfo_quality_score_accrual_risk_below_0_5():
    # Ratios: 0.1, 0.2, 0.3, 0.4, 0.49 => avg = 0.298
    assert (
        cfo_quality_score(
            cfo_by_year=[10, 20, 30, 40, 49],
            pat_by_year=[100, 100, 100, 100, 100],
            years=5,
        )
        == 0.298
    )


def test_cfo_quality_score_returns_none_if_any_pat_is_zero():
    assert (
        cfo_quality_score(
            cfo_by_year=[100, 110, 120, 130, 140],
            pat_by_year=[100, 0, 120, 130, 140],
            years=5,
        )
        is None
    )


def test_capex_intensity_none_when_sales_zero():
    assert capex_intensity(investing_activity=-50.0, sales=0.0) is None


def test_fcf_conversion_rate_none_when_operating_profit_zero():
    assert fcf_conversion_rate(free_cash_flow=-20.0, operating_profit=0.0) is None


def test_fcf_conversion_rate_normal():
    # (-20)/50*100 = -40
    assert fcf_conversion_rate(free_cash_flow=-20.0, operating_profit=50.0) == -40.0


def test_capex_intensity_uses_abs_and_percent():
    # abs(-20)/200*100 = 10
    assert capex_intensity(investing_activity=-20.0, sales=200.0) == 10.0


