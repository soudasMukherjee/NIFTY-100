-- ============================================================
-- Sprint 1 · Day 07 — Exploratory Queries (10)
-- Run against nifty100.db to demo the loaded, validated database
-- ============================================================

-- 1. Row counts across all 12 tables (sanity check against exit criteria)
SELECT 'companies' t, COUNT(*) n FROM companies
UNION ALL SELECT 'profitandloss', COUNT(*) FROM profitandloss
UNION ALL SELECT 'balancesheet', COUNT(*) FROM balancesheet
UNION ALL SELECT 'cashflow', COUNT(*) FROM cashflow
UNION ALL SELECT 'analysis', COUNT(*) FROM analysis
UNION ALL SELECT 'documents', COUNT(*) FROM documents
UNION ALL SELECT 'prosandcons', COUNT(*) FROM prosandcons
UNION ALL SELECT 'sectors', COUNT(*) FROM sectors
UNION ALL SELECT 'stock_prices', COUNT(*) FROM stock_prices
UNION ALL SELECT 'financial_ratios', COUNT(*) FROM financial_ratios
UNION ALL SELECT 'market_cap', COUNT(*) FROM market_cap
UNION ALL SELECT 'peer_groups', COUNT(*) FROM peer_groups;

-- 2. Companies with the fewest years of P&L history (data-coverage check, DQ-13)
SELECT company_id, COUNT(DISTINCT year) AS years_covered
FROM profitandloss
WHERE period_type = 'ANNUAL'
GROUP BY company_id
ORDER BY years_covered ASC
LIMIT 10;

-- 3. Top 10 companies by average operating profit margin (last 5 available years)
SELECT company_id, ROUND(AVG(opm_percentage), 2) AS avg_opm_pct
FROM profitandloss
WHERE period_type = 'ANNUAL' AND opm_percentage IS NOT NULL
GROUP BY company_id
ORDER BY avg_opm_pct DESC
LIMIT 10;

-- 4. Sector-level revenue concentration: total latest-year sales by broad sector
SELECT s.broad_sector, ROUND(SUM(p.sales), 0) AS total_sales_cr
FROM profitandloss p
JOIN sectors s ON p.company_id = s.company_id
WHERE p.year = (SELECT MAX(year) FROM profitandloss WHERE period_type = 'ANNUAL')
GROUP BY s.broad_sector
ORDER BY total_sales_cr DESC;

-- 5. Companies where balance sheet fails to balance beyond 1% (DQ-04 flagged rows)
SELECT company_id, year, total_assets, total_liabilities,
       ROUND(ABS(total_assets - total_liabilities) * 100.0 /
             MAX(ABS(total_assets), ABS(total_liabilities)), 2) AS diff_pct
FROM balancesheet
WHERE total_assets IS NOT NULL AND total_liabilities IS NOT NULL
  AND ABS(total_assets - total_liabilities) * 100.0 /
      MAX(ABS(total_assets), ABS(total_liabilities)) >= 1.0
ORDER BY diff_pct DESC
LIMIT 15;

-- 6. Debt-heavy companies: highest debt_to_equity from financial_ratios (latest year)
SELECT fr.company_id, fr.year, fr.debt_to_equity
FROM financial_ratios fr
WHERE fr.year = (SELECT MAX(year) FROM financial_ratios)
  AND fr.debt_to_equity IS NOT NULL
ORDER BY fr.debt_to_equity DESC
LIMIT 10;

-- 7. Stock price volatility proxy: avg daily high-low spread % per company
SELECT company_id,
       ROUND(AVG((high_price - low_price) / NULLIF(low_price, 0) * 100), 2) AS avg_daily_range_pct
FROM stock_prices
GROUP BY company_id
ORDER BY avg_daily_range_pct DESC
LIMIT 10;

-- 8. Peer group membership counts (sanity check DQ on peer_groups)
SELECT peer_group_name, COUNT(*) AS n_members,
       SUM(is_benchmark) AS n_benchmarks
FROM peer_groups
GROUP BY peer_group_name
ORDER BY n_members DESC;

-- 9. Companies with the strongest 10-year compounded profit growth (from analysis table)
SELECT company_id, profit_growth_years, profit_growth_pct
FROM analysis
WHERE profit_growth_years = 10
ORDER BY profit_growth_pct DESC
LIMIT 10;

-- 10. Cross-table join demo: full latest-year snapshot for a single company
--     (swap 'TCS' for any valid company_id)
SELECT c.company_name, s.broad_sector, p.year, p.sales, p.net_profit,
       b.total_assets, cf.net_cash_flow, fr.return_on_equity_pct
FROM companies c
JOIN sectors s ON c.company_id = s.company_id
LEFT JOIN profitandloss p ON c.company_id = p.company_id
    AND p.year = (SELECT MAX(year) FROM profitandloss WHERE company_id = c.company_id)
LEFT JOIN balancesheet b ON c.company_id = b.company_id AND b.year = p.year
LEFT JOIN cashflow cf ON c.company_id = cf.company_id AND cf.year = p.year
LEFT JOIN financial_ratios fr ON c.company_id = fr.company_id AND fr.year = p.year
WHERE c.company_id = 'TCS';
