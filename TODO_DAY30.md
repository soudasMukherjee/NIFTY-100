# Day 30 — NLP · Auto Pros/Cons Generator

## Sprint 5 · Epics 07, 08 & 09 — Cash Flow Intelligence + Reports + NLP

### Goal (Day 30)
Implement an automated pros/cons generator with 12 pro rules and 12 con rules
(con rules implemented as mirror-opposites of the pro rules), driven by data in
`nifty100.db`, writing a long-format CSV to `output/pros_cons_generated.csv`.

### Pro Rules (12)
1. ROE > 20% sustained for 3+ years
2. FCF positive for 5+ consecutive years
3. D/E = 0 in latest year (debt-free)
4. Revenue CAGR > 15% over 5 years
5. OPM > 25% in latest year
6. PAT CAGR > 20% over 5 years
7. ICR > 10 or debt-free
8. Dividend Yield > 2% with FCF positive
9. EPS CAGR > 15% over 5 years
10. ROE improving for 3 consecutive years
11. Revenue CAGR > PAT CAGR (operating leverage)
12. Balance-sheet assets growing with declining debt

### Con Rules (12 — mirror opposites)
1. ROE < 10% → weak capital efficiency
2. FCF negative → constrained cash generation
3. D/E > 1.5 → high leverage / elevated interest burden
4. Revenue CAGR < 5% → weak top-line momentum
5. OPM < 10% → weak pricing power / margin pressure
6. PAT CAGR < 5% → weak profit compounding
7. ICR < 2 and not debt-free → financial stress from debt servicing
8. Dividend Yield < 1% → low income returns
9. EPS CAGR < 5% → weak earnings growth
10. ROE declining for 3 consecutive years → weakening business quality
11. Revenue CAGR > PAT CAGR (margin dilution) → falling profitability
12. Assets growing with rising debt → debt-funded expansion

### Steps
- [x] Create TODO_DAY30.md (this file)
- [x] Step 1: Create `src/nlp/pros_cons_generator.py`
  - [x] 12 pro-rule predicates + texts
  - [x] 12 con-rule predicates + texts
  - [x] `load_company_data()` — latest ratios + historical sequences + dividend yield
  - [x] `evaluate_company()` — evaluate one company
  - [x] `generate_pros_cons()` — build `output/pros_cons_generated.csv`
  - [x] `run_generator()` — summary dict + `__main__` CLI
- [x] Step 2: Update `src/nlp/__init__.py` docstring
- [x] Step 3: Create `tests/nlp/test_pros_cons_generator.py`
- [x] Step 4: Run generator CLI + verify output CSV
- [x] Step 5: Run pytest for NLP tests + full suite

## Day 30 — Verification Summary

| Check | Result |
|-------|--------|
| `src/nlp/pros_cons_generator.py` | 12 pro rules + 12 con rules (24 total) ✅ |
| `output/pros_cons_generated.csv` | 614 rows (90 companies: 413 pros, 201 cons), schema: company_id, type, rule_id, text ✅ |
| `output/pros_cons_summary.csv` | 90 companies, per-company pros_count/cons_count/total_count ✅ |
| NLP unit tests | **58 passed** (19 Day 29 + 39 Day 30) ✅ |
| Generator CLI | runs via `python -m src.nlp.pros_cons_generator` ✅ |
