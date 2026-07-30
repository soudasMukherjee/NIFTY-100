from __future__ import annotations

import math

import sys
from pathlib import Path

# Make `src/` importable when running tests from repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from src.analytics.cagr import (
    cagr,
    pat_cagr,
    pat_cagr_windows,
    revenue_cagr,
    revenue_cagr_windows,
)



def test_cagr_basic_values():
    # start=100, end=121, periods=2 => (121/100)^(1/2)-1 = 0.1 => 10%
    assert cagr(start=100.0, end=121.0, periods=2) == 10.0


def test_cagr_start_zero_returns_none():
    assert cagr(start=0.0, end=10.0, periods=2) is None


def test_cagr_periods_zero_returns_none():
    assert cagr(start=100.0, end=121.0, periods=0) is None


def test_revenue_cagr_window_3_uses_first_and_last_and_periods_window_minus_1():
    # Provide 3 values for a 3-year window. periods = 2
    # start=100 end=121 periods=2 => 10%
    vals = [100.0, 110.0, 121.0]
    assert revenue_cagr(revenues=vals, window_years=3) == 10.0


def test_pat_cagr_insufficient_history_returns_none():
    vals = [100.0, 120.0]  # only 2 values
    assert pat_cagr(pats=vals, window_years=3) is None


def test_revenue_cagr_windows_returns_none_for_10_when_not_enough():
    # 5 values => only 3 and 5 windows computable.
    revenues = [100.0, 110.0, 121.0, 133.1, 146.41]  # 100*(1.1)^k
    out = revenue_cagr_windows(revenues)

    assert out[3] == 10.0
    assert out[5] == 10.0
    assert out[10] is None


def test_pat_cagr_windows_negative_start_returns_valid_cagr():
    # CAGR works with negative start too mathematically (no guard except start==0).
    # start=-100 end=-121 periods=2 => (-121/-100)=1.21 => 10%
    pats = [-100.0, -110.0, -121.0, -133.1, -146.41]
    out = pat_cagr_windows(pats)
    assert out[3] == 10.0
    assert out[5] == 10.0

