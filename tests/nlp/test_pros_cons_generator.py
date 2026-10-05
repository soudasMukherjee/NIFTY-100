"""Unit tests for the Day 30 NLP Auto Pros/Cons Generator."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import pandas as pd
import pytest

import src.nlp.pros_cons_generator as pcg
from src.nlp.pros_cons_generator import (
    ALL_RULES,
    CON_RULES,
    PRO_RULES,
    CompanyData,
    evaluate_company,
    generate_pros_cons,
    _pro_assets_growing,
    _pro_debt_free,
    _pro_dividend_yield,
    _pro_eps_cagr,
    _pro_fcf_positive,
    _pro_icr_high,
    _pro_operating_leverage,
    _pro_opm_high,
    _pro_pat_cagr,
    _pro_revenue_cagr,
    _pro_roe_high,
    _pro_roe_improving,
)


def _make_data(**overrides) -> CompanyData:
    """Build a CompanyData with sensible defaults, overridable per test."""
    defaults = dict(
        company_id="TEST",
        latest_roe=25.0,
        latest_opm=30.0,
        latest_de=0.0,
        latest_icr=15.0,
        latest_fcf=100.0,
        revenue_cagr_5yr=20.0,
        pat_cagr_5yr=25.0,
        eps_cagr_5yr=18.0,
        dividend_yield_pct=3.0,
        roe_history=[22.0, 23.0, 24.0, 25.0],
        fcf_history=[10.0, 20.0, 30.0, 40.0, 50.0],
        de_history=[0.2, 0.15, 0.1, 0.0],
        assets_history=[1000.0, 1200.0, 1400.0, 1600.0],
    )
    defaults.update(overrides)
    return CompanyData(**defaults)


# ============================================================
# Registry structure
# ============================================================

class TestRuleRegistry:
    def test_12_pro_rules(self):
        assert len(PRO_RULES) == 12

    def test_12_con_rules(self):
        assert len(CON_RULES) == 12

    def test_24_total_rules(self):
        assert len(ALL_RULES) == 24

    def test_rule_texts_present(self):
        for rule in ALL_RULES:
            assert rule.rule_id
            assert rule.kind in ("pro", "con")
            assert rule.text
            assert callable(rule.predicate)


# ============================================================
# Pro Rule predicates
# ============================================================

class TestProRoeHigh:
    def test_roe_above_20_sustained_3y(self):
        assert _pro_roe_high(_make_data(roe_history=[19.0, 21.0, 22.0, 23.0]))

    def test_roe_not_sustained(self):
        assert not _pro_roe_high(_make_data(roe_history=[19.0, 21.0, 22.0]))

    def test_insufficient_history(self):
        assert not _pro_roe_high(_make_data(roe_history=[21.0, 22.0]))


class TestProFcfPositive:
    def test_fcf_positive_5y(self):
        assert _pro_fcf_positive(_make_data(fcf_history=[1.0, 2.0, 3.0, 4.0, 5.0]))

    def test_fcf_negative_one_year(self):
        assert not _pro_fcf_positive(_make_data(fcf_history=[1.0, 2.0, -3.0, 4.0, 5.0]))

    def test_insufficient_history(self):
        assert not _pro_fcf_positive(_make_data(fcf_history=[1.0, 2.0, 3.0]))


class TestProDebtFree:
    def test_zero_debt(self):
        assert _pro_debt_free(_make_data(latest_de=0.0))

    def test_has_debt(self):
        assert not _pro_debt_free(_make_data(latest_de=0.5))

    def test_none_debt(self):
        assert not _pro_debt_free(_make_data(latest_de=None))


class TestProRevenueCagr:
    def test_above_15(self):
        assert _pro_revenue_cagr(_make_data(revenue_cagr_5yr=16.0))

    def test_below_15(self):
        assert not _pro_revenue_cagr(_make_data(revenue_cagr_5yr=14.0))


class TestProOpmHigh:
    def test_opm_above_25(self):
        assert _pro_opm_high(_make_data(latest_opm=26.0))

    def test_opm_below_25(self):
        assert not _pro_opm_high(_make_data(latest_opm=24.0))


class TestProPatCagr:
    def test_above_20(self):
        assert _pro_pat_cagr(_make_data(pat_cagr_5yr=21.0))

    def test_below_20(self):
        assert not _pro_pat_cagr(_make_data(pat_cagr_5yr=19.0))


class TestProIcrHigh:
    def test_icr_above_10(self):
        assert _pro_icr_high(_make_data(latest_icr=11.0, latest_de=0.5))

    def test_debt_free_always_true(self):
        assert _pro_icr_high(_make_data(latest_icr=1.0, latest_de=0.0))

    def test_low_icr_with_debt(self):
        assert not _pro_icr_high(_make_data(latest_icr=5.0, latest_de=0.5))


class TestProDividendYield:
    def test_yield_above_2_with_positive_fcf(self):
        assert _pro_dividend_yield(_make_data(dividend_yield_pct=2.5, latest_fcf=100.0))

    def test_yield_above_2_but_negative_fcf(self):
        assert not _pro_dividend_yield(_make_data(dividend_yield_pct=2.5, latest_fcf=-1.0))

    def test_yield_at_2(self):
        assert not _pro_dividend_yield(_make_data(dividend_yield_pct=2.0, latest_fcf=100.0))


class TestProEpsCagr:
    def test_above_15(self):
        assert _pro_eps_cagr(_make_data(eps_cagr_5yr=16.0))

    def test_below_15(self):
        assert not _pro_eps_cagr(_make_data(eps_cagr_5yr=14.0))


class TestProRoeImproving:
    def test_improving_3y(self):
        assert _pro_roe_improving(_make_data(roe_history=[15.0, 18.0, 21.0, 24.0]))

    def test_not_improving(self):
        assert not _pro_roe_improving(_make_data(roe_history=[24.0, 21.0, 18.0, 15.0]))

    def test_insufficient_history(self):
        assert not _pro_roe_improving(_make_data(roe_history=[10.0, 12.0]))


class TestProOperatingLeverage:
    def test_revenue_cagr_gt_pat_cagr(self):
        assert _pro_operating_leverage(_make_data(revenue_cagr_5yr=20.0, pat_cagr_5yr=15.0))

    def test_revenue_cagr_lt_pat_cagr(self):
        assert not _pro_operating_leverage(_make_data(revenue_cagr_5yr=10.0, pat_cagr_5yr=25.0))


class TestProAssetsGrowing:
    def test_assets_grow_debt_falls(self):
        assert _pro_assets_growing(_make_data(
            assets_history=[1000.0, 1500.0, 2000.0],
            de_history=[0.5, 0.3, 0.1],
        ))

    def test_assets_grow_debt_rises(self):
        assert not _pro_assets_growing(_make_data(
            assets_history=[1000.0, 1500.0, 2000.0],
            de_history=[0.1, 0.3, 0.5],
        ))

    def test_insufficient_history(self):
        assert not _pro_assets_growing(_make_data(
            assets_history=[1000.0],
            de_history=[0.5],
        ))


# ============================================================
# evaluate_company
# ============================================================

class TestEvaluateCompany:
    def test_returns_matched_rules(self):
        data = _make_data()
        rows = evaluate_company(data)
        assert isinstance(rows, list)
        for r in rows:
            assert set(r.keys()) == {"company_id", "type", "rule_id", "text"}
            assert r["company_id"] == "TEST"
            assert r["type"] in ("pro", "con")

    def test_can_pass_subset_of_rules(self):
        data = _make_data()
        rows = evaluate_company(data, rules=PRO_RULES)
        assert all(r["type"] == "pro" for r in rows)

    def test_weak_company_gets_cons(self):
        data = _make_data(
            latest_roe=5.0,
            latest_opm=8.0,
            latest_de=2.0,
            latest_icr=1.0,
            latest_fcf=-10.0,
            revenue_cagr_5yr=3.0,
            pat_cagr_5yr=2.0,
            eps_cagr_5yr=1.0,
            dividend_yield_pct=0.5,
            roe_history=[20.0, 15.0, 10.0, 5.0],
            fcf_history=[10.0, 5.0, -1.0, -5.0, -10.0],
        )
        rows = evaluate_company(data)
        types = {r["type"] for r in rows}
        assert "con" in types


# ============================================================
# Integration against real DB
# ============================================================

class TestGenerateProsCons:
    def test_generates_csv_from_real_db(self, tmp_path):
        db = Path("nifty100.db")
        if not db.exists():
            pytest.skip("nifty100.db not present")
        generated_path, summary_path = generate_pros_cons(db_path=db, out_dir=tmp_path)
        generated = pd.read_csv(generated_path)
        summary = pd.read_csv(summary_path)

        assert generated_path.exists()
        assert list(generated.columns) == ["company_id", "type", "rule_id", "text"]
        assert len(generated) > 0
        assert set(generated["type"]).issubset({"pro", "con"})
        assert set(generated["rule_id"]).issubset({r.rule_id for r in ALL_RULES})

        assert summary_path.exists()
        assert list(summary.columns) == ["company_id", "pros_count", "cons_count", "total_count"]
        assert len(summary) > 0
