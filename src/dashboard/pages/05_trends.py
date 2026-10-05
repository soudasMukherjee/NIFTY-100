from __future__ import annotations

import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

METRIC_CHOICES = {
    "roe_pct": ("ROE (%)", "return_on_equity_pct"),
    "npm_pct": ("Net Margin (%)", "net_profit_margin_pct"),
    "opm_pct": ("Operating Margin (%)", "operating_profit_margin_pct"),
    "fcf_cr": ("FCF (₹ Cr)", "free_cash_flow_cr"),
    "de_ratio": ("D/E", "debt_to_equity"),
    "interest_cov": ("Interest Coverage", "interest_coverage"),
}


def _coerce_year(value: object) -> int | None:
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    digits = re.findall(r"\d{4}", text)
    if digits:
        return int(digits[-1])
    return None


def _search_options(companies: pd.DataFrame, query: str) -> list[str]:
    values = (
        companies["company_id"].fillna("") + " - " + companies["company_name"].fillna("")
    ).tolist()
    if not query:
        return values[:50]
    query = query.strip().upper()
    return [value for value in values if query in value.upper()][:50]


def _calculate_yoy_pct(values: pd.Series) -> pd.Series:
    result = pd.Series([None] * len(values), index=values.index, dtype="float64")
    for index in range(1, len(values)):
        previous = values.iloc[index - 1]
        current = values.iloc[index]
        if pd.isna(previous) or pd.isna(current) or previous in (0, 0.0):
            continue
        result.iloc[index] = ((current - previous) / previous) * 100.0
    return result


def _prepare_trends_frame(ratios: pd.DataFrame) -> pd.DataFrame:
    if ratios.empty:
        return pd.DataFrame(columns=["year", "metric", "value"])
    frame = ratios.copy()
    metric_columns = [column for _, column in METRIC_CHOICES.values()]
    columns = ["year"] + [col for col in metric_columns if col in frame.columns]
    frame = frame.loc[:, columns]
    if metric_columns:
        frame = frame.dropna(how="all", subset=[col for col in metric_columns if col in frame.columns])
    frame["year"] = frame["year"].apply(_coerce_year)
    frame = frame.dropna(subset=["year"]).sort_values("year")
    frame = frame.tail(10)
    return frame


def render(db):
    st.title("Trends")
    st.write("Compare a company’s recent operating history across multiple metrics.")

    companies = db.get_companies()
    query = st.text_input("Search by ticker or company name")
    matches = _search_options(companies, query)
    if not matches:
        st.warning("Ticker not found — please try another")
        return

    selection = st.selectbox("Select company", matches)
    ticker = selection.split(" - ", 1)[0]
    ratios = db.get_ratios(ticker)
    if ratios.empty:
        st.info("No ratio history is available for this company yet.")
        return

    prepared = _prepare_trends_frame(ratios)
    if prepared.empty:
        st.info("Insufficient ratio history is available for this company.")
        return

    available_metrics = [
        metric_key
        for metric_key, (_, column) in METRIC_CHOICES.items()
        if column in prepared.columns
    ]
    if not available_metrics:
        st.info("No reported metrics are available for this company.")
        return

    default_metrics = [metric for metric in ["roe_pct"] if metric in available_metrics]
    selected_metrics = st.multiselect(
        "Overlay up to 3 metrics",
        options=available_metrics,
        default=default_metrics or [available_metrics[0]],
        max_selections=3,
    )
    if not selected_metrics:
        st.info("Choose at least one metric to plot.")
        return

    fig = go.Figure()
    for metric_key in selected_metrics:
        _, column = METRIC_CHOICES[metric_key]
        values = pd.to_numeric(prepared[column], errors="coerce")
        yoy = _calculate_yoy_pct(values)
        metric_label = dict(METRIC_CHOICES)[metric_key][0]
        fig.add_trace(
            go.Scatter(
                x=prepared["year"],
                y=values,
                mode="lines+markers",
                name=metric_label,
                line=dict(width=2),
            )
        )
        for x_value, y_value, yoy_value in zip(prepared["year"], values, yoy):
            if pd.notna(y_value) and pd.notna(yoy_value):
                fig.add_annotation(
                    x=x_value,
                    y=y_value,
                    text=f"{yoy_value:+.1f}%",
                    showarrow=False,
                    yshift=10,
                    xshift=0,
                    font=dict(size=10),
                )

    fig.update_layout(
        title=f"{ticker} — last 10 annual data points",
        xaxis_title="Year",
        yaxis_title="Metric value",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.08, xanchor="center", x=0.5),
        margin=dict(l=20, r=20, t=60, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)
