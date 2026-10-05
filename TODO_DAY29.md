# Day 29 — NLP Analysis Text Parser

## Sprint 5 · Epics 07, 08 & 09 — Cash Flow Intelligence + Reports + NLP

### Goal (Day 29)
Parse `analysis.xlsx` text fields via regex into structured metrics with parse-failure
logging and Ratio Engine cross-validation.

### Steps
- [x] Create TODO_DAY29.md (this file)
- [x] Step 1: Create `src/nlp/__init__.py` package marker
- [x] Step 2: Create `src/nlp/parser.py` with:
  - [x] `parse_metric_text()` — regex extraction (period years + value %)
  - [x] `parse_analysis_xlsx()` — writes `output/analysis_parsed.csv`
  - [x] Failure logging to `output/parse_failures.csv`
  - [x] `cross_validate_cagr()` — compare parsed vs Ratio Engine (financial_ratios)
        CAGR; flag divergence > 5% → `output/cagr_cross_validation.csv`
- [x] Step 3: Create `tests/nlp/test_parser.py` — unit tests (19 tests)
- [x] Step 4: Run parser CLI + verify outputs (analysis_parsed.csv, parse_failures.csv, cagr_cross_validation.csv)
- [x] Step 5: Run pytest for NLP tests — 19 passed; full suite 357 passed
- [x] Step 6: Remove temporary inspection scripts (_inspect_analysis.py, _inspect_fr.py)

## Day 29 — Verification Summary

| Check | Result |
|-------|--------|
| `output/analysis_parsed.csv` | 80 rows (20 companies × 4 metrics), schema: company_id, metric_type, period_years, value_pct ✅ |
| `output/parse_failures.csv` | 0 failures — all source text parsed ✅ |
| `output/cagr_cross_validation.csv` | 8 rows (4 companies × 2 metrics), 1 flagged (SBILIFE sales_growth divergence 7.76%) ✅ |
| NLP unit tests | 19 passed ✅ |
| Full test suite | **357 passed, 0 failures** ✅ |
| Regex handling | Standard `<N> Years: <val>%`, no-colon, negative values, decimals, TTM, Last Year ✅ |

