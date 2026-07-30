# Nifty 100 Financial Intelligence Platform — Sprint 1: Data Foundation

ETL pipeline that loads 12 source Excel files (7 core + 5 supplementary) into a
validated SQLite database (`nifty100.db`), enforcing 16 data quality rules.

## Quickstart

```bash
pip install -r requirements.txt
make load        # build schema + load all 12 files -> nifty100.db, output/load_audit.csv
make validate     # run DQ-01..DQ-16 -> output/validation_failures.csv
make test          # 35+ unit tests on normaliser.py
python3 src/etl/manual_review.py   # Day 06 spot-check of 5 random companies
```

## Structure

```
db/schema.sql              10-table SQLite schema, PK/FK, PRAGMA foreign_keys=ON
src/etl/normaliser.py       normalize_year(), normalize_ticker(), parse_horizon_metric()
src/etl/loader.py           reads all 12 files, applies normalisation, loads DB
src/etl/validator.py        DQ-01..DQ-16, writes validation_failures.csv
src/etl/manual_review.py    Day 06 5-company spot check
tests/etl/test_normaliser.py  35 unit tests (20 year, 15 ticker)
notebooks/exploratory_queries.sql   10 demo queries
output/                     load_audit.csv, validation_failures.csv (generated)
```

## What Sprint 1 actually found in this dataset

Running the pipeline against the real source files surfaces genuine data
quality issues — this is the point of Sprint 1, not a bug in the loader:

- **Orphan tickers**: `WIPRO`, `ZYDUSLIFE`, `AGTL`, `ULTRACEMCO`, and others
  appear in `profitandloss` / `balancesheet` / `cashflow` / `documents` /
  `analysis` / `financial_ratios` but are **not** among the 92 rows in
  `companies.xlsx`. These rows are rejected at load time (FK integrity) and
  logged in `load_audit.csv`.
- **Malformed year strings**: `'Mar 2023 15'`, `'Mar 2016 9m'` in
  `profitandloss.xlsx` don't match any known period format and are rejected
  rather than silently mis-parsed.
- **121 CRITICAL DQ failures** on the loaded rows, dominated by
  `stock_prices` rows where `open`/`close` fall outside the `[low, high]`
  range (DQ-14), plus one company (`ADANIENSOL`, 2014) with zero sales
  (DQ-06).
- **649 WARNING-level** findings — mostly URL formatting (DQ-10) and OPM%
  vs. computed operating-margin drift (DQ-05) — logged for the Day 06
  manual review, not blocking.

Because the true source has 92 companies but child tables reference more
than 92 distinct tickers, `SELECT COUNT(*) FROM companies` still returns 92
(the exit criterion), but the loader rejects the orphaned child rows rather
than dropping the FK constraint or fabricating company records. Decide
before Day 05 sign-off whether those extra tickers should instead be added
to `companies` — if source data for them exists elsewhere, that's the
correct fix rather than permanently rejecting the rows.

## Design decisions worth knowing about

- **`normalize_year`** resolves on **calendar year of the statement**, not
  a fiscal-year label, so join keys stay unambiguous. `TTM` rows are kept
  and tagged `period_type='TTM'` rather than dropped, so trend queries can
  filter with `WHERE period_type='ANNUAL'`.
- **2-digit years pivot at 50** (`Mar-13` → 2013, `Mar-95` → 1995).
- **`market_cap` and `peer_groups`** are included as extra tables beyond
  the ticket's listed 10 — no source file is silently dropped. If you need
  to hold strictly to 10 tables, fold `market_cap` into `financial_ratios`
  and defer `peer_groups` to its Sprint 4 module.
