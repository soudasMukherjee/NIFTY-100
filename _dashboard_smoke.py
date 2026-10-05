"""Smoke-test all 8 dashboard pages against the real nifty100.db.

Patches the global streamlit module so page modules (which do
`import streamlit as st`) hit a fake UI layer. Uses representative tickers
including partial-data tickers ATGL and SBIN.
"""
from __future__ import annotations

import importlib.util
import sys
import traceback
from pathlib import Path

ROOT = Path("c:/nifty100_sprint1")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PAGES_DIR = ROOT / "src" / "dashboard" / "pages"


def load_page(name: str):
    spec = importlib.util.spec_from_file_location(f"smoke_{name}", PAGES_DIR / f"{name}.py")
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {name}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class UI:
    """Fake object used for both st.* and st.sidebar.* calls."""

    def __init__(self, session_state=None):
        self._session_state = session_state if session_state is not None else {}
        self.text_input_query = "TCS"
        self.id = 0  # streamlit cache internals read st.sidebar.id

    def __enter__(self):  # context manager for `with st.sidebar.expander(...)`
        return self

    def __exit__(self, *a):
        return False

    def title(self, *a, **k): return None
    def write(self, *a, **k): return None
    def markdown(self, *a, **k): return None
    def caption(self, *a, **k): return None
    def info(self, *a, **k): return None
    def warning(self, *a, **k): return None
    def error(self, *a, **k): return None
    def subheader(self, *a, **k): return None
    def dataframe(self, *a, **k): return None
    def plotly_chart(self, *a, **k): return None
    def metric(self, *a, **k): return None
    def download_button(self, *a, **k): return None
    def header(self, *a, **k): return None
    def set_page_config(self, *a, **k): return None
    def radio(self, *a, **k): return None

    def text_input(self, label, **k):
        return self.text_input_query

    def selectbox(self, label, options, **k):
        if options is None or len(options) == 0:
            raise ValueError(f"selectbox '{label}' got empty options")
        return options[0]

    def multiselect(self, label, options, **k):
        if not options:
            return []
        max_selections = k.get("max_selections") or 3
        return list(options[:min(max_selections, len(options))])

    def slider(self, label, **k):
        return k.get("value", 0.0)

    def button(self, label, **k):
        return False

    def expander(self, *a, **k):
        return self

    def columns(self, n, **k):
        class Cols(list):
            pass
        if isinstance(n, (list, tuple)):
            n = len(n)
        return Cols([UI(self._session_state) for _ in range(n)])

    def sidebar(self):  # pragma: no cover - attribute patched instead
        return self

    @property
    def session_state(self):
        return self._session_state


def patch_streamlit():
    import streamlit as st

    ui = UI()
    st_attrs = [
        "title", "write", "markdown", "caption", "info", "warning", "error",
        "subheader", "dataframe", "plotly_chart", "metric", "download_button",
        "header", "set_page_config", "text_input", "selectbox", "multiselect",
        "slider", "button", "expander", "columns",
    ]
    originals = {}
    for attr in st_attrs:
        originals[f"st.{attr}"] = getattr(st, attr)
        setattr(st, attr, getattr(ui, attr))
    originals["st.sidebar"] = st.sidebar
    st.sidebar = ui
    st.session_state = ui.session_state
    return originals


def restore_streamlit(originals):
    import streamlit as st

    for name, value in originals.items():
        attr = name.split(".")[1]
        setattr(st, attr, value)


def run_smoke():
    from src.dashboard.utils import db

    print("=" * 60)
    print("Dashboard page smoke test (real nifty100.db)")
    print("=" * 60)

    page_files = [
        "01_home", "02_profile", "03_screener", "04_peers",
        "05_trends", "06_sectors", "07_capital", "08_reports",
    ]
    failures = 0

    originals = patch_streamlit()

    try:
        for page in page_files:
            try:
                mod = load_page(page)
                if page == "08_reports":
                    # Avoid real network HEAD requests during smoke test.
                    mod._check_report_url = lambda url: (True, 200)
                mod.render(db)
                print(f"  [OK] {page}")
            except Exception:
                failures += 1
                print(f"  [FAIL] {page}")
                traceback.print_exc()

        # Ticker-specific runs for search-based pages (incl. partial data).
        for page in ["02_profile", "05_trends", "08_reports"]:
            for ticker in ["ATGL", "SBIN", "TCS", "HDFCBANK"]:
                try:
                    import streamlit as st
                    mod = load_page(page)
                    if page == "08_reports":
                        mod._check_report_url = lambda url: (True, 200)
                    st.text_input = lambda label, **k: ticker
                    ui_rx = UI()
                    st.selectbox = ui_rx.selectbox
                    st.multiselect = ui_rx.multiselect
                    mod.render(db)
                    print(f"  [OK] {page} (ticker={ticker})")
                except Exception:
                    failures += 1
                    print(f"  [FAIL] {page} (ticker={ticker})")
                    traceback.print_exc()
    finally:
        restore_streamlit(originals)

    print("=" * 60)
    print(f"Result: {'ALL PASSED' if failures == 0 else f'{failures} FAILURES'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run_smoke())

