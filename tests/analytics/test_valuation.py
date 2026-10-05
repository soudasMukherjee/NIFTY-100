from __future__ import annotations

import pandas as pd
from pandas.testing import assert_frame_equal

from src.analytics.valuation import (
    build_valuation_summary,
    compute_5yr_median_pe,
)


def test_compute_5yr_median_pe_returns_latest_five_year_median():
    history = pd.DataFrame(
        [
            {"company_id": "AAA", "year": 2019, "pe_ratio": 10.0},
            {"company_id": "AAA", "year": 2020, "pe_ratio": 12.0},
            {"company_id": "AAA", "year": 2021, "pe_ratio": 14.0},
            {"company_id": "AAA", "year": 2022, "pe_ratio": 16.0},
            {"company_id": "AAA", "year": 2023, "pe_ratio": 18.0},
            {"company_id": "AAA", "year": 2024, "pe_ratio": 20.0},
            {"company_id": "BBB", "year": 2024, "pe_ratio": 30.0},
        ]
    )

    median_series = compute_5yr_median_pe(history)

    assert median_series.loc["AAA"] == 16.0
    assert median_series.loc["BBB"] == 30.0


def test_build_valuation_summary_flags_and_pct_calculations():
    valuation_base = pd.DataFrame(
        [
            {
                "company_id": "AAA",
                "company_name": "Alpha",
                "broad_sector": "Tech",
                "market_cap_crore": 100.0,
                "pe_ratio": 30.0,
                "pb_ratio": 4.0,
                "ev_ebitda": 12.0,
                "free_cash_flow_cr": 5.0,
            },
            {
                "company_id": "BBB",
                "company_name": "Beta",
                "broad_sector": "Tech",
                "market_cap_crore": 200.0,
                "pe_ratio": 10.0,
                "pb_ratio": 2.0,
                "ev_ebitda": 8.0,
                "free_cash_flow_cr": 4.0,
            },
        ]
    )

    market_cap_history = pd.DataFrame(
        [
            {"company_id": "AAA", "year": 2024, "pe_ratio": 30.0},
            {"company_id": "AAA", "year": 2023, "pe_ratio": 32.0},
            {"company_id": "AAA", "year": 2022, "pe_ratio": 28.0},
            {"company_id": "AAA", "year": 2021, "pe_ratio": 26.0},
            {"company_id": "AAA", "year": 2020, "pe_ratio": 24.0},
            {"company_id": "BBB", "year": 2024, "pe_ratio": 10.0},
            {"company_id": "BBB", "year": 2023, "pe_ratio": 12.0},
            {"company_id": "BBB", "year": 2022, "pe_ratio": 11.0},
            {"company_id": "BBB", "year": 2021, "pe_ratio": 9.0},
            {"company_id": "BBB", "year": 2020, "pe_ratio": 8.0},
        ]
    )

    result = build_valuation_summary(valuation_base, market_cap_history)

    expected = pd.DataFrame(
        [
            {
                "company_id": "AAA",
                "company_name": "Alpha",
                "sector": "Tech",
                "P/E": 30.0,
                "P/B": 4.0,
                "EV/EBITDA": 12.0,
                "FCF_yield_pct": 5.0,
                "5yr_median_PE": 28.0,
                "PE_vs_sector_median_pct": 150.0,
                "flag": "Fair",
            },
            {
                "company_id": "BBB",
                "company_name": "Beta",
                "sector": "Tech",
                "P/E": 10.0,
                "P/B": 2.0,
                "EV/EBITDA": 8.0,
                "FCF_yield_pct": 2.0,
                "5yr_median_PE": 10.0,
                "PE_vs_sector_median_pct": 50.0,
                "flag": "Discount",
            },
        ]
    )

    assert_frame_equal(result.reset_index(drop=True), expected)
