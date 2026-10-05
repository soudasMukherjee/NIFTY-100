from __future__ import annotations

from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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


def _is_valid_url(url: object) -> bool:
    """Return True only for a non-empty, http(s) URL that is not a null/NaN marker."""
    if url is None:
        return False
    if isinstance(url, float) and pd.isna(url):
        return False
    text = str(url).strip()
    if not text:
        return False
    # Some source rows store 'Null', 'nan', 'N/A', '-' etc. as the URL.
    if text.lower() in {"null", "nan", "n/a", "na", "-", "none"}:
        return False
    return text.lower().startswith(("http://", "https://"))


_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


@st.cache_data(ttl=3600)
def _check_report_url(url: str) -> tuple[bool, int | None]:
    if not _is_valid_url(url):
        return False, None
    # BSE blocks bare requests (HTTP 403); a browser-like User-Agent is needed.
    request = Request(url, method="HEAD", headers=_BROWSER_HEADERS)
    try:
        with urlopen(request, timeout=8) as response:
            return response.status < 400, response.status
    except HTTPError as exc:
        return False, exc.code
    except URLError:
        return False, None
    except ValueError:
        return False, None


def render(db):
    st.title("Annual Reports")
    st.write("Search for a company and review the availability of its annual report PDFs.")

    companies = db.get_companies()
    query = st.text_input("Search by ticker or company name")
    matches = _search_options(companies, query)
    if not matches:
        st.warning("Ticker not found — please try another")
        return

    selection = st.selectbox("Select company", matches)
    ticker = selection.split(" - ", 1)[0]

    with db._connect() as conn:
        documents = pd.read_sql_query(
            "SELECT year, annual_report_url FROM documents WHERE company_id = ? ORDER BY year DESC",
            conn,
            params=(ticker,),
        )

    if documents.empty:
        st.info("No annual report links are available for this company.")
        return

    st.subheader(f"Available annual report years — {ticker}")
    for _, row in documents.iterrows():
        year = int(row["year"]) if pd.notna(row["year"]) else "Unknown"
        url = row.get("annual_report_url")
        url_str = str(url) if url is not None and not (
            isinstance(url, float) and pd.isna(url)
        ) else ""
        is_available, _ = _check_report_url(url_str)
        col1, col2 = st.columns([1, 3])
        col1.write(str(year))
        if is_available and url_str:
            col2.markdown(f"[Open BSE PDF ({year})]({url_str})")
        else:
            col2.markdown(
                '<span style="background-color:#f8d7da;color:#721c24;padding:2px 8px;border-radius:4px;">Report unavailable</span>',
                unsafe_allow_html=True,
            )
