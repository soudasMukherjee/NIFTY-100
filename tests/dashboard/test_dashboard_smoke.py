from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_ROOT = ROOT / "src" / "dashboard"


def _load_page_module(module_name: str, page_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, page_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load {page_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _build_fake_db():
    companies = pd.DataFrame(
        [
            {"company_id": "ABC", "company_name": "ABC Ltd", "broad_sector": "Financials", "sub_sector": "Banks"},
            {"company_id": "XYZ", "company_name": "XYZ Ltd", "broad_sector": "Financials", "sub_sector": "Banks"},
        ]
    )
    ratios = pd.DataFrame(
        [
            {"company_id": "ABC", "year": 2023, "return_on_equity_pct": 18.5},
            {"company_id": "XYZ", "year": 2023, "return_on_equity_pct": 14.2},
        ]
    )
    pl = pd.DataFrame(
        [
            {"company_id": "ABC", "year": 2023, "period_type": "ANNUAL", "sales": 1000.0},
            {"company_id": "XYZ", "year": 2023, "period_type": "ANNUAL", "sales": 800.0},
        ]
    )

    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE market_cap(company_id TEXT, year INTEGER, market_cap_crore REAL)")
    conn.execute("CREATE TABLE cashflow(company_id TEXT, year INTEGER, operating_activity REAL, investing_activity REAL, financing_activity REAL)")
    conn.executemany(
        "INSERT INTO market_cap VALUES (?, ?, ?)",
        [("ABC", 2023, 2500.0), ("XYZ", 2023, 1800.0)],
    )
    conn.executemany(
        "INSERT INTO cashflow VALUES (?, ?, ?, ?, ?)",
        [("ABC", 2023, 300.0, -120.0, -50.0), ("XYZ", 2023, 220.0, -80.0, -30.0)],
    )
    conn.commit()

    class FakeDB:
        def get_companies(self):
            return companies

        def get_ratios(self, company_id):
            return ratios[ratios["company_id"] == company_id].copy()

        def get_pl(self, company_id):
            return pl[pl["company_id"] == company_id].copy()

        def _connect(self):
            return conn

    return FakeDB()


def _patch_streamlit(monkeypatch, module):
    def fake_title(*args, **kwargs):
        return None

    def fake_write(*args, **kwargs):
        return None

    def fake_info(*args, **kwargs):
        return None

    def fake_selectbox(label, options, *args, **kwargs):
        return options[0] if options else None

    def fake_plotly_chart(*args, **kwargs):
        return None

    def fake_subheader(*args, **kwargs):
        return None

    def fake_dataframe(*args, **kwargs):
        return None

    monkeypatch.setattr(module.st, "title", fake_title)
    monkeypatch.setattr(module.st, "write", fake_write)
    monkeypatch.setattr(module.st, "info", fake_info)
    monkeypatch.setattr(module.st, "selectbox", fake_selectbox)
    monkeypatch.setattr(module.st, "plotly_chart", fake_plotly_chart)
    monkeypatch.setattr(module.st, "subheader", fake_subheader)
    monkeypatch.setattr(module.st, "dataframe", fake_dataframe)


def test_sector_page_renders_with_sample_data(monkeypatch):
    module = _load_page_module("test_sectors_page", DASHBOARD_ROOT / "pages" / "06_sectors.py")
    _patch_streamlit(monkeypatch, module)

    module.render(_build_fake_db())


def test_capital_page_renders_with_sample_data(monkeypatch):
    module = _load_page_module("test_capital_page", DASHBOARD_ROOT / "pages" / "07_capital.py")
    _patch_streamlit(monkeypatch, module)

    module.render(_build_fake_db())
