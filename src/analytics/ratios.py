from __future__ import annotations

import logging
from typing import Optional, Sequence

# Re-export cashflow KPIs from dedicated module for backward compatibility.
from src.analytics.cashflow_kpis import (
    capex_intensity,
    cfo_quality_score,
    fcf_conversion_rate,
    free_cash_flow,
)

logger = logging.getLogger(__name__)


def net_profit_margin(net_profit: float, sales: float) -> Optional[float]:

    """Net Profit Margin = net_profit / sales * 100.

    Returns None when sales == 0.
    """
    if sales == 0:
        return None
    return (net_profit / sales) * 100


def operating_profit_margin(
    operating_profit: float,
    sales: float,
    opm_percentage: float | None = None,
    *,
    logger: logging.Logger | None = None,
    tolerance_pct: float = 1.0,
) -> Optional[float]:
    """Operating Profit Margin.

    Computes operating_profit / sales * 100.

    If `opm_percentage` is provided, cross-check the computed value against it
    and log when drift exceeds `tolerance_pct` (percentage-point tolerance).

    Returns None when sales == 0.
    """
    if sales == 0:
        return None

    computed = (operating_profit / sales) * 100

    if opm_percentage is not None:
        logg = logger or logging.getLogger(__name__)
        try:
            stated = float(opm_percentage)
            diff = abs(computed - stated)
            if diff > tolerance_pct:
                logg.warning(
                    "OPM%% drift: computed=%.4f stated=%.4f diff=%.4f tolerance=%.4f",
                    computed,
                    stated,
                    diff,
                    tolerance_pct,
                )
        except Exception:
            logg.warning(
                "OPM% cross-check skipped due to invalid opm_percentage=%r",
                opm_percentage,
            )

    return computed


def return_on_equity(net_profit: float, equity_capital: float, reserves: float) -> Optional[float]:
    """Return on Equity (ROE): net_profit / (equity_capital + reserves) * 100.

    Returns None when (equity_capital + reserves) <= 0.
    """
    denom = equity_capital + reserves
    if denom <= 0:
        return None
    return (net_profit / denom) * 100


def return_on_capital_employed(
    *,
    ebit: float,
    equity_capital: float,
    reserves: float,
    borrowings: float,
) -> Optional[float]:
    """Return on Capital Employed (ROCE): EBIT / (equity + reserves + borrowings) * 100.

    Returns None when denominator <= 0.
    """
    denom = equity_capital + reserves + borrowings
    if denom <= 0:
        return None
    return (ebit / denom) * 100


def return_on_assets(net_profit: float, total_assets: float) -> Optional[float]:
    """Return on Assets (ROA): net_profit / total_assets * 100.

    Returns None when total_assets == 0.
    """
    if total_assets == 0:
        return None
    return (net_profit / total_assets) * 100


def is_financials_sector(broad_sector: str | None) -> bool:
    return (broad_sector or "").strip().lower() == "financials"


def net_debt(
    *,
    borrowings: float,
    investments: float,
) -> float:
    """Net Debt.

    Proxy: borrowings - investments.
    """
    return float(borrowings) - float(investments)


def debt_to_equity(
    *,
    borrowings: float,
    equity_capital: float,
    reserves: float,
) -> float | None:

    """Debt-to-Equity ratio (D/E).

    Formula: borrowings / (equity_capital + reserves)

    Returns 0 (not None) when borrowings == 0.

    Returns None when denominator <= 0.
    """
    denom = equity_capital + reserves
    if borrowings == 0:
        return 0.0
    if denom <= 0:
        return None
    return borrowings / denom


def icr_label_for_debt_free(is_debt_free: bool) -> str:
    return "Debt Free" if is_debt_free else ""


def icr_warning_flag(
    *,
    interest_coverage_ratio_pct: float | None,
) -> bool:
    """ICR warning flag.

    True when ICR < 1.5.
    """
    if interest_coverage_ratio_pct is None:
        return False
    return float(interest_coverage_ratio_pct) < 1.5


def interest_coverage_ratio(
    *,
    operating_profit: float,
    other_income: float,
    interest: float,
) -> float | None:

    """Interest Coverage Ratio (ICR).

    ICR = (operating_profit + other_income) / interest.

    Returns None when interest == 0.
    """
    if interest == 0:
        return None
    return (operating_profit + other_income) / interest


def high_leverage_flag(
    *,
    debt_to_equity_pct: float | None,
    broad_sector: str | None,
) -> bool:

    """High leverage flag.

    If D/E > 5 and company is NOT in Financials sector => True.
    Otherwise False.
    """
    if debt_to_equity_pct is None:
        return False
    if is_financials_sector(broad_sector):
        return False
    return float(debt_to_equity_pct) > 5.0


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


def asset_turnover(
    *,
    sales: float,
    total_assets: float,
) -> float | None:

    """Asset Turnover.

    Asset Turnover = sales / total_assets

    Returns None when total_assets == 0.
    """
    if total_assets == 0:
        return None
    return float(sales) / float(total_assets)


def roce_with_sector_benchmark(

    *,
    broad_sector: str | None,
    roce_pct: Optional[float],
    sector_roce_benchmark_pct: float | None,
) -> Optional[float]:
    """ROCE helper.


    Spec note: for companies in Financials broad_sector, use a sector-relative
    ROCE benchmark instead of an absolute threshold.

    This function returns the value that should be used for evaluation:
      - if Financials: returns (roce_pct - benchmark)
      - else: returns roce_pct

    If required inputs are missing, returns None.
    """
    if roce_pct is None:
        return None

    if is_financials_sector(broad_sector):
        if sector_roce_benchmark_pct is None:
            return None
        return roce_pct - float(sector_roce_benchmark_pct)

    return roce_pct

