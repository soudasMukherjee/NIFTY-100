-- ============================================================
-- Nifty 100 Financial Intelligence Platform
-- Sprint 1 · Day 04 — SQLite Database Schema
-- 10 tables · PK/FK enforced · PRAGMA foreign_keys = ON
-- ============================================================

PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------
-- 1. companies  (master table — PK referenced by everything else)
-- ------------------------------------------------------------
DROP TABLE IF EXISTS companies;
CREATE TABLE companies (
    company_id          TEXT PRIMARY KEY,      -- ticker, e.g. 'ABB'
    company_name         TEXT NOT NULL,
    company_logo         TEXT,
    chart_link            TEXT,
    about_company         TEXT,
    website                TEXT,
    nse_profile            TEXT,
    bse_profile            TEXT,
    face_value             REAL,
    book_value             REAL,
    roce_percentage        REAL,
    roe_percentage         REAL
);

-- ------------------------------------------------------------
-- 2. profitandloss  (annual P&L line items)
-- ------------------------------------------------------------
DROP TABLE IF EXISTS profitandloss;
CREATE TABLE profitandloss (
    id                   INTEGER PRIMARY KEY,
    company_id            TEXT NOT NULL,
    year_raw               TEXT NOT NULL,        -- original string, e.g. 'Mar 2024'
    year                    INTEGER NOT NULL,      -- normalized fiscal year, e.g. 2024
    period_type            TEXT NOT NULL DEFAULT 'ANNUAL',  -- ANNUAL | TTM
    sales                   REAL,
    expenses                REAL,
    operating_profit        REAL,
    opm_percentage          REAL,
    other_income            REAL,
    interest                 REAL,
    depreciation             REAL,
    profit_before_tax        REAL,
    tax_percentage           REAL,
    net_profit                REAL,
    eps                       REAL,
    dividend_payout           REAL,
    UNIQUE (company_id, year, period_type),
    FOREIGN KEY (company_id) REFERENCES companies(company_id)
);

-- ------------------------------------------------------------
-- 3. balancesheet
-- ------------------------------------------------------------
DROP TABLE IF EXISTS balancesheet;
CREATE TABLE balancesheet (
    id                   INTEGER PRIMARY KEY,
    company_id            TEXT NOT NULL,
    year_raw               TEXT NOT NULL,
    year                    INTEGER NOT NULL,
    period_type            TEXT NOT NULL DEFAULT 'ANNUAL',
    equity_capital           REAL,
    reserves                  REAL,
    borrowings                 REAL,
    other_liabilities           REAL,
    total_liabilities            REAL,
    fixed_assets                  REAL,
    cwip                            REAL,
    investments                      REAL,
    other_asset                       REAL,
    total_assets                       REAL,
    UNIQUE (company_id, year, period_type),
    FOREIGN KEY (company_id) REFERENCES companies(company_id)
);

-- ------------------------------------------------------------
-- 4. cashflow
-- ------------------------------------------------------------
DROP TABLE IF EXISTS cashflow;
CREATE TABLE cashflow (
    id                   INTEGER PRIMARY KEY,
    company_id            TEXT NOT NULL,
    year_raw               TEXT NOT NULL,
    year                    INTEGER NOT NULL,
    operating_activity        REAL,
    investing_activity          REAL,
    financing_activity            REAL,
    net_cash_flow                   REAL,
    UNIQUE (company_id, year),
    FOREIGN KEY (company_id) REFERENCES companies(company_id)
);

-- ------------------------------------------------------------
-- 5. analysis  (multi-horizon growth metrics — one row per company)
-- ------------------------------------------------------------
DROP TABLE IF EXISTS analysis;
CREATE TABLE analysis (
    id                   INTEGER PRIMARY KEY,
    company_id            TEXT NOT NULL UNIQUE,
    sales_growth_years        INTEGER,     -- horizon parsed out of "10 Years: 21%"
    sales_growth_pct           REAL,
    profit_growth_years          INTEGER,
    profit_growth_pct             REAL,
    stock_cagr_years                INTEGER,
    stock_cagr_pct                   REAL,
    roe_years                         INTEGER,
    roe_pct                            REAL,
    FOREIGN KEY (company_id) REFERENCES companies(company_id)
);

-- ------------------------------------------------------------
-- 6. documents  (annual report links)
-- ------------------------------------------------------------
DROP TABLE IF EXISTS documents;
CREATE TABLE documents (
    id                   INTEGER PRIMARY KEY,
    company_id            TEXT NOT NULL,
    year                    INTEGER NOT NULL,
    annual_report_url        TEXT,
    UNIQUE (company_id, year),
    FOREIGN KEY (company_id) REFERENCES companies(company_id)
);

-- ------------------------------------------------------------
-- 7. prosandcons
-- ------------------------------------------------------------
DROP TABLE IF EXISTS prosandcons;
CREATE TABLE prosandcons (
    id                   INTEGER PRIMARY KEY,
    company_id            TEXT NOT NULL,
    pros                    TEXT,
    cons                     TEXT,
    FOREIGN KEY (company_id) REFERENCES companies(company_id)
);

