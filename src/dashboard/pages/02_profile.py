from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import streamlit as st


def _search_options(companies: pd.DataFrame, query: str) -> list[str]:
    values = (
        companies["company_id"].fillna("") + " - " + companies["company_name"].fillna("")
    ).tolist()
    if not query:
        return values[:50]
    query = query.strip().upper()
    return [value for value in values if query in value.upper()][:50]


def _format_metric(value: float | None, suffix: str = "") -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:.1f}{suffix}"


def _render_badges(label: str, items: list[str], emoji: str, container) -> None:
    if not items:
        container.write("_No items available._")
        return
    container.markdown(f"**{label}**")
    for item in items:
        container.markdown(f"{emoji} {item}")


def render(db):
    st.title("Company Profile")

    companies = db.get_companies()
    query = st.text_input("Search by ticker or company name")
    matches = _search_options(companies, query)

    if not matches:
        st.warning("Ticker not found — please try another")
        return

    selection = st.selectbox("Select company", matches)
    ticker = selection.split(" - ", 1)[0]
    if not ticker:
        st.warning("Ticker not found — please try another")
        return

    company = companies[companies["company_id"] == ticker]
    if company.empty:
        st.warning("Ticker not found — please try another")
        return

    company_row = company.iloc[0]
    st.subheader(f"{company_row['company_name']} ({ticker})")
    broad_sector = company_row.get('broad_sector') or 'Unknown'
    sub_sector = company_row.get('sub_sector') or 'Unknown'
    st.write(
        f"**Sector:** {broad_sector}  \
         **Sub-sector:** {sub_sector}"
    )
    st.write(f"**NSE ticker:** {ticker}")
    about_text = company_row.get("about_company")
    st.write(about_text if about_text and not pd.isna(about_text) else "No description available.")

    ratios = db.get_ratios(ticker)
    latest_ratio = ratios.head(1)
    latest_ratio_row = latest_ratio.iloc[0] if not latest_ratio.empty else None

    def _latest_value(key: str):
        if latest_ratio_row is None:
            return None
        return latest_ratio_row.get(key)

    st.markdown("---")
    kpis = st.columns(6)
    kpis[0].metric("ROE", _format_metric(_latest_value("return_on_equity_pct"), "%"))
    kpis[1].metric("ROCE", _format_metric(company_row.get("roce_percentage"), "%"))
    kpis[2].metric("Net Profit Margin", _format_metric(_latest_value("net_profit_margin_pct"), "%"))
    kpis[3].metric("D/E", _format_metric(_latest_value("debt_to_equity")))
    kpis[4].metric("Revenue CAGR 5yr", _format_metric(_latest_value("revenue_cagr_5yr"), "%"))
    kpis[5].metric("FCF", _format_metric(_latest_value("free_cash_flow_cr")))

    if latest_ratio.empty:
        st.info("No financial ratio data available for this company yet.")
        st.markdown("---")
        proscons = db.get_prosandcons(ticker)
        pros = []
        cons = []
        if not proscons.empty:
            row = proscons.iloc[0]
            pros_text = row.get("pros") if row.get("pros") is not None else ""
            cons_text = row.get("cons") if row.get("cons") is not None else ""
            pros = [item.strip() for item in str(pros_text).splitlines() if item.strip()]
            cons = [item.strip() for item in str(cons_text).splitlines() if item.strip()]
        st.subheader("Pros and Cons")
        pcol, ccol = st.columns(2)
        _render_badges("Pros", pros, ":white_check_mark:", pcol)
        _render_badges("Cons", cons, ":x:", ccol)
        return

    pl = db.get_pl(ticker)
    annual_pl = pl[pl["period_type"] == "ANNUAL"].dropna(subset=["year"])
    annual_pl = annual_pl.sort_values("year", ascending=True).head(10)
    st.markdown("---")
    st.subheader("Revenue & Net Profit (Last 10 years)")
    if annual_pl.empty:
        st.info("No annual profit and loss data available.")
    else:
        fig = px.bar(
            annual_pl,
            x="year",
            y=["sales", "net_profit"],
            labels={"value": "₹ Crore", "variable": "Metric", "year": "Year"},
            title="Revenue and Net Profit",
            barmode="group",
        )
        st.plotly_chart(fig, use_container_width=True)

    history = db.get_returns_history(ticker)
    st.subheader("ROE and ROCE (Last 10 years)")
    if history.empty:
        st.info("No historical ROE/ROCE data available.")
    else:
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=history["year"],
                y=history["roe_pct"],
                name="ROE",
                mode="lines+markers",
                line=dict(color="#1f77b4"),
            )
        )
        fig.add_trace(
            go.Scatter(
                x=history["year"],
                y=history["roce_pct"],
                name="ROCE",
                mode="lines+markers",
                line=dict(color="#ff7f0e"),
                yaxis="y2",
            )
        )
        fig.update_layout(
            xaxis_title="Year",
            yaxis_title="ROE (%)",
            yaxis2=dict(
                title="ROCE (%)",
                overlaying="y",
                side="right",
            ),
            legend_title="Metric",
        )
        st.plotly_chart(fig, use_container_width=True)

    proscons = db.get_prosandcons(ticker)
    pros = []
    cons = []
    if not proscons.empty:
        row = proscons.iloc[0]
        pros_text = row.get("pros") if row.get("pros") is not None else ""
        cons_text = row.get("cons") if row.get("cons") is not None else ""
        pros = [item.strip() for item in str(pros_text).splitlines() if item.strip()]
        cons = [item.strip() for item in str(cons_text).splitlines() if item.strip()]

    st.markdown("---")
    st.subheader("Pros and Cons")
    pcol, ccol = st.columns(2)
    _render_badges("Pros", pros, ":white_check_mark:", pcol)
    _render_badges("Cons", cons, ":x:", ccol)
