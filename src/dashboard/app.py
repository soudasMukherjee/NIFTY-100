from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.dashboard.utils import db

PAGES_DIR = Path(__file__).resolve().parent / "pages"
# (file_name, icon, label)
PAGE_FILES = [
    ("01_home.py", "🏠", "Home"),
    ("02_profile.py", "🏢", "Company Profile"),
    ("03_screener.py", "🔍", "Screener"),
    ("04_peers.py", "🤝", "Peers"),
    ("05_trends.py", "📈", "Trends"),
    ("06_sectors.py", "🏭", "Sectors"),
    ("07_capital.py", "💰", "Capital"),
    ("08_reports.py", "📄", "Reports"),
]


def load_page_module(page_file: Path):
    spec = importlib.util.spec_from_file_location(
        f"dashboard.pages.{page_file.stem}",
        page_file,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load page module from {page_file}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    st.set_page_config(
        page_title="Nifty 100 Analytics",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    with st.sidebar:
        st.markdown(
            """
            <style>
            .sidebar-brand {
                font-size: 1.35rem;
                font-weight: 700;
                letter-spacing: 0.5px;
                margin-bottom: 0.1rem;
            }
            .sidebar-sub {
                color: #8a8a8a;
                font-size: 0.8rem;
                margin-bottom: 1rem;
            }
            </style>
            <div class="sidebar-brand">📊 Nifty 100 Analytics</div>
            <div class="sidebar-sub">Sprint 4 dashboard scaffold</div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("#### Navigation")
        page_files = [file_name for file_name, _, _ in PAGE_FILES]
        page_labels = [f"{icon} {label}" for _, icon, label in PAGE_FILES]
        selected_label = st.radio(
            "Go to page",
            page_labels,
            label_visibility="collapsed",
            index=0,
        )

        selected_index = page_labels.index(selected_label)
        page_file_name = page_files[selected_index]
        selected_title = PAGE_FILES[selected_index][2]
        page_path = PAGES_DIR / page_file_name

        st.markdown("---")
        st.markdown(
            "Built on `streamlit` with shared SQLite data utilities."
        )

    try:
        page_module = load_page_module(page_path)
    except Exception as exc:
        st.error(f"Unable to load page '{selected_title}': {exc}")
        raise

    if hasattr(page_module, "render"):
        page_module.render(db)
    else:
        st.warning("This page is not yet implemented.")


if __name__ == "__main__":
    main()
