"""Day 27 QA — verify all 92 tickers load on Profile page + screener extremes."""
from __future__ import annotations

import sys
import time
import traceback
from pathlib import Path

ROOT = Path("c:/nifty100_sprint1")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from _dashboard_smoke import load_page, UI, patch_streamlit, restore_streamlit  # noqa: E402


def main():
    from src.dashboard.utils import db

    companies = db.get_companies()
    tickers = companies["company_id"].tolist()
    print(f"Companies in DB: {len(tickers)}")

    originals = patch_streamlit()
    failures = 0
    load_times = []

    try:
        # ---- Profile page for ALL tickers ----
        profile = load_page("02_profile")
        print("\n== Profile page: all tickers ==")
        for idx, ticker in enumerate(tickers, 1):
            import streamlit as st
            st.text_input = lambda label, **k: ticker
            ui_rx = UI()
            st.selectbox = ui_rx.selectbox
            start = time.time()
            try:
                profile.render(db)
                elapsed = time.time() - start
                load_times.append(elapsed)
                if idx % 20 == 0 or idx == len(tickers):
                    print(f"  ...{idx}/{len(tickers)} ok (latest {elapsed:.2f}s)")
            except Exception:
                failures += 1
                print(f"  [FAIL] profile ticker={ticker}")
                traceback.print_exc()

        # ---- Trends page for all tickers ----
        trends = load_page("05_trends")
        print("\n== Trends page: all tickers ==")
        for idx, ticker in enumerate(tickers, 1):
            import streamlit as st
            st.text_input = lambda label, **k: ticker
            ui_rx = UI()
            st.selectbox = ui_rx.selectbox
            try:
                trends.render(db)
                if idx % 20 == 0 or idx == len(tickers):
                    print(f"  ...{idx}/{len(tickers)} ok")
            except Exception:
                failures += 1
                print(f"  [FAIL] trends ticker={ticker}")
                traceback.print_exc()

        # ---- Screener with extreme slider values ----
        screener = load_page("03_screener")
        print("\n== Screener: extreme filters ==")
        try:
            import streamlit as st
            # All min values (most permissive) -> expect many results, no crash
            st.session_state["screener_filters"] = {
                "roe_min": 0.0, "de_max": 5.0, "fcf_min": 0.0,
                "revenue_cagr_5yr_min": 0.0, "pat_cagr_5yr_min": 0.0, "opm_min": 0.0,
                "pe_max": 100.0, "pb_max": 20.0, "dividend_yield_min": 0.0, "icr_min": 0.0,
            }
            st.slider = lambda label, **k: {"ROE min (%)": 0.0, "D/E max": 5.0}.get(label, k.get("value", 0.0))
            st.button = lambda label, **k: False
            screener.render(db)
            print("  [OK] screener all-min filters")
        except Exception:
            failures += 1
            print("  [FAIL] screener all-min filters")
            traceback.print_exc()

        try:
            import streamlit as st
            # All max-strict values (most restrictive) -> expect 0 or few results, no crash
            st.session_state["screener_filters"] = {
                "roe_min": 40.0, "de_max": 0.0, "fcf_min": 1000.0,
                "revenue_cagr_5yr_min": 40.0, "pat_cagr_5yr_min": 50.0, "opm_min": 50.0,
                "pe_max": 0.0, "pb_max": 0.0, "dividend_yield_min": 15.0, "icr_min": 50.0,
            }
            st.slider = lambda label, **k: {"ROE min (%)": 40.0, "D/E max": 0.0}.get(label, k.get("value", 0.0))
            st.button = lambda label, **k: False
            screener.render(db)
            print("  [OK] screener all-max-strict filters")
        except Exception:
            failures += 1
            print("  [FAIL] screener all-max-strict filters")
            traceback.print_exc()
    finally:
        restore_streamlit(originals)

    print("\n" + "=" * 60)
    print(f"Ticker profile render times: min={min(load_times):.2f}s "
          f"max={max(load_times):.2f}s avg={sum(load_times)/len(load_times):.2f}s (n={len(load_times)})")
    print(f"Result: {'ALL PASSED' if failures == 0 else f'{failures} FAILURES'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

