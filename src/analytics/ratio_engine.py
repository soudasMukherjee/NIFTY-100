"""
Composite Quality Score Engine — Sprint 3 · Day 16

Implements the weighted composite quality score on a 0–100 scale:

    35% Profitability
        ROE   (15%) → _score_roe()
        ROCE  (10%) → _score_roce()
        NPM   (10%) → _score_npm()

    30% Cash Quality
        FCF CAGR (15%)   → _score_fcf_cagr()
        CFO/PAT  (10%)   → _score_cfo_pat_ratio()
        FCF positive (5%) → _score_fcf_positive()

    20% Growth
        Revenue CAGR (10%) → _score_revenue_cagr()
        PAT CAGR     (10%) → _score_pat_cagr()

    15% Leverage
        D/E  (10%) → _score_debt_to_equity()
        ICR  ( 5%) → _score_interest_coverage()

All sub-scores return a float in [0, 100] or None when the input is missing.
If any sub-score in a category is None, the category contribution is proportionally
re-weighted among the available sub-scores within that category.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================
# Scoring helpers — each maps a raw metric to 0..100
# ============================================================

def _score_roe(roe_pct: Optional[float]) -> Optional[float]:
    """Score Return on Equity (0–100).

    Thresholds:
        >= 25 → 100
        >= 20 →  80
        >= 15 →  60
        >= 10 →  40
        >=  5 →  20
        <   5 → linear 0–20 (5 maps to 20, 0 maps to 0)
    """
    if roe_pct is None:
        return None
    v = float(roe_pct)
    if v >= 25:
        return 100.0
    if v >= 20:
        return 80.0
    if v >= 15:
        return 60.0
    if v >= 10:
        return 40.0
    if v >= 5:
        return 20.0
    return max(0.0, (v / 5.0) * 20.0)


def _score_roce(roce_pct: Optional[float]) -> Optional[float]:
    """Score Return on Capital Employed (0–100).

    Thresholds:
        >= 30 → 100
        >= 20 →  80
        >= 15 →  60
        >= 10 →  40
        >=  5 →  20
        <   5 → linear 0–20
    """
    if roce_pct is None:
        return None
    v = float(roce_pct)
    if v >= 30:
        return 100.0
    if v >= 20:
        return 80.0
    if v >= 15:
        return 60.0
    if v >= 10:
        return 40.0
    if v >= 5:
        return 20.0
    return max(0.0, (v / 5.0) * 20.0)


def _score_npm(npm_pct: Optional[float]) -> Optional[float]:
    """Score Net Profit Margin (0–100).

    Thresholds:
        >= 20 → 100
        >= 15 →  80
        >= 10 →  60
        >=  5 →  40
        >=  2 →  20
        <   2 → linear 0–20
    """
    if npm_pct is None:
        return None
    v = float(npm_pct)
    if v >= 20:
        return 100.0
    if v >= 15:
        return 80.0
    if v >= 10:
        return 60.0
    if v >= 5:
        return 40.0
    if v >= 2:
        return 20.0
    return max(0.0, (v / 2.0) * 20.0)


def _score_fcf_cagr(cagr_pct: Optional[float]) -> Optional[float]:
    """Score FCF CAGR (0–100).

    Thresholds:
        >= 20 → 100
        >= 15 →  80
        >= 10 →  60
        >=  5 →  40
        >=  0 →  20
        <   0 →   0
    """
    if cagr_pct is None:
        return None
    v = float(cagr_pct)
    if v >= 20:
        return 100.0
    if v >= 15:
        return 80.0
    if v >= 10:
        return 60.0
    if v >= 5:
        return 40.0
    if v >= 0:
        return 20.0
    return 0.0


def _score_cfo_pat_ratio(ratio: Optional[float]) -> Optional[float]:
    """Score CFO/PAT ratio (0–100).

    Thresholds:
        >= 1.50 → 100
        >= 1.00 →  80
        >= 0.70 →  60
        >= 0.50 →  40
        >= 0.25 →  20
        <  0.25 →   0
    """
    if ratio is None:
        return None
    v = float(ratio)
    if v >= 1.50:
        return 100.0
    if v >= 1.00:
        return 80.0
    if v >= 0.70:
        return 60.0
    if v >= 0.50:
        return 40.0
    if v >= 0.25:
        return 20.0
    return 0.0


def _score_fcf_positive(fcf: Optional[float]) -> Optional[float]:
    """Score FCF positive flag (0 or 100).

    Returns 100 if FCF > 0, 0 if FCF <= 0, None if unknown.
    """
    if fcf is None:
        return None
    return 100.0 if float(fcf) > 0 else 0.0


def _score_revenue_cagr(cagr_pct: Optional[float]) -> Optional[float]:
    """Score Revenue CAGR (0–100).

    Thresholds:
        >= 25 → 100
        >= 20 →  80
        >= 15 →  60
        >= 10 →  40
        >=  5 →  20
        <   5 → linear 0–20
    """
    if cagr_pct is None:
        return None
    v = float(cagr_pct)
    if v >= 25:
        return 100.0
    if v >= 20:
        return 80.0
    if v >= 15:
        return 60.0
    if v >= 10:
        return 40.0
    if v >= 5:
        return 20.0
    return max(0.0, (v / 5.0) * 20.0)


def _score_pat_cagr(cagr_pct: Optional[float]) -> Optional[float]:
    """Score PAT CAGR (0–100).

    Thresholds:
        >= 25 → 100
        >= 20 →  80
        >= 15 →  60
        >= 10 →  40
        >=  5 →  20
        <   5 → linear 0–20
    """
    if cagr_pct is None:
        return None
    v = float(cagr_pct)
    if v >= 25:
        return 100.0
    if v >= 20:
        return 80.0
    if v >= 15:
        return 60.0
    if v >= 10:
        return 40.0
    if v >= 5:
        return 20.0
    return max(0.0, (v / 5.0) * 20.0)


def _score_debt_to_equity(de_ratio: Optional[float]) -> Optional[float]:
    """Score Debt-to-Equity (0–100, lower is better).

    Thresholds:
        = 0.0 → 100  (debt-free)
        <= 0.3 →  80
        <= 0.5 →  60
        <= 1.0 →  40
        <= 2.0 →  20
        >  2.0 →   0
    """
    if de_ratio is None:
        return None
    v = float(de_ratio)
    if v == 0.0:
        return 100.0
    if v <= 0.3:
        return 80.0
    if v <= 0.5:
        return 60.0
    if v <= 1.0:
        return 40.0
    if v <= 2.0:
        return 20.0
    return 0.0


def _score_interest_coverage(icr: Optional[float]) -> Optional[float]:
    """Score Interest Coverage Ratio (0–100, higher is better).

    Thresholds:
        >= 10 → 100
        >=  5 →  80
        >=  3 →  60
        >=  2 →  40
        >=  1 →  20
        <   1 →   0
    """
    if icr is None:
        return None
    v = float(icr)
    if v >= 10:
        return 100.0
    if v >= 5:
        return 80.0
    if v >= 3:
        return 60.0
    if v >= 2:
        return 40.0
    if v >= 1:
        return 20.0
    return 0.0


# ============================================================
# Winsorisation — cap extreme values at P10/P90
# ============================================================

def winsorise_value(
    value: Optional[float],
    p10: Optional[float],
    p90: Optional[float],
) -> Optional[float]:
    """Cap a single value at the given P10/P90 bounds.

    If value < p10 → p10.
    If value > p90 → p90.
    If any input is None → None.
    """
    if value is None or p10 is None or p90 is None:
        return value
    v = float(value)
    p10_v = float(p10)
    p90_v = float(p90)
    if v < p10_v:
        return p10_v
    if v > p90_v:
        return p90_v
    return v


def compute_winsorisation_bounds(
    series: list[Optional[float]],
    lower_quantile: float = 0.10,
    upper_quantile: float = 0.90,
) -> tuple[Optional[float], Optional[float]]:
    """Compute P10 and P90 from a list of values (ignoring None).

    Returns (p10, p90). If insufficient data, returns (None, None).
    """
    clean = [v for v in series if v is not None]
    if len(clean) < 4:  # need at least a few values for meaningful percentiles
        return None, None
    sorted_vals = sorted(clean)
    n = len(sorted_vals)
    p10_idx = max(0, min(n - 1, int(n * lower_quantile)))
    p90_idx = max(0, min(n - 1, int(n * upper_quantile)))
    return sorted_vals[p10_idx], sorted_vals[p90_idx]


# ============================================================
# Sector-relative percentile scoring
# ============================================================

def sector_percentile_score(
    value: Optional[float],
    sector_values: list[Optional[float]],
) -> Optional[float]:
    """Compute a 0-100 score as the percentile rank of `value` within `sector_values`.

    A value at the median → 50.
    A value higher than all peers → 100.
    A value lower than all peers → 0.

    Returns None if value is None or sector_values is empty.
    """
    if value is None or not sector_values:
        return None
    clean = [v for v in sector_values if v is not None]
    if not clean:
        return None
    v = float(value)
    sorted_vals = sorted(clean)
    n = len(sorted_vals)
    # Count how many are strictly less than v
    count_less = sum(1 for x in sorted_vals if x < v)
    # Percentile rank = (count_less / (n - 1)) * 100 for n > 1
    if n <= 1:
        return 50.0  # single company in sector → middle
    rank = (count_less / (n - 1)) * 100.0
    return round(max(0.0, min(100.0, rank)), 2)


def compute_sector_percentile_scores(
    *,
    company_values: dict[str, Optional[float]],  # company_id -> raw value
    sector_map: dict[str, str],  # company_id -> broad_sector
    metric_name: str = "",
) -> dict[str, Optional[float]]:
    """Compute percentile scores per sector for all companies.

    For each company, finds its sector peers, computes percentile rank
    of the company's value within that sector.

    Returns dict of company_id -> sector_percentile_score.
    """
    # Group values by sector
    sector_values: dict[str, list[tuple[str, Optional[float]]]] = {}
    for cid, val in company_values.items():
        sector = sector_map.get(cid, "Unknown")
        if sector not in sector_values:
            sector_values[sector] = []
        sector_values[sector].append((cid, val))

    result: dict[str, Optional[float]] = {}
    for sector, pairs in sector_values.items():
        vals_in_sector = [v for _, v in pairs]
        for cid, val in pairs:
            result[cid] = sector_percentile_score(val, vals_in_sector)

    return result


# ============================================================
# Main composite score function
# ============================================================

def composite_quality_score_v2(
    *,
    # Profitability
    roe_pct: Optional[float] = None,
    roce_pct: Optional[float] = None,
    npm_pct: Optional[float] = None,
    # Cash Quality
    fcf_cagr_5yr: Optional[float] = None,
    cfo_pat_ratio: Optional[float] = None,
    fcf_value: Optional[float] = None,
    # Growth
    revenue_cagr_5yr: Optional[float] = None,
    pat_cagr_5yr: Optional[float] = None,
    # Leverage
    debt_to_equity: Optional[float] = None,
    interest_coverage: Optional[float] = None,
) -> Optional[float]:
    """Composite Quality Score on a 0–100 scale.

    Weights (as per spec):
        35% Profitability: ROE(15) + ROCE(10) + NPM(10)
        30% Cash Quality:  FCF CAGR(15) + CFO/PAT(10) + FCF positive(5)
        20% Growth:        Revenue CAGR(10) + PAT CAGR(10)
        15% Leverage:      D/E(10) + ICR(5)

    If any individual sub-score within a category is missing (None), that
    sub-score's weight is redistributed proportionally among the available
    sub-scores within the same category. If ALL sub-scores in a category
    are missing, that category contributes 0 to the final score.

    Returns a float in [0, 100] or None if all inputs are None.
    """

    # --- Profitability (35%) ---
    profit_scores: list[tuple[Optional[float], float]] = [
        (_score_roe(roe_pct), 15.0),
        (_score_roce(roce_pct), 10.0),
        (_score_npm(npm_pct), 10.0),
    ]
    profitability = _weighted_category(profit_scores, total_weight=35.0)

    # --- Cash Quality (30%) ---
    cash_scores: list[tuple[Optional[float], float]] = [
        (_score_fcf_cagr(fcf_cagr_5yr), 15.0),
        (_score_cfo_pat_ratio(cfo_pat_ratio), 10.0),
        (_score_fcf_positive(fcf_value), 5.0),
    ]
    cash_quality = _weighted_category(cash_scores, total_weight=30.0)

    # --- Growth (20%) ---
    growth_scores: list[tuple[Optional[float], float]] = [
        (_score_revenue_cagr(revenue_cagr_5yr), 10.0),
        (_score_pat_cagr(pat_cagr_5yr), 10.0),
    ]
    growth = _weighted_category(growth_scores, total_weight=20.0)

    # --- Leverage (15%) ---
    leverage_scores: list[tuple[Optional[float], float]] = [
        (_score_debt_to_equity(debt_to_equity), 10.0),
        (_score_interest_coverage(interest_coverage), 5.0),
    ]
    leverage = _weighted_category(leverage_scores, total_weight=15.0)

    total = profitability + cash_quality + growth + leverage

    # If everything was missing, return None
    if total == 0.0 and all(
        s is None
        for scores in [profit_scores, cash_scores, growth_scores, leverage_scores]
        for s, _ in scores
    ):
        return None

    return round(total, 2)


def _weighted_category(
    scores: list[tuple[Optional[float], float]],
    total_weight: float,
) -> float:
    """Compute weighted contribution for a category.

    Parameters
    ----------
    scores : list of (score_or_none, weight)
        Each tuple is (sub_score, sub_weight_in_percent).
    total_weight : float
        Total category weight (e.g. 35.0 for Profitability).

    Returns
    -------
    float
        Contribution to the final composite score.
    """
    available = [(s, w) for s, w in scores if s is not None]
    if not available:
        return 0.0

    actual_total_weight = sum(w for _, w in available)
    contribution = 0.0
    for s, w in available:
        proportion = w / actual_total_weight
        contribution += s * proportion * (total_weight / 100.0)

    return contribution


# ============================================================
# Backward-compatible wrapper (old signature)
# ============================================================

def composite_quality_score(
    *,
    cfo_quality_score: Optional[float],
    fcf_conversion_rate_pct: Optional[float],
) -> Optional[float]:
    """Legacy composite score (Day 12 implementation).

    Delegates to the new v2 engine using None for all other inputs.
    This preserves backward compatibility with existing callers until
    they are migrated.
    """
    # The legacy inputs don't map cleanly to the new formula,
    # so we keep the old logic for backward compatibility.
    if cfo_quality_score is None or fcf_conversion_rate_pct is None:
        return None
    return (float(cfo_quality_score) + float(fcf_conversion_rate_pct) / 100.0) / 2.0

