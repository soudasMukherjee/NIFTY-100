from __future__ import annotations

import logging
from typing import Optional, Sequence


logger = logging.getLogger(__name__)


def free_cash_flow(
    *,
    operating_activity: float,
    investing_activity: float,
) -> float:
    """Free Cash Flow (FCF).

    FCF = operating_activity + investing_activity

    Negative values are allowed.
    """
    return float(operating_activity) + float(investing_activity)


def cfo_quality_score(
    *,
    cfo_by_year: Sequence[float],
    pat_by_year: Sequence[float],
    years: int = 5,
) -> float | None:
    """CFO Quality Score.

    Score = average over N years of CFO / PAT.

    - Uses the first/last N elements from the provided sequences (oldest -> newest).
    - Returns None if PAT == 0 for any year used.

    Thresholds (for downstream labeling):
      > 1.0 High Quality
      0.5-1.0 Moderate
      < 0.5 Accrual Risk
    """
    if years <= 0:
        return None
    if cfo_by_year is None or pat_by_year is None:
        return None
    if len(cfo_by_year) < years or len(pat_by_year) < years:
        return None

    cfo_vals = list(map(float, cfo_by_year[-years:]))
    pat_vals = list(map(float, pat_by_year[-years:]))

    ratios: list[float] = []
    for cfo, pat in zip(cfo_vals, pat_vals):
        if pat == 0:
            return None
        ratios.append(cfo / pat)

    return sum(ratios) / float(years)


def fcf_conversion_rate(
    *,
    free_cash_flow: float,
    operating_profit: float,
) -> float | None:
    """FCF Conversion Rate.

    FCF Conversion Rate = (Free Cash Flow / Operating Profit) * 100.

    Returns None when operating_profit == 0.

    Note: FCF can be negative; that is allowed.
    """
    if operating_profit == 0:
        return None
    return float(free_cash_flow) / float(operating_profit) * 100


def capex_intensity(
    *,
    investing_activity: float,
    sales: float,
) -> float | None:
    """CapEx Intensity.

    Intensity = abs(investing_activity) / sales * 100

    Returns None when sales == 0.
    """
    if sales == 0:
        return None
    return abs(float(investing_activity)) / float(sales) * 100

