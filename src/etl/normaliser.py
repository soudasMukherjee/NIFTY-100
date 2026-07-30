"""
Sprint 1 · Day 02 — Excel Loader & Normaliser
normalize_year()  : collapses messy period strings into a clean int fiscal year
normalize_ticker() : cleans/uppercases company ticker strings

Observed raw formats in the source workbooks (from actual data, not guessed):
    profitandloss / balancesheet : 'Dec 2012', 'Mar 2014', ..., 'TTM', 'Sep 2024'
    cashflow                     : 'Mar-13', 'Mar-14', ... AND 'Mar 2014' style rows
"""

from __future__ import annotations
import re

# Month-name and abbreviated formats we've actually seen in the data
_MONTH_YEAR_RE = re.compile(r"^([A-Za-z]{3,9})[\s\-]?(\d{2,4})$")

_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


class NormalisationError(ValueError):
    """Raised when a value cannot be safely normalised."""


def normalize_year(raw_period, *, current_year: int = 2026) -> tuple[int, str]:
    """
    Convert a raw period string into (fiscal_year:int, period_type:str).

    Handles:
      'Mar 2024'  -> (2024, 'ANNUAL')
      'Dec 2012'  -> (2012, 'ANNUAL')
      'Mar-13'    -> (2013, 'ANNUAL')     # 2-digit year, pivot at 50
      'Mar-99'    -> (1999, 'ANNUAL')
      'TTM'       -> (current_year, 'TTM')   # trailing twelve months -> tag, don't fabricate a year
      'Sep 2024'  -> (2024, 'ANNUAL')     # off-cycle FY-end still resolves to that year
      None / ''   -> raises NormalisationError

    Design decisions (documented for the DQ/validator layer):
      - We normalise on CALENDAR year of the statement date, not "FY24"
        accounting-convention labels, to keep the join key unambiguous.
      - 2-digit years pivot at 50: 00-49 -> 2000-2049, 50-99 -> 1950-1999.
      - 'TTM' rows are kept (not dropped) but flagged via period_type so
        downstream annual trend analysis can filter them out with
        WHERE period_type = 'ANNUAL'.
    """
    if raw_period is None:
        raise NormalisationError("year value is null")

    s = str(raw_period).strip()
    if not s:
        raise NormalisationError("year value is empty string")

    if s.upper() == "TTM":
        return current_year, "TTM"

    m = _MONTH_YEAR_RE.match(s)
    if not m:
        raise NormalisationError(f"unrecognised year format: {raw_period!r}")

    month_str, year_str = m.groups()
    month_key = month_str[:3].lower()
    if month_key not in _MONTH_MAP:
        raise NormalisationError(f"unrecognised month token in: {raw_period!r}")

    year_int = int(year_str)
    if year_int < 100:
        year_int = 2000 + year_int if year_int <= 49 else 1900 + year_int

    if not (1990 <= year_int <= current_year + 1):
        raise NormalisationError(f"year out of plausible range: {year_int} (from {raw_period!r})")

    return year_int, "ANNUAL"


def normalize_ticker(raw_ticker) -> str:
    """
    Clean a company ticker/company_id string.

    Handles:
      ' abb '     -> 'ABB'
      'Abb'       -> 'ABB'
      'ADANI ENT' -> 'ADANIENT'   (internal whitespace stripped — NSE tickers
                                    never contain spaces)
      None / ''   -> raises NormalisationError
    """
    if raw_ticker is None:
        raise NormalisationError("ticker is null")

    s = str(raw_ticker).strip().upper()
    s = re.sub(r"\s+", "", s)

    if not s:
        raise NormalisationError("ticker is empty after cleaning")

    if not re.match(r"^[A-Z0-9\-&]+$", s):
        raise NormalisationError(f"ticker contains unexpected characters: {raw_ticker!r}")

    return s


def parse_horizon_metric(raw_text):
    """
    Used for analysis.xlsx columns that embed both a horizon and a
    percentage in one string, e.g. '10 Years: 21%' or '5 Years          14%'.
    Returns (horizon_years:int|None, pct_value:float|None).
    Returns (None, None) if the text can't be parsed (kept, not dropped,
    so the row isn't silently lost — validator flags it as a WARNING).
    """
    if raw_text is None:
        return None, None
    s = str(raw_text).strip()
    if not s:
        return None, None

    horizon_m = re.search(r"(\d+)\s*Years?", s, re.IGNORECASE)
    pct_m = re.search(r"(-?\d+(?:\.\d+)?)\s*%", s)

    horizon = int(horizon_m.group(1)) if horizon_m else None
    pct = float(pct_m.group(1)) if pct_m else None
    return horizon, pct
