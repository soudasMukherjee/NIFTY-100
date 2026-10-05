from __future__ import annotations

import pandas as pd
import streamlit as st

from src.screener.engine import create_screener, ScreenerRequest

PRESET_BUTTON_LABELS = {
    "quality_compounder": "Quality",
    "value_pick": "Value",
    "growth_accelerator": "Growth",
    "dividend_champion": "Dividend",
    "debt_free_blue_chip": "Debt-Free",
    "turnaround_watch": "Turnaround",
}

FILTER_KEYS = [
    "roe_min",
    "de_max",
    "fcf_min",
    "revenue_cagr_5yr_min",
    "pat_cagr_5yr_min",
    "opm_min",
    "pe_max",
    "pb_max",
    "dividend_yield_min",
    "icr_min",
]

SLIDER_CONFIG = {
    "roe_min": {"label": "ROE min (%)", "min": 0.0, "max": 40.0, "step": 0.5},
    "de_max": {"label": "D/E max", "min": 0.0, "max": 5.0, "step": 0.05},
    "fcf_min": {"label": "FCF min (₹Cr)", "min": 0.0, "max": 1000.0, "step": 10.0},
    "revenue_cagr_5yr_min": {"label": "Revenue CAGR 5Y min (%)", "min": 0.0, "max": 40.0, "step": 0.5},
    "pat_cagr_5yr_min": {"label": "PAT CAGR 5Y min (%)", "min": 0.0, "max": 50.0, "step": 0.5},
    "opm_min": {"label": "OPM min (%)", "min": 0.0, "max": 50.0, "step": 0.5},
    "pe_max": {"label": "P/E max", "min": 0.0, "max": 100.0, "step": 1.0},
    "pb_max": {"label": "P/B max", "min": 0.0, "max": 20.0, "step": 0.1},
    "dividend_yield_min": {"label": "Dividend Yield min (%)", "min": 0.0, "max": 15.0, "step": 0.1},
    "icr_min": {"label": "ICR min", "min": 0.0, "max": 50.0, "step": 0.5},
}

DISPLAY_COLUMNS = [
    "company_id",
    "company_name",
    "broad_sector",
    "composite_quality_score",
    "return_on_equity_pct",
    "debt_to_equity",
    "free_cash_flow_cr",
    "revenue_cagr_5yr",
    "pat_cagr_5yr",
    "operating_profit_margin_pct",
    "pe_ratio",
    "pb_ratio",
    "dividend_yield_pct",
    "interest_coverage",
]

RENAME_COLUMNS = {
    "company_name": "Name",
    "broad_sector": "Sector",
    "composite_quality_score": "Composite Score",
    "return_on_equity_pct": "ROE (%)",
    "debt_to_equity": "D/E",
    "free_cash_flow_cr": "FCF (₹Cr)",
    "revenue_cagr_5yr": "Revenue CAGR 5Y (%)",
    "pat_cagr_5yr": "PAT CAGR 5Y (%)",
    "operating_profit_margin_pct": "OPM (%)",
    "pe_ratio": "P/E",
    "pb_ratio": "P/B",
    "dividend_yield_pct": "Dividend Yield (%)",
    "interest_coverage": "ICR",
}


def _get_default_filters(engine):
    return {
        metric_key: float(engine.metrics[metric_key].default_threshold)
        for metric_key in FILTER_KEYS
    }


def _prepare_results(results: pd.DataFrame, db) -> pd.DataFrame:
    companies = db.get_companies()[["company_id", "company_name"]]
    # The screener engine already returns broad_sector (LEFT JOIN sectors);
    # merge company name only so we don't create duplicate broad_sector columns.
    merged = results.merge(companies, on="company_id", how="left")
    merged = merged.reindex(columns=DISPLAY_COLUMNS).copy()
    merged = merged.rename(columns=RENAME_COLUMNS)
    merged["Composite Score"] = merged["Composite Score"].round(2)
    numeric_columns = [
        "ROE (%)", "D/E", "FCF (₹Cr)", "Revenue CAGR 5Y (%)",
        "PAT CAGR 5Y (%)", "OPM (%)", "P/E", "P/B",
        "Dividend Yield (%)", "ICR",
    ]
    for col in numeric_columns:
        if col in merged.columns:
            merged[col] = pd.to_numeric(merged[col], errors="coerce").round(2)
    return merged


def render(db):
    st.title("Screener")
    st.write("Use the sliders below to filter the latest company metrics.")
    st.sidebar.header("Screener filters")

    screener = create_screener()
    if "screener_filters" not in st.session_state:
        st.session_state["screener_filters"] = _get_default_filters(screener)

    with st.sidebar.expander("Presets", expanded=True):
        preset_cols = st.columns(3)
        for index, (preset_id, label) in enumerate(PRESET_BUTTON_LABELS.items()):
            if preset_cols[index % 3].button(label, key=f"preset_{preset_id}"):
                preset_values = screener.get_preset_filters(preset_id)
                for metric_key in FILTER_KEYS:
                    st.session_state["screener_filters"][metric_key] = float(
                        preset_values.get(metric_key, screener.metrics[metric_key].default_threshold)
                    )

    if st.sidebar.button("Reset filters"):
        st.session_state["screener_filters"] = _get_default_filters(screener)

    st.sidebar.markdown("---")
    for metric_key in FILTER_KEYS:
        config = SLIDER_CONFIG[metric_key]
        current_value = st.session_state["screener_filters"].get(metric_key, float(screener.metrics[metric_key].default_threshold))
        slider_value = st.sidebar.slider(
            config["label"],
            min_value=config["min"],
            max_value=config["max"],
            value=current_value,
            step=config["step"],
            key=f"slider_{metric_key}",
        )
        st.session_state["screener_filters"][metric_key] = float(slider_value)

    request = ScreenerRequest(filters=st.session_state["screener_filters"])
    results = screener.screen(request)
    screener.close()

    shown_results = _prepare_results(results, db)
    # Convert to a uniform string dtype so pyarrow/Arrow can serialize to
    # st.dataframe (fillna("N/A") alone creates mixed float+str object columns).
    display_results = shown_results.fillna("N/A").astype(str)
    matched = len(shown_results)
    st.markdown(f"**{matched} companies match your filters**")

    csv_bytes = shown_results.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download CSV",
        data=csv_bytes,
        file_name="screener_results.csv",
        mime="text/csv",
    )

    if matched == 0:
        st.info("No companies match the current filters. Adjust the sliders or choose a different preset.")
        return

    st.dataframe(display_results, use_container_width=True)
