# Day 18 — Peer Percentile Rankings

## Steps

- [x] Step 1: Create `src/analytics/peer.py` — loads peer_groups.xlsx, computes PERCENT_RANK for 10 metrics within each of 11 peer groups
- [x] Step 2: Run the module to generate `output/peer_percentile_rankings.csv`
- [x] Step 3: Create `tests/analytics/test_peer.py` with 40 tests
- [x] Step 4: Run tests — **40/40 PASS**
- [x] Step 5: Populate `peer_percentiles` SQLite table with columns: company_id, peer_group_name, metric, value, percentile_rank, year
- [x] Step 6: Replace Composite Score with ROCE as the 10th metric
- [x] Step 7: Fix metric labels: NPM → Net Profit Margin, ICR → Interest Coverage
- [x] Step 8: Add 'No peer group assigned' message for companies not in any peer group (no error raised)
- [x] Step 9: Add `peer_percentiles` table to `db/schema.sql`

