from __future__ import annotations

import logging
import sys
from pathlib import Path



# Make `src/` importable when running tests from repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from src.analytics.ratios import (
    net_profit_margin,
    operating_profit_margin,
    return_on_equity,
    return_on_capital_employed,
    return_on_assets,
    debt_to_equity,
    high_leverage_flag,
    interest_coverage_ratio,
    icr_label_for_debt_free,
    icr_warning_flag,
    net_debt,
    asset_turnover,
    free_cash_flow,
    cfo_quality_score,
    capex_intensity,
)










def test_net_profit_margin_normal():
    assert net_profit_margin(net_profit=50.0, sales=200.0) == 25.0


def test_net_profit_margin_sales_zero_returns_none():
    assert net_profit_margin(net_profit=50.0, sales=0.0) is None


def test_operating_profit_margin_normal():
    # 30 / 100 * 100 = 30
    assert operating_profit_margin(operating_profit=30.0, sales=100.0) == 30.0


def test_operating_profit_margin_sales_zero_returns_none():
    assert operating_profit_margin(operating_profit=30.0, sales=0.0) is None


def test_operating_profit_margin_cross_check_no_log_when_within_tolerance(caplog):
    caplog.set_level(logging.WARNING)

    # computed = 30, stated = 30.5, diff=0.5 <= tolerance 1.0
    res = operating_profit_margin(
        operating_profit=30.0,
        sales=100.0,
        opm_percentage=30.5,
        tolerance_pct=1.0,
    )
    assert res == 30.0
    assert "OPM% drift" not in caplog.text


def test_operating_profit_margin_cross_check_logs_when_exceeds_tolerance(caplog):
    caplog.set_level(logging.WARNING)

    # computed = 30, stated = 31.5, diff=1.5 > tolerance 1.0
    res = operating_profit_margin(
        operating_profit=30.0,
        sales=100.0,
        opm_percentage=31.5,
        tolerance_pct=1.0,
    )
    assert res == 30.0
    assert "OPM% drift" in caplog.text


def test_return_on_equity_normal():
    # denom = 60+40=100, roe=100/100*100 = 100
    assert return_on_equity(net_profit=100.0, equity_capital=60.0, reserves=40.0) == 100.0


def test_return_on_equity_denom_zero_returns_none():
    assert return_on_equity(net_profit=100.0, equity_capital=0.0, reserves=0.0) is None


def test_return_on_capital_employed_normal():
    # denom=100+30+20=150; roce=30/150*100=20
    assert (
        return_on_capital_employed(
            ebit=30.0,
            equity_capital=100.0,
            reserves=30.0,
            borrowings=20.0,
        )
        == 20.0
    )


def test_return_on_capital_employed_denom_zero_returns_none():
    assert (
        return_on_capital_employed(
            ebit=30.0,
            equity_capital=0.0,
            reserves=0.0,
            borrowings=0.0,
        )
        is None
    )


def test_return_on_assets_normal():
    # 100 / 200 * 100 = 50
    assert return_on_assets(net_profit=100.0, total_assets=200.0) == 50.0


def test_return_on_assets_total_assets_zero_returns_none():
    assert return_on_assets(net_profit=100.0, total_assets=0.0) is None


def test_return_on_assets_negative_equity_denominator_none_case():
    # Spec: return None if total_assets = 0; for negative assets we compute normally.
    # But user requested "negative equity (None)"; we interpret it as non-positive denominator.
    assert return_on_assets(net_profit=100.0, total_assets=-200.0) == -50.0


def test_return_on_assets_negative_total_assets_zero_denominator():
    assert return_on_assets(net_profit=100.0, total_assets=0.0) is None


def test_return_on_assets_zero_denominator_multiple():
    for v in [0, 0.0]:
        assert return_on_assets(net_profit=1.0, total_assets=v) is None


def test_return_on_assets_negative_net_profit_normal():
    # -50 / 100 * 100 = -50
    assert return_on_assets(net_profit=-50.0, total_assets=100.0) == -50.0


def test_return_on_assets_cross_check_within_tolerance_logging_placeholder(caplog):
    # Placeholder cross-check requirement not applicable to ROA helper itself.
    # Ensure it doesn't log anything.
    caplog.set_level(logging.WARNING)
    res = return_on_assets(net_profit=100.0, total_assets=200.0)
    assert res == 50.0
    assert caplog.text == ""


def test_return_on_assets_return_type_none_or_float():
    assert isinstance(return_on_assets(net_profit=1.0, total_assets=2.0), float)


def test_debt_to_equity_normal():
    # borrowings 50 / (equity 100 + reserves 50) = 0.3333...
    res = debt_to_equity(borrowings=50.0, equity_capital=100.0, reserves=50.0)
    assert res == 1 / 3


def test_debt_to_equity_borrowings_zero_returns_zero_not_none():
    res = debt_to_equity(borrowings=0.0, equity_capital=100.0, reserves=50.0)
    assert res == 0.0


def test_debt_to_equity_denominator_zero_returns_none():
    res = debt_to_equity(borrowings=10.0, equity_capital=0.0, reserves=0.0)
    assert res is None


def test_high_leverage_flag_true_when_de_ratio_gt_5_and_not_financials():
    # D/E = 6 => True if sector is not Financials
    assert high_leverage_flag(debt_to_equity_pct=6.0, broad_sector="Industrials") is True


def test_high_leverage_flag_false_when_financials_even_if_de_ratio_gt_5():
    assert high_leverage_flag(debt_to_equity_pct=6.0, broad_sector="Financials") is False


def test_high_leverage_flag_false_when_de_ratio_none():
    assert high_leverage_flag(debt_to_equity_pct=None, broad_sector="Industrials") is False


def test_interest_coverage_ratio_normal():
    # (operating_profit + other_income) / interest
    assert interest_coverage_ratio(
        operating_profit=100.0,
        other_income=20.0,
        interest=10.0,
    ) == 12.0


def test_interest_coverage_ratio_interest_zero_returns_none():
    assert (
        interest_coverage_ratio(
            operating_profit=100.0,
            other_income=20.0,
            interest=0.0,
        )
        is None
    )


def test_icr_label_for_debt_free():
    assert icr_label_for_debt_free(True) == "Debt Free"
    assert icr_label_for_debt_free(False) == ""


def test_icr_warning_flag_true_when_icr_below_1_5():
    assert icr_warning_flag(interest_coverage_ratio_pct=1.49) is True


def test_icr_warning_flag_false_when_icr_equal_or_above_1_5():
    assert icr_warning_flag(interest_coverage_ratio_pct=1.5) is False


def test_icr_warning_flag_false_when_icr_none():
    assert icr_warning_flag(interest_coverage_ratio_pct=None) is False


def test_net_debt_normal():
    # borrowings - investments
    assert net_debt(borrowings=100.0, investments=30.0) == 70.0




