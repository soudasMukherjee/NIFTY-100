from __future__ import annotations

import math
from typing import Optional, Sequence, Tuple

# EPS CAGR flags
EPS_DECLINE_TO_LOSS = "DECLINE_TO_LOSS"
EPS_TURNAROUND = "TURNAROUND"
EPS_BOTH_NEGATIVE = "BOTH_NEGATIVE"
EPS_ZERO_BASE = "ZERO_BASE"
EPS_INSUFFICIENT = "INSUFFICIENT"


def cagr(start: float, end: float, periods: int) -> Optional[float]:
    """Compound Annual Growth Rate (CAGR).

    Formula (as requested): ((end/start)^(1/n) - 1) x 100

    Args:
        start: Starting value (must be non-zero).
        end: Ending value.
        periods: Number of years (must be > 0).

    Returns:
        CAGR in percentage terms, or None when inputs are invalid.
    """

    if periods <= 0:
        return None
    if start == 0:
        return None

    start_f = float(start)
    end_f = float(end)

    ratio = end_f / start_f

    # Edge case: negative ratio means start and end have opposite signs.
    # CAGR is undefined for mixed-sign windows (would yield complex numbers).
    if ratio < 0:
        return None

    growth_factor = ratio ** (1.0 / float(periods))

    # Keep deterministic equality for unit tests.
    return round((growth_factor - 1.0) * 100.0, 10)


def _window_cagr(values: Sequence[float], window_years: int) -> Optional[float]:
    if window_years <= 0:
        return None
    if values is None:
        return None
    if len(values) < window_years:
        return None

    start = values[0]
    end = values[window_years - 1]
    # For N-year window, periods = N-1 between the first and last points.
    return cagr(start=start, end=end, periods=window_years - 1)


def revenue_cagr(revenues: Sequence[float], window_years: int) -> Optional[float]:
    """Revenue CAGR over a window.

    Expects `revenues` ordered oldest -> newest and sized to the window.

    Note: If you provide exactly `window_years` values (e.g., 3 values for a
    3-year window), the CAGR uses periods = window_years - 1.
    """

    return _window_cagr(values=revenues, window_years=window_years)


def pat_cagr(pats: Sequence[float], window_years: int) -> Optional[float]:
    """PAT (net profit) CAGR over a window.

    Expects `pats` ordered oldest -> newest and sized to the window.

    Note: If you provide exactly `window_years` values (e.g., 3 values for a
    3-year window), the CAGR uses periods = window_years - 1.
    """

    return _window_cagr(values=pats, window_years=window_years)


def revenue_cagr_windows(revenues: Sequence[float]) -> dict[int, Optional[float]]:
    """Compute Revenue CAGR for 3, 5, and 10 year windows."""

    def last_window(size: int) -> Sequence[float] | None:
        if revenues is None or len(revenues) < size:
            return None
        return revenues[-size:]

    out: dict[int, Optional[float]] = {3: None, 5: None, 10: None}
    for size in out.keys():
        wnd = last_window(size)
        if wnd is not None:
            out[size] = revenue_cagr(revenues=wnd, window_years=size)
    return out


def pat_cagr_windows(pats: Sequence[float]) -> dict[int, Optional[float]]:
    """Compute PAT CAGR for 3, 5, and 10 year windows."""

    def last_window(size: int) -> Sequence[float] | None:
        if pats is None or len(pats) < size:
            return None
        return pats[-size:]

    out: dict[int, Optional[float]] = {3: None, 5: None, 10: None}
    for size in out.keys():
        wnd = last_window(size)
        if wnd is not None:
            out[size] = pat_cagr(pats=wnd, window_years=size)
    return out


def eps_cagr(
    *,
    eps_start: float,
    eps_end: float,
    periods: int,
) -> tuple[Optional[float], Optional[str]]:
    """EPS CAGR with edge-case flags.

    Returns (cagr_pct, flag).
    - Valid computation: (value, None)
    - Any invalid edge-case: (None, flag)

    Rules:
      * Positive + Positive => compute normally
      * Positive + Negative => None with flag DECLINE_TO_LOSS
      * Negative + Positive => None with flag TURNAROUND
      * Negative + Negative => None with flag BOTH_NEGATIVE
      * Zero base (eps_start == 0) => None with flag ZERO_BASE
    """

    if periods <= 0:
        return None, None

    if eps_start == 0:
        return None, EPS_ZERO_BASE

    start_f = float(eps_start)
    end_f = float(eps_end)

    start_pos = start_f > 0
    end_pos = end_f > 0

    if start_pos and end_pos:
        return cagr(start=start_f, end=end_f, periods=periods), None
    if start_pos and not end_pos:
        return None, EPS_DECLINE_TO_LOSS
    if not start_pos and end_pos:
        return None, EPS_TURNAROUND
    # both are not positive => includes negative+negative and zero-ending cases
    return None, EPS_BOTH_NEGATIVE


def free_cash_flow_cagr(fcf_values: Sequence[float], window_years: int) -> Optional[float]:
    """Free Cash Flow CAGR over a window.

    Expects `fcf_values` ordered oldest -> newest and sized to the window.
    Uses the same pattern as revenue_cagr.

    Note: FCF can be negative. CAGR is undefined when start <= 0 (negative or zero),
    in which case returns None.
    """
    return _window_cagr(values=fcf_values, window_years=window_years)


def free_cash_flow_cagr_windows(fcf_values: Sequence[float]) -> dict[int, Optional[float]]:
    """Compute Free Cash Flow CAGR for 3, 5, and 10 year windows."""

    def last_window(size: int) -> Sequence[float] | None:
        if fcf_values is None or len(fcf_values) < size:
            return None
        return fcf_values[-size:]

    out: dict[int, Optional[float]] = {3: None, 5: None, 10: None}
    for size in out.keys():
        wnd = last_window(size)
        if wnd is not None:
            out[size] = free_cash_flow_cagr(fcf_values=wnd, window_years=size)
    return out


def eps_cagr_windows(
    eps_by_year: Sequence[float],
) -> dict[int, tuple[Optional[float], Optional[str]]]:

    """Compute EPS CAGR for 3, 5, and 10 year windows.

    Assumptions:
      - `eps_by_year` ordered oldest -> newest
      - window N uses eps at indices [-N] and [-1]
      - CAGR uses periods = window_years - 1

    Edge:
      - insufficient data => (None, INSUFFICIENT)
    """

    out: dict[int, tuple[Optional[float], Optional[str]]] = {
        3: (None, None),
        5: (None, None),
        10: (None, None),
    }

    for window_years in out.keys():
        if eps_by_year is None or len(eps_by_year) < window_years:
            out[window_years] = (None, EPS_INSUFFICIENT)
            continue

        start = eps_by_year[-window_years]
        end = eps_by_year[-1]
        periods = window_years - 1

        cagr_pct, flag = eps_cagr(eps_start=start, eps_end=end, periods=periods)
        out[window_years] = (cagr_pct, flag)

    return out
