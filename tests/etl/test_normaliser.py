"""
Sprint 1 · Day 02 — 35+ unit tests for normaliser.py
20 for normalize_year(), 15 for normalize_ticker()
Run: pytest tests/etl/test_normaliser.py -v
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "etl"))
from normaliser import normalize_year, normalize_ticker, NormalisationError


# ============================================================
# normalize_year() — 20 tests
# ============================================================

def test_year_mar_2024():
    assert normalize_year("Mar 2024") == (2024, "ANNUAL")

def test_year_dec_2012():
    assert normalize_year("Dec 2012") == (2012, "ANNUAL")

def test_year_dash_format():
    assert normalize_year("Mar-13") == (2013, "ANNUAL")

def test_year_dash_format_2():
    assert normalize_year("Mar-24") == (2024, "ANNUAL")

def test_year_ttm():
    year, ptype = normalize_year("TTM", current_year=2026)
    assert ptype == "TTM"
    assert year == 2026

def test_year_ttm_case_insensitive():
    _, ptype = normalize_year("ttm")
    assert ptype == "TTM"

def test_year_sep_2024_offcycle():
    assert normalize_year("Sep 2024") == (2024, "ANNUAL")

def test_year_two_digit_pivot_low():
    # 00-49 -> 2000s
    assert normalize_year("Mar-05")[0] == 2005

def test_year_two_digit_pivot_high():
    # 50-99 -> 1900s
    assert normalize_year("Mar-95")[0] == 1995

def test_year_full_four_digit():
    assert normalize_year("Mar 2020")[0] == 2020

def test_year_whitespace_tolerant():
    assert normalize_year("  Mar 2020  ") == (2020, "ANNUAL")

def test_year_none_raises():
    with pytest.raises(NormalisationError):
        normalize_year(None)

def test_year_empty_string_raises():
    with pytest.raises(NormalisationError):
        normalize_year("")

def test_year_garbage_raises():
    with pytest.raises(NormalisationError):
        normalize_year("not-a-year")

def test_year_malformed_quarter_suffix_raises():
    # Real dirty data found in profitandloss.xlsx: 'Mar 2023 15'
    with pytest.raises(NormalisationError):
        normalize_year("Mar 2023 15")

def test_year_malformed_9m_suffix_raises():
    # Real dirty data found in profitandloss.xlsx: 'Mar 2016 9m'
    with pytest.raises(NormalisationError):
        normalize_year("Mar 2016 9m")

def test_year_out_of_range_raises():
    with pytest.raises(NormalisationError):
        normalize_year("Mar 1800")

def test_year_bad_month_raises():
    with pytest.raises(NormalisationError):
        normalize_year("Xyz 2020")

def test_year_jan_month():
    assert normalize_year("Jan 2021")[0] == 2021

def test_year_all_months_parse():
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    for m in months:
        year, ptype = normalize_year(f"{m} 2020")
        assert year == 2020 and ptype == "ANNUAL"


# ============================================================
# normalize_ticker() — 15 tests
# ============================================================

def test_ticker_basic_upper():
    assert normalize_ticker("abb") == "ABB"

def test_ticker_already_upper():
    assert normalize_ticker("ABB") == "ABB"

def test_ticker_strips_whitespace():
    assert normalize_ticker("  ABB  ") == "ABB"

def test_ticker_removes_internal_whitespace():
    assert normalize_ticker("ADANI ENT") == "ADANIENT"

def test_ticker_mixed_case():
    assert normalize_ticker("AdaniEnt") == "ADANIENT"

def test_ticker_none_raises():
    with pytest.raises(NormalisationError):
        normalize_ticker(None)

def test_ticker_empty_raises():
    with pytest.raises(NormalisationError):
        normalize_ticker("")

def test_ticker_whitespace_only_raises():
    with pytest.raises(NormalisationError):
        normalize_ticker("   ")

def test_ticker_allows_numbers():
    assert normalize_ticker("m&m") == "M&M"

def test_ticker_allows_ampersand():
    assert normalize_ticker("M&M") == "M&M"

def test_ticker_allows_hyphen():
    assert normalize_ticker("TATA-MOTORS") == "TATA-MOTORS"

def test_ticker_rejects_special_chars():
    with pytest.raises(NormalisationError):
        normalize_ticker("ABB@#$")

def test_ticker_idempotent():
    once = normalize_ticker("abb")
    twice = normalize_ticker(once)
    assert once == twice == "ABB"

def test_ticker_real_sample_zydus():
    assert normalize_ticker(" zyduslife ") == "ZYDUSLIFE"

def test_ticker_real_sample_ultracemco():
    assert normalize_ticker("ultracemco") == "ULTRACEMCO"
