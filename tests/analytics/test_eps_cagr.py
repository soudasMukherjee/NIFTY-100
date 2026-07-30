from __future__ import annotations

import sys
from pathlib import Path

# Make `src/` importable when running tests from repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from src.analytics.cagr import (
    EPS_BOTH_NEGATIVE,
    EPS_DECLINE_TO_LOSS,
    EPS_INSUFFICIENT,
    EPS_TURNAROUND,
    EPS_ZERO_BASE,
    eps_cagr,
    eps_cagr_windows,
)


def test_eps_cagr_positive_positive_computes():
    # 100 -> 121 over 2 periods => 10%
    val, flag = eps_cagr(eps_start=100.0, eps_end=121.0, periods=2)
    assert val == 10.0
    assert flag is None


def test_eps_cagr_zero_base_returns_none_zero_base():
    val, flag = eps_cagr(eps_start=0.0, eps_end=10.0, periods=2)
    assert val is None
    assert flag == EPS_ZERO_BASE


def test_eps_cagr_positive_negative_decline_to_loss():
    val, flag = eps_cagr(eps_start=100.0, eps_end=-121.0, periods=2)
    assert val is None
    assert flag == EPS_DECLINE_TO_LOSS


def test_eps_cagr_negative_positive_turnaround():
    val, flag = eps_cagr(eps_start=-100.0, eps_end=121.0, periods=2)
    assert val is None
    assert flag == EPS_TURNAROUND


def test_eps_cagr_negative_negative_both_negative_returns_none():
    val, flag = eps_cagr(eps_start=-100.0, eps_end=-121.0, periods=2)
    assert val is None
    assert flag == EPS_BOTH_NEGATIVE


def test_eps_cagr_windows_insufficient_for_10():
    eps_by_year = [1.0, 1.1, 1.21, 1.331, 1.4641]  # 5 values
    out = eps_cagr_windows(eps_by_year)

    # 3-year and 5-year windows computable, 10-year not.
    assert out[10][0] is None
    assert out[10][1] == EPS_INSUFFICIENT


def test_eps_cagr_windows_decline_to_loss_flag_for_3():
    # 3-year window uses eps_by_year[-3] as start and [-1] as end.
    eps_by_year = [-1.0, 0.5, -2.0, -1.0]
    # For window_years=3, start=eps_by_year[-3] = 0.5 (positive), end=eps_by_year[-1] = -1.0 (negative)
    # => DECLINE_TO_LOSS
    out = eps_cagr_windows(eps_by_year)
    assert out[3][0] is None
    assert out[3][1] == EPS_DECLINE_TO_LOSS



