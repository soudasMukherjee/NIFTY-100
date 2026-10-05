from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_module(relative_path: str):
    module_path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_path.stem, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_trends_yoy_helper_marks_initial_value_as_missing():
    module = _load_module("src/dashboard/pages/05_trends.py")

    series = pd.Series([100.0, 120.0, 90.0])
    yoy = module._calculate_yoy_pct(series)

    assert pd.isna(yoy.iloc[0])
    assert yoy.iloc[1] == 20.0
    assert yoy.iloc[2] == -25.0


def test_capital_treemap_helper_groups_companies_by_pattern():
    capital_module = _load_module("src/dashboard/pages/07_capital.py")

    frame = pd.DataFrame(
        [
            {"company_id": "A", "company_name": "Alpha", "pattern_label": "Reinvestor"},
            {"company_id": "B", "company_name": "Beta", "pattern_label": "Reinvestor"},
            {"company_id": "C", "company_name": "Gamma", "pattern_label": "Cash Accumulator"},
        ]
    )

    labels, parents, values = capital_module._build_treemap_data(frame)

    assert labels[0] == "All Companies"
    assert "Reinvestor" in labels
    assert values[labels.index("Reinvestor")] == 2
