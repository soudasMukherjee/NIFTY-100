# Sprint 4 — Day 22–28: Streamlit Dashboard + Valuation (55 SP)

## Sprint Goal
Fully working 8-screen Streamlit dashboard on localhost:8501 that loads without
errors for all 92 tickers. Valuation module produces `output/valuation_summary.xlsx`
with FCF yield, P/E flags, and overvaluation/discount labels. CSV export works on
the screener screen.

## Root-Cause Fixes (critical)

- [x] Step 0: Investigate current state — identified critical bugs:
      1. `src/dashboard/utils/db.py` DB_PATH resolves to `src/nifty100.db` (wrong dir)
      2. `financial_ratios` has duplicate/mixed-type year rows (text `'Mar 2024'` + int `2024`)
      3. `MAX(year)` subqueries on mixed types return wrong latest-year rows
      4. 2 companies (ATGL, SBIN) have no `financial_ratios` rows → need graceful handling
      5. `07_capital.py` can crash on NULL cashflow activity values
      6. `03_screener.py` `_prepare_results` produced duplicate `broad_sector` columns → KeyError
      7. `04_peers.py` treated `is_benchmark` (0/1 ints from SQLite) as boolean mask → crash

## Phase 1 — Data layer fixes

- [x] Step 1: Fix `src/dashboard/utils/db.py` — DB_PATH root resolution + robust `MAX(CAST(year AS INTEGER))`
- [x] Step 2: Write + run DB cleanup migration — remove stale text-year rows from `financial_ratios`
- [x] Step 3: Re-verify data integrity (distinct pairs, latest-year coverage, no NULL composite gaps)

## Phase 2 — Dashboard page fixes

- [x] Step 4: Fix `07_capital.py` — handle NULL/NaN cashflow activity values
- [x] Step 5: Fix `01_home.py` — N/A guards for empty year data + robust top-5 sort
- [x] Step 6: Fix `02_profile.py` — partial-data tickers (ATGL/SBIN) show N/A + pros/cons without crashing
- [x] Step 7: Fix `03_screener.py` — merge company_name only (avoid duplicate broad_sector KeyError)
- [x] Step 8: Fix `04_peers.py` — cast `is_benchmark` to bool before boolean masking
- [x] Step 9: Verify all 8 pages render for all 92 tickers (incl. partial-data tickers ATGL, SBIN)
- [x] Step 10: Ensure `N/A` displayed for missing metrics (no crashes)

## Phase 3 — Valuation module re-verification

- [x] Step 11: Re-run `src/analytics/valuation.py` against cleaned data
- [x] Step 12: Confirm `output/valuation_summary.xlsx` (92 rows, FCF yield, flags) + `valuation_flags.csv`
- [x] Flag distribution: 48 Fair / 30 Discount / 14 Caution

## Phase 4 — Testing & QA

- [x] Step 13: Run full test suite — **338 passed, 0 failures**
- [x] Step 14: Smoke-test all 8 dashboard pages via patched render — ALL PASSED
- [x] Step 15: Company Profile page renders all 92 tickers (avg 0.05s, max 0.18s < 3s target)
- [x] Step 16: Trends page renders all 92 tickers
- [x] Step 17: Screener extreme sliders (all-min and all-max strict) — no crash, correct result labels
- [x] Step 18: Reports page renders with `Report unavailable` badge handling
- [x] Step 19: Update TODO.md with completion status

## QA Summary (Day 27)

| Check | Result |
|-------|--------|
| 8 dashboard pages render | ALL PASSED (real nifty100.db) |
| Profile screen — all 92 tickers | ALL PASSED |
| Trends screen — all 92 tickers | ALL PASSED |
| Profile load time (5 tickers target <3s) | avg 0.05s / max 0.18s ✅ |
| Partial-data tickers (ATGL, SBIN) | render with N/A, no crash ✅ |
| Screener extreme sliders | no crash, correct count label ✅ |
| Unit tests | **338 passed, 0 failures** |
| valuation_summary.xlsx | 92 companies, FCF yield, P/E flags ✅ |
| valuation_flags.csv | only Caution (14) + Discount (30) rows ✅ |
| Screener CSV download | works (well-formed CSV of visible columns) ✅ |

