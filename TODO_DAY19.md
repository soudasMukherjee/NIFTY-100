# Day 19 — Radar Charts

## Steps to Complete

- [x] 1. Explore codebase — peer.py, ratio_engine.py, composite_score_export.py, schema
- [x] 2. Plan approved — create radar_charts.py module
- [x] 3. Created `src/analytics/radar_charts.py` with:
  - [x] 3a. METRICS definition (8 axes: ROE, ROCE, NPM, D/E, FCF Score, PAT CAGR 5yr, Rev CAGR 5yr, Composite Score)
  - [x] 3b. `load_data()` — loads latest ratios + ROCE + peer groups (handles mixed year types)
  - [x] 3c. `normalize_to_0_100()` — min-max normalization per peer group, inverts D/E
  - [x] 3d. `_make_radar_chart()` — matplotlib polar plot with filled polygon + dashed peer avg
  - [x] 3e. `_make_standalone_chart()` — bar chart comparing company composite vs Nifty 100 avg
  - [x] 3f. `export_all_radar_charts()` — main orchestrator
- [x] 4. Run completed — **90 charts exported** (55 peer-group radar + 35 standalone bar charts)
- [ ] 5. Create test file `tests/analytics/test_radar_charts.py` (pending)

