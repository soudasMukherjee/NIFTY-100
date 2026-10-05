from __future__ import annotations

import plotly.express as px
import pandas as pd
import streamlit as st


def _format_value(value: float | None, suffix: str = "") -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:.1f}{suffix}"


def render(db):
    st.title("Home")
    st.markdown("### Nifty 100 Analytics")

    year = st.sidebar.selectbox("Select year", list(range(2019, 2025)), index=5)
    companies = db.get_companies()
    ratios = db.get_financial_ratios_by_year(year)
    market_cap = db.get_market_cap_by_year(year)

    merged = ratios.merge(
        companies[["company_id", "company_name"]],
        on="company_id",
        how="left",
    )

    avg_roe = ratios["return_on_equity_pct"].dropna().mean() if not ratios.empty else None
    median_pe = market_cap["pe_ratio"].dropna().median() if not market_cap.empty else None
    median_de = ratios["debt_to_equity"].dropna().median() if not ratios.empty else None
    total_companies = len(companies)
    median_revenue_cagr = ratios["revenue_cagr_5yr"].dropna().median() if not ratios.empty else None
    debt_free_count = int((ratios["debt_to_equity"] == 0).sum()) if not ratios.empty else 0

    cols = st.columns(6)
    cols[0].metric("Average ROE", _format_value(avg_roe, "%"))
    cols[1].metric("Median P/E", _format_value(median_pe))
    cols[2].metric("Median D/E", _format_value(median_de))
    cols[3].metric("Total Companies", f"{total_companies}")
    cols[4].metric("Median Revenue CAGR 5yr", _format_value(median_revenue_cagr, "%"))
    cols[5].metric("Debt-Free Companies", f"{debt_free_count}")

    st.markdown("---")
    st.subheader("Sector breakdown")
    sectors = companies["broad_sector"].fillna("Unknown")
    sector_counts = sectors.value_counts().reset_index()
    sector_counts.columns = ["Sector", "Count"]
    fig = px.pie(
        sector_counts,
        names="Sector",
        values="Count",
        hole=0.45,
        title="Company count by sector",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Top 5 companies by composite quality score")
    if merged.empty:
        top5 = pd.DataFrame()
        st.info("No data available for the selected year.")
    else:
        top5 = merged.sort_values(
            "composite_quality_score",
            ascending=False,
            na_position="last",
        ).head(5)
    if top5.empty and not merged.empty:
        st.info("No data available for the selected year.")
    elif not top5.empty:
        display = top5[
            ["company_id", "company_name", "composite_quality_score",
             "return_on_equity_pct", "revenue_cagr_5yr", "free_cash_flow_cr"]
        ].copy()
        display["composite_quality_score"] = display["composite_quality_score"].round(1)
        display["return_on_equity_pct"] = display["return_on_equity_pct"].round(1)
        display["revenue_cagr_5yr"] = display["revenue_cagr_5yr"].round(1)
        display["free_cash_flow_cr"] = display["free_cash_flow_cr"].round(2)
        # Uniform string dtype keeps st.dataframe Arrow-serializable while
        # still displaying "N/A" for missing values.
        display = display.fillna("N/A").astype(str)
        st.dataframe(display.rename(columns={
            "company_id": "Ticker",
            "company_name": "Company",
            "composite_quality_score": "Quality Score",
            "return_on_equity_pct": "ROE (%)",
            "revenue_cagr_5yr": "Revenue CAGR 5yr (%)",
            "free_cash_flow_cr": "FCF (₹Cr)",
        }))
