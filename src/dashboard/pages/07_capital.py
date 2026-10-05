from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.analytics.capital_allocation import classify_capital_allocation_patterns


def _safe_float(value):
    if value is None:
        return 0.0
    try:
        result = float(value)
    except (TypeError, ValueError):
        return 0.0
    if pd.isna(result):
        return 0.0
    return result


def _build_treemap_data(frame: pd.DataFrame) -> tuple[list[str], list[str], list[int]]:
    if frame.empty:
        return ["All Companies"], [""], [0]

    labels = ["All Companies"]
    parents = [""]
    values: list[int] = [len(frame)]

    for pattern_label in sorted(frame["pattern_label"].dropna().astype(str).unique().tolist()):
        pattern_rows = frame[frame["pattern_label"] == pattern_label]
        labels.append(pattern_label)
        parents.append("All Companies")
        values.append(int(len(pattern_rows)))

        for _, row in pattern_rows.iterrows():
            labels.append(row["company_name"])
            parents.append(pattern_label)
            values.append(1)

    return labels, parents, values


def render(db):
    st.title("Capital Allocation Map")
    st.write("Explore how the latest cash flow patterns group the universe of companies.")

    companies = db.get_companies()[["company_id", "company_name"]]
    with db._connect() as conn:
        cashflow = pd.read_sql_query(
            "SELECT company_id, year, operating_activity, investing_activity, financing_activity FROM cashflow ORDER BY company_id, year",
            conn,
        )

    if cashflow.empty:
        st.info("No cash flow allocation data is available yet.")
        return

    rows: list[dict[str, object]] = []
    for company_id, company_name in companies.itertuples(index=False):
        company_cashflow = cashflow[cashflow["company_id"] == company_id]
        if company_cashflow.empty:
            continue
        latest_row = company_cashflow.iloc[-1]
        rows.append(
            {
                "company_id": company_id,
                "company_name": company_name,
                "year": latest_row["year"],
                "cfo": _safe_float(latest_row["operating_activity"]),
                "cfi": _safe_float(latest_row["investing_activity"]),
                "cff": _safe_float(latest_row["financing_activity"]),
            }
        )

    if not rows:
        st.info("No companies with cash flow data were found.")
        return

    allocation_frame = pd.DataFrame(rows)
    classified = pd.DataFrame(
        classify_capital_allocation_patterns(
            rows=[
                {
                    "company_id": row["company_id"],
                    "year": row["year"],
                    "cfo": row["cfo"],
                    "cfi": row["cfi"],
                    "cff": row["cff"],
                }
                for _, row in allocation_frame.iterrows()
            ]
        )
    )
    allocation_frame = allocation_frame.merge(classified, on=["company_id", "year"], how="left")

    labels, parents, values = _build_treemap_data(allocation_frame)
    fig = go.Figure(
        go.Treemap(
            labels=labels,
            parents=parents,
            values=values,
            branchvalues="total",
            textinfo="label+value",
            hovertemplate="<b>%{label}</b><br>%{value} companies<extra></extra>",
        )
    )
    fig.update_layout(template="plotly_white", margin=dict(t=30, l=10, r=10, b=10), autosize=True)
    st.plotly_chart(fig, use_container_width=True)

    pattern_labels = [label for label in labels if label not in {"All Companies"} and label in allocation_frame["pattern_label"].astype(str).unique().tolist()]
    if not pattern_labels:
        st.info("No allocation patterns are available yet.")
        return

    selected_pattern = st.selectbox("Select pattern", pattern_labels, index=0)

    if selected_pattern:
        companies_in_pattern = allocation_frame[allocation_frame["pattern_label"] == selected_pattern][["company_id", "company_name"]]
        st.subheader(f"Companies in {selected_pattern}")
        st.dataframe(companies_in_pattern, use_container_width=True)
