# Day 20 — Peer Comparison Excel Report

## Steps

- [ ] 1. Create `src/analytics/peer_comparison_xlsx.py` with:
  - [ ] 1a. 20-metric definition + data loading from DB (financial_ratios, companies, market_cap, peer_groups)
  - [ ] 1b. Percentile rank computation per peer group for each metric
  - [ ] 1c. XLSX generation with 11 sheets, 42 columns (company_id, company_name, 20 raw + 20 pctl)
  - [ ] 1d. Color-coding: green (≥75), yellow (25-75), red (≤25)
  - [ ] 1e. Benchmark row highlight (gold/amber)
  - [ ] 1f. Summary row with peer group median
- [ ] 2. Run the module → verify `output/peer_comparison.xlsx` is created
- [ ] 3. Create `tests/analytics/test_peer_comparison_xlsx.py`

