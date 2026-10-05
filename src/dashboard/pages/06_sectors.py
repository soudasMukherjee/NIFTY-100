from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st


def _coerce_year(value: object) -> int | None:
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    import re

    digits = re.findall(r"\d{4}", text)
    if digits:
        return int(digits[-1])
    return None


def _build_sector_snapshot(db) -> pd.DataFrame:
    companies = db.get_companies()[["company_id", "company_name", "broad_sector", "sub_sector"]]
    with db._connect() as conn:
        market_cap = pd.read_sql_query(
            "SELECT company_id, year, market_cap_crore FROM market_cap ORDER BY company_id, year",
            conn,
        )

    rows: list[dict[str, object]] = []
    for company_id, company_name, broad_sector, sub_sector in companies.itertuples(index=False):
        ratios = db.get_ratios(company_id)
        if ratios.empty:
            continue
        ratios = ratios.copy()
        ratios["year"] = ratios["year"].apply(_coerce_year)
        ratios = ratios.dropna(subset=["year"]).sort_values("year", ascending=False)
        latest_ratio = ratios.iloc[0] if not ratios.empty else None
        if latest_ratio is None:
            continue

        pl = db.get_pl(company_id)
        annual_pl = pl[(pl["period_type"] == "ANNUAL") & pl["year"].notna()].copy()
        if not annual_pl.empty:
            annual_pl["year"] = annual_pl["year"].apply(_coerce_year)
            annual_pl = annual_pl.dropna(subset=["year"]).sort_values("year")
            latest_pl = annual_pl.iloc[-1] if not annual_pl.empty else None
            revenue = latest_pl.get("sales") if latest_pl is not None else None
        else:
            revenue = None

        market = market_cap[market_cap["company_id"] == company_id]
        latest_market = market.iloc[-1] if not market.empty else None
        market_cap_value = latest_market["market_cap_crore"] if latest_market is not None else None

        rows.append(
            {
                "company_id": company_id,
                "company_name": company_name,
                "sector": broad_sector,
                "sub_sector": sub_sector,
                "revenue": revenue,
                "roe": latest_ratio.get("return_on_equity_pct"),
                "market_cap": market_cap_value,
            }
        )

    return pd.DataFrame(rows)


def render(db):
    st.title("Sectors")
    st.write("Explore company-level metrics by sector with a bubble chart and median KPI view.")

    snapshot = _build_sector_snapshot(db)
    if snapshot.empty:
        st.info("No sector snapshot data is available yet.")
        return

    sector_names = sorted(snapshot["sector"].dropna().unique().tolist())
    selected_sector = st.selectbox("Select sector", sector_names)
    sector_frame = snapshot[snapshot["sector"] == selected_sector].copy()
    sector_frame = sector_frame.dropna(subset=["revenue", "roe", "market_cap"])
    if sector_frame.empty:
        st.info("No companies with complete data are available for this sector.")
        return

    fig = px.scatter(
        sector_frame,
        x="revenue",
        y="roe",
        size="market_cap",
        color="sub_sector",
        hover_name="company_name",
        hover_data={
            "company_id": True,
            "sector": True,
            "sub_sector": True,
            "revenue": ":,.0f",
            "roe": ":.2f",
            "market_cap": ":,.0f",
        },
        size_max=50,
        labels={"revenue": "Revenue (₹ Cr)", "roe": "ROE (%)", "market_cap": "Market Cap (₹ Cr)"},
        title=f"{selected_sector} — bubble chart",
    )
    fig.update_traces(marker=dict(opacity=0.7))
    fig.update_layout(template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)

    median_metrics = {
        "Revenue (₹ Cr)": sector_frame["revenue"].median(),
        "ROE (%)": sector_frame["roe"].median(),
        "Market Cap (₹ Cr)": sector_frame["market_cap"].median(),
    }
    median_df = pd.DataFrame({"KPI": list(median_metrics.keys()), "Median": list(median_metrics.values())})
    chart = px.bar(
        median_df,
        x="KPI",
        y="Median",
        color="KPI",
        text_auto=".2s",
        title=f"{selected_sector} — median KPI values",
    )
    chart.update_layout(template="plotly_white", showlegend=False)
    st.plotly_chart(chart, use_container_width=True)
    st.markdown("---")
    # Uniform string dtype keeps st.dataframe Arrow-serializable while still
    # displaying "N/A" for missing median values.
    median_df = median_df.fillna("N/A").astype(str)
    st.dataframe(median_df, use_container_width=True)
