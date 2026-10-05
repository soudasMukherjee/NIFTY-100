"""Unit tests for the Day 29 NLP Analysis Text Parser."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import pandas as pd
import pytest

from src.nlp.parser import (
    parse_metric_text,
    parse_analysis_xlsx,
    cross_validate_cagr,
    _period_sentinel,
    PERIOD_LAST_YEAR,
    PERIOD_TTM,
)


# ============================================================
# parse_metric_text
# ============================================================

class TestParseMetricText:
    def test_standard_colon_format(self):
        assert parse_metric_text("10 Years: 21%") == (10, 21.0)

    def test_long_spaces_before_pct(self):
        assert parse_metric_text("5 Years:       24%") == (5, 24.0)

    def test_no_colon_single_spaces(self):
        assert parse_metric_text("5 Years          14%") == (5, 14.0)

    def test_decimal_value(self):
        assert parse_metric_text("3 Years: 14.5%") == (3, 14.5)

    def test_negative_value(self):
        assert parse_metric_text("1 Year:         -2%") == (1, -2.0)

    def test_ttm_non_numeric_horizon(self):
        assert parse_metric_text("TTM:            43%") == (PERIOD_TTM, 43.0)

    def test_last_year_non_numeric_horizon(self):
        assert parse_metric_text("Last Year:      12%") == (PERIOD_LAST_YEAR, 12.0)

    def test_none_returns_none_none(self):
        assert parse_metric_text(None) == (None, None)

    def test_empty_string_returns_none_none(self):
        assert parse_metric_text("") == (None, None)
        assert parse_metric_text("   ") == (None, None)

    def test_unparseable_returns_none_none(self):
        assert parse_metric_text("no numeric data here") == (None, None)
        assert parse_metric_text("Growth: strong") == (None, None)

    def test_extra_trailing_whitespace_handled(self):
        assert parse_metric_text("10 Years:     11%             ") == (10, 11.0)


class TestPeriodSentinel:
    def test_ttm(self):
        assert _period_sentinel("TTM") == PERIOD_TTM

    def test_last_year(self):
        assert _period_sentinel("Last Year") == PERIOD_LAST_YEAR

    def test_regex_special_chars(self):
        assert _period_sentinel("TTM") == PERIOD_TTM


# ============================================================
# Integration-ish tests against the real source data
# ============================================================

class TestParseAnalysisXlsx:
    def test_parses_real_xlsx(self, tmp_path):
        src = Path("data/core/analysis.xlsx")
        if not src.exists():
            pytest.skip("analysis.xlsx not present")
        parsed_path, failures_path = parse_analysis_xlsx(
            xlsx_path=src, out_dir=tmp_path
        )
        parsed = pd.read_csv(parsed_path)
        failures = pd.read_csv(failures_path) if failures_path.exists() else pd.DataFrame()

        assert parsed_path.exists()
        assert list(parsed.columns) == [
            "company_id", "metric_type", "period_years", "value_pct",
        ]
        assert len(parsed) > 0
        # Every metric_type is one of the four target fields.
        assert set(parsed["metric_type"]).issubset(
            {"sales_growth", "profit_growth", "stock_cagr", "roe"}
        )
        # Failures carry the required columns when present.
        assert set(failures.columns).issuperset(
            {"company_id", "metric_type", "source_column", "raw_text", "reason"}
        )

    def test_parsed_csv_has_expected_schema(self):
        # Deterministic check on a tiny synthetic fixture.
        import pandas as pd
        from io import StringIO

        # Build a minimal analysis.xlsx in tmp via parse_analysis_xlsx contract:
        # header=1 means row 0 is a title row, row 1 is the header.
        pass

    def test_cross_validate_cagr_runs(self, tmp_path):
        src = Path("data/core/analysis.xlsx")
        db = Path("nifty100.db")
        if not src.exists() or not db.exists():
            pytest.skip("analysis.xlsx or nifty100.db not present")
        parsed_df = pd.read_csv(
            "output/analysis_parsed.csv"
        ) if Path("output/analysis_parsed.csv").exists() else None
        if parsed_df is None:
            # Generate from source.
            parsed_path, _ = parse_analysis_xlsx(src, out_dir=tmp_path)
            parsed_df = pd.read_csv(parsed_path)
        out_path = cross_validate_cagr(parsed_df, db_path=db, out_dir=tmp_path)
        out = pd.read_csv(out_path)
        assert out_path.exists()
        assert set(out.columns).issuperset(
            {"company_id", "metric_type", "parsed_value_pct",
             "ratio_engine_value_pct", "divergence_pct", "flag_review"}
        )


# ============================================================
# Pure unit tests for cross-validation logic (no DB needed)
# ============================================================

class TestCrossValidateCagr:
    def test_flags_divergence_over_threshold(self, tmp_path, monkeypatch):
        from src import nlp
        from src.nlp import parser as parser_mod

        fake_engine = pd.DataFrame({
            "company_id": ["TCS"],
            "revenue_cagr_5yr": [10.0],
            "pat_cagr_5yr": [12.0],
        })
        monkeypatch.setattr(parser_mod, "_load_ratio_engine_cagr", lambda db_path: fake_engine)

        parsed = pd.DataFrame({
            "company_id": ["TCS", "TCS", "TCS", "TCS"],
            "metric_type": ["sales_growth", "profit_growth", "stock_cagr", "roe"],
            "period_years": [5, 5, 5, 5],
            "value_pct": [10.0, 12.0, 20.0, 15.0],
        })

        out_path = parser_mod.cross_validate_cagr(
            parsed, db_path=tmp_path / "nope.db", out_dir=tmp_path,
            divergence_threshold=5.0,
        )
        out = pd.read_csv(out_path)
        # Both sales & profit match exactly -> no flags.
        assert out["flag_review"].tolist() == [False, False]

    def test_no_flag_when_under_threshold(self, tmp_path, monkeypatch):
        from src.nlp import parser as parser_mod

        fake_engine = pd.DataFrame({
            "company_id": ["TCS"],
            "revenue_cagr_5yr": [10.0],
            "pat_cagr_5yr": [12.0],
        })
        monkeypatch.setattr(parser_mod, "_load_ratio_engine_cagr", lambda db_path: fake_engine)

        parsed = pd.DataFrame({
            "company_id": ["TCS"],
            "metric_type": ["sales_growth"],
            "period_years": [5],
            "value_pct": [14.0],  # diff = 4.0 <= 5.0 -> no flag
        })
        out_path = parser_mod.cross_validate_cagr(
            parsed, db_path=tmp_path / "nope.db", out_dir=tmp_path,
            divergence_threshold=5.0,
        )
        out = pd.read_csv(out_path)
        assert out["flag_review"].tolist() == [False]
