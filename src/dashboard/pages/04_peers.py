from __future__ import annotations

import plotly.graph_objects as go
import pandas as pd
import streamlit as st

from src.analytics.radar_charts import METRICS, normalize_to_0_100

RADAR_LABELS = [metric[0] for metric in METRICS]

KPI_COLUMNS = [
    "company_id",
    "company_name",
    "broad_sector",
    "is_benchmark",
    "return_on_equity_pct",
    "roce_pct",
    "net_profit_margin_pct",
    "debt_to_equity",
    "free_cash_flow_cr",
    "revenue_cagr_5yr",
    "pat_cagr_5yr",
    "composite_quality_score",
    "pe_ratio",
    "pb_ratio",
]

RENAME_COLUMNS = {
    "company_id": "Company ID",
    "company_name": "Company",
    "broad_sector": "Sector",
    "is_benchmark": "Benchmark",
    "return_on_equity_pct": "ROE (%)",
    "roce_pct": "ROCE (%)",
    "net_profit_margin_pct": "NPM (%)",
    "debt_to_equity": "D/E",
    "free_cash_flow_cr": "FCF (₹Cr)",
    "revenue_cagr_5yr": "Revenue CAGR 5Y (%)",
    "pat_cagr_5yr": "PAT CAGR 5Y (%)",
    "composite_quality_score": "Composite Score",
    "pe_ratio": "P/E",
    "pb_ratio": "P/B",
}


def _to_arrow_safe(df: pd.DataFrame, keep_bool: str | None = None) -> pd.DataFrame:
    """Return a copy of the DataFrame with each column given a single uniform
    dtype so pyarrow/Arrow can serialize it to st.dataframe.

    The sheet spec requires missing values to show as 'N/A'.  Doing this with
    ``fillna("N/A")`` alone produces mixed object columns (float + str) that
    crash ``st.dataframe`` with `Could not convert 'N/A' with type str:
    tried to convert to double`.  Here we keep an optional boolean column as
    bool (needed by the benchmark-row styler) and cast every other column to
    a single string dtype.
    """
    result = df.copy()
    for col in result.columns:
        if keep_bool is not None and col == keep_bool:
            continue
        # Ensure the column actually contains only str after fillna; this
        # turns e.g. float columns that still contain NaN into float then
        # converts them to str uniformly.
        result[col] = result[col].astype(str)
    return result


def _build_company_label(row: pd.Series) -> str:
    return f"{row['company_id']} — {row['company_name']}"


def _safe_metrics(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    for _, col, _ in METRICS:
        if col in result.columns:
            result[col] = pd.to_numeric(result[col], errors="coerce")
    result["roce_pct"] = pd.to_numeric(result.get("roce_pct"), errors="coerce")
    return result


def _build_radar_chart(company_values: list[float], peer_values: list[float], company_label: str, group_name: str) -> go.Figure:
    closed_labels = RADAR_LABELS + [RADAR_LABELS[0]]
    company_closed = company_values + [company_values[0]]
    peer_closed = peer_values + [peer_values[0]]

    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(
            r=company_closed,
            theta=closed_labels,
            fill="toself",
            name=company_label,
            line=dict(color="#1f77b4"),
            marker=dict(size=6),
        )
    )
    fig.add_trace(
        go.Scatterpolar(
            r=peer_closed,
            theta=closed_labels,
            fill="none",
            name=f"{group_name} average",
            line=dict(color="#d62728", dash="dash"),
            marker=dict(size=6),
        )
    )
    fig.update_layout(
        polar=dict(
            radialaxis=dict(range=[0, 100], tickvals=[0, 25, 50, 75, 100], ticktext=["0", "25", "50", "75", "100"], showgrid=True),
            angularaxis=dict(rotation=90, direction="clockwise"),
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.1, xanchor="center", x=0.5),
        margin=dict(l=30, r=30, t=45, b=30),
        template="plotly_white",
        title={"text": f"{company_label} vs {group_name} average", "x":0.5},
    )
    return fig


def render(db):
    st.title("Peers")
    st.write("Compare a selected company to its peer group with a radar chart and KPI table.")

    peer_groups = db.get_peer_groups()["peer_group_name"].tolist()
    group = st.selectbox("Select peer group", peer_groups)
    if not group:
        return

    peers = db.get_peers(group)
    if peers.empty:
        st.warning("No peers found for this group.")
        return

    peers = _safe_metrics(peers)
    peers = peers.assign(company_label=peers.apply(_build_company_label, axis=1))

    # Ensure is_benchmark is a proper bool column (SQLite returns 0/1 as integers).
    peers["is_benchmark"] = peers["is_benchmark"].astype(bool)

    benchmark_rows = peers[peers["is_benchmark"]]
    default_index = 0
    if not benchmark_rows.empty:
        benchmark_id = benchmark_rows.iloc[0]["company_id"]
        default_index = peers.index[peers["company_id"] == benchmark_id].tolist()[0]

    selected_label = st.selectbox("Select company", peers["company_label"].tolist(), index=default_index)
    selected_company_id = selected_label.split(" — ")[0]
    selected_company = peers[peers["company_id"] == selected_company_id].iloc[0]

    norm_peers = normalize_to_0_100(peers, METRICS)
    metric_cols = [metric[1] for metric in METRICS]
    norm_cols = [f"{col}_norm" for col in metric_cols]

    company_norm = norm_peers[norm_peers["company_id"] == selected_company_id].iloc[0]
    peer_avg = norm_peers[norm_peers["peer_group_name"] == group] if "peer_group_name" in norm_peers.columns else norm_peers
    peer_avg_values = []
    for col in norm_cols:
        avg_value = peer_avg[col].mean(skipna=True)
        peer_avg_values.append(0.0 if pd.isna(avg_value) else float(avg_value))
    company_values = [float(company_norm[col]) if pd.notna(company_norm[col]) else 0.0 for col in norm_cols]

    chart = _build_radar_chart(company_values, peer_avg_values, selected_label, group)

    col1, col2 = st.columns([2, 3], gap="large")
    with col1:
        st.plotly_chart(chart, use_container_width=True)
    with col2:
        st.subheader("Selected company KPIs")
        selected_kpis = selected_company.reindex(KPI_COLUMNS).rename(RENAME_COLUMNS)
        selected_kpis = selected_kpis.to_frame().T
        if "Composite Score" in selected_kpis.columns:
            selected_kpis["Composite Score"] = selected_kpis["Composite Score"].round(2)
        # Convert to uniform str types so pyarrow/Arrow can serialize the frame
        # (fillna("N/A") alone creates mixed object columns that crash st.dataframe).
        st.dataframe(_to_arrow_safe(selected_kpis.fillna("N/A")), use_container_width=True)

    st.markdown("---")
    st.subheader(f"Peer group KPI table — {group}")
    display_table = peers.reindex(columns=KPI_COLUMNS).rename(columns=RENAME_COLUMNS)
    if "Composite Score" in display_table.columns:
        display_table["Composite Score"] = display_table["Composite Score"].round(2)
    display_table = display_table.fillna("N/A")
    # Keep the Benchmark column boolean (used by the style function) and convert
    # the remaining columns to a single str dtype for Arrow-safe serialization.
    display_table = _to_arrow_safe(display_table, keep_bool="Benchmark")

    def _highlight_benchmark(row: pd.Series) -> list[str]:
        color = "background-color: #fff4cc" if row["Benchmark"] else ""
        return [color] * len(row)

    styled = display_table.style.apply(_highlight_benchmark, axis=1)
    st.dataframe(styled, use_container_width=True)
    st.caption("Benchmark company row is highlighted.")
