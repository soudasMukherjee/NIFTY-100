# Day 13 — Bank ROCE Carve-Out & Edge Case Log

## Checklist
- [ ] Regenerate/verify `nifty100.db` contains `companies` rows with `roce_percentage` and `roe_percentage`.
- [ ] Implement ROCE cross-check: computed ROCE vs `companies.roce_percentage` and log anomalies (>5%) to `output/ratio_edge_cases.log`.
- [ ] Implement ROE cross-check: computed ROE vs `companies.roe_percentage` and log anomalies (>5%) to `output/ratio_edge_cases.log`.
- [ ] Categorise each logged anomaly into: `data source issue`, `version difference`, `formula discrepancy`.
- [ ] Ensure Financials broad_sector (banks/NBFCs/insurance): suppress standard D/E high leverage warning flag.
- [ ] Run tests (`pytest -q`) and verify log file gets created.