-- ------------------------------------------------------------
-- 8. sectors  (supplementary)
-- ------------------------------------------------------------
DROP TABLE IF EXISTS sectors;
CREATE TABLE sectors (
    id                   INTEGER PRIMARY KEY,
    company_id            TEXT NOT NULL UNIQUE,
    broad_sector            TEXT,
    sub_sector                TEXT,
    index_weight_pct           REAL,
    market_cap_category          TEXT,
    FOREIGN KEY (company_id) REFERENCES companies(company_id)
);

-- ------------------------------------------------------------
-- 9. stock_prices  (supplementary — daily/periodic OHLCV)
-- ------------------------------------------------------------
DROP TABLE IF EXISTS stock_prices;
CREATE TABLE stock_prices (
    id                   INTEGER PRIMARY KEY,
    company_id            TEXT NOT NULL,
    date                    TEXT NOT NULL,     -- ISO 'YYYY-MM-DD'
    open_price               REAL,
    high_price                 REAL,
    low_price                    REAL,
    close_price                    REAL,
    volume                          INTEGER,
    adjusted_close                    REAL,
    UNIQUE (company_id, date),
    FOREIGN KEY (company_id) REFERENCES companies(company_id)
);

-- ------------------------------------------------------------
-- 10. financial_ratios  (supplementary — precomputed ratios; validated
--      against Sprint 2's own ratio engine as a cross-check)
-- ------------------------------------------------------------
DROP TABLE IF EXISTS financial_ratios;
CREATE TABLE financial_ratios (
    id                   INTEGER PRIMARY KEY,
    company_id            TEXT NOT NULL,
    year                    INTEGER NOT NULL,

    -- Profitability
    net_profit_margin_pct     REAL,
    operating_profit_margin_pct REAL,
    return_on_equity_pct           REAL,

    -- Leverage / Coverage
    debt_to_equity                   REAL,
    interest_coverage                  REAL,

    -- Efficiency
    asset_turnover                       REAL,

    -- Cash flow KPIs
    free_cash_flow_cr                      REAL,
    fcf_conversion_rate_pct               REAL,
    cash_from_operations_cr              REAL,
    capex_cr                              REAL,

    -- Capital allocation / per-share
    earnings_per_share                   REAL,
    book_value_per_share                REAL,

    -- Dividend
    dividend_payout_ratio_pct          REAL,

    -- Debt
    total_debt_cr                       REAL,

    -- Growth (3y & 5y windows)
    revenue_cagr_3yr                   REAL,
    de_yoy_change_pct                  REAL,
    revenue_cagr_5yr                   REAL,
    pat_cagr_5yr                       REAL,
    eps_cagr_5yr                       REAL,
    fcf_cagr_5yr                       REAL,

    -- Composite
    composite_quality_score           REAL,

    UNIQUE (company_id, year),
    FOREIGN KEY (company_id) REFERENCES companies(company_id)
);


-- ------------------------------------------------------------
-- market_cap and peer_groups are additional supplementary sets present
-- in the source data (market_cap.xlsx, peer_groups.xlsx). The sprint
-- ticket lists 10 tables; these two are folded in here so no source
-- data is dropped on the floor. Remove this block if you want to hold
-- strictly to the 10-table count and defer these to Sprint 4/9.
-- ------------------------------------------------------------
DROP TABLE IF EXISTS market_cap;
CREATE TABLE market_cap (
    id                   INTEGER PRIMARY KEY,
    company_id            TEXT NOT NULL,
    year                    INTEGER NOT NULL,
    market_cap_crore          REAL,
    enterprise_value_crore      REAL,
    pe_ratio                      REAL,
    pb_ratio                        REAL,
    ev_ebitda                         REAL,
    dividend_yield_pct                  REAL,
    UNIQUE (company_id, year),
    FOREIGN KEY (company_id) REFERENCES companies(company_id)
);

DROP TABLE IF EXISTS peer_groups;
CREATE TABLE peer_groups (
    id                   INTEGER PRIMARY KEY,
    peer_group_name       TEXT NOT NULL,
    company_id              TEXT NOT NULL,
    is_benchmark               INTEGER NOT NULL DEFAULT 0,  -- 0/1 boolean
    FOREIGN KEY (company_id) REFERENCES companies(company_id)
);

DROP TABLE IF EXISTS peer_percentiles;
CREATE TABLE peer_percentiles (
    id              INTEGER PRIMARY KEY,
    company_id      TEXT NOT NULL,
    peer_group_name TEXT NOT NULL,
    metric          TEXT NOT NULL,
    value           REAL,
    percentile_rank REAL,
    year            INTEGER NOT NULL,
    FOREIGN KEY (company_id) REFERENCES companies(company_id)
);

-- ------------------------------------------------------------
-- Indexes for common query patterns (company + year lookups)
-- ------------------------------------------------------------
CREATE INDEX idx_pl_company_year ON profitandloss(company_id, year);
CREATE INDEX idx_bs_company_year ON balancesheet(company_id, year);
CREATE INDEX idx_cf_company_year ON cashflow(company_id, year);
CREATE INDEX idx_ratios_company_year ON financial_ratios(company_id, year);
CREATE INDEX idx_prices_company_date ON stock_prices(company_id, date);
CREATE INDEX idx_mcap_company_year ON market_cap(company_id, year);
