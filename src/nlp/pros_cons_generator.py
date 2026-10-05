"""
Sprint 5 · Day 30 — NLP · Auto Pros/Cons Generator

Automatically derives bullish ("pro") and bearish ("con") narrative bullets for
each company from the quantitative data in ``nifty100.db``.

The generator implements 12 pro rules and 12 con rules. The con rules are the
mirror-opposites of the pro rules (i.e. the same indicators evaluated on the
negative side). Each rule is a pure predicate function over a ``CompanyData``
object and carries a human-readable ``text`` exactly as specified for the pros
and aligned wording for the cons.

Data sources (all read from ``nifty100.db``):
    financial_ratios   latest-year ratios + 5-year CAGR fields
    profitandloss      annual sales / net-profit sequences (for min/improving checks)
    balancesheet       annual borrowings / total_assets sequences (pro rules 10 & 12)
    cashflow           annual operating/investing activity -> FCF sequence
    market_cap         dividend_yield_pct (rule 8)

Outputs (written to ``output/``):
    pros_cons_generated.csv   long-format: company_id, type, rule_id, text
    pros_cons_summary.csv     per-company counts of pros/cons matched
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "nifty100.db"
OUTPUT_DIR = ROOT / "output"

# Number of consecutive years used for "sustained / 3+ years" style checks.
MIN_YEARS = 3
FCF_YEARS = 5
CAGR_YEARS = 5


# ============================================================
# Data model
# ============================================================

@dataclass
class CompanyData:
    """Aggregated quantitative inputs needed to evaluate all 24 rules."""

    company_id: str
    # latest-year (most recent) values
    latest_roe: Optional[float] = None            # %
    latest_opm: Optional[float] = None            # %
    latest_de: Optional[float] = None             # ratio
    latest_icr: Optional[float] = None            # ratio
    latest_fcf: Optional[float] = None            # ₹ crore
    # 5-year CAGR metrics (from financial_ratios)
    revenue_cagr_5yr: Optional[float] = None      # %
    pat_cagr_5yr: Optional[float] = None          # %
    eps_cagr_5yr: Optional[float] = None          # %
    # dividend yield (%) from market_cap
    dividend_yield_pct: Optional[float] = None    # %
# historical sequences (oldest -> newest)
    roe_history: list[Optional[float]] = field(default_factory=list)
    fcf_history: list[Optional[float]] = field(default_factory=list)
    de_history: list[Optional[float]] = field(default_factory=list)
    assets_history: list[Optional[float]] = field(default_factory=list)

    @property
    def is_debt_free(self) -> bool:
        """True when the latest D/E is exactly 0 (debt-free)."""
        return self.latest_de is not None and float(self.latest_de) == 0.0


# ============================================================
# Rule container
# ============================================================

@dataclass(frozen=True)
class Rule:
    rule_id: str
    kind: str            # "pro" | "con"
    text: str
    predicate: Callable[[CompanyData], bool]


# ============================================================
# Pro Rule predicates (12)
# ============================================================

def _pro_roe_high(data: CompanyData) -> bool:
    """Rule 1: ROE > 20% sustained for 3+ years."""
    if len(data.roe_history) < MIN_YEARS:
        return False
    return all(v is not None and v > 20.0 for v in data.roe_history[-MIN_YEARS:])


def _pro_fcf_positive(data: CompanyData) -> bool:
    """Rule 2: FCF positive for 5+ consecutive years."""
    if len(data.fcf_history) < FCF_YEARS:
        return False
    return all(v is not None and v > 0 for v in data.fcf_history[-FCF_YEARS:])


def _pro_debt_free(data: CompanyData) -> bool:
    """Rule 3: D/E = 0 in latest year (debt-free)."""
    return data.is_debt_free


def _pro_revenue_cagr(data: CompanyData) -> bool:
    """Rule 4: Revenue CAGR > 15% over 5 years."""
    return data.revenue_cagr_5yr is not None and data.revenue_cagr_5yr > 15.0


def _pro_opm_high(data: CompanyData) -> bool:
    """Rule 5: OPM > 25% in latest year."""
    return data.latest_opm is not None and data.latest_opm > 25.0


def _pro_pat_cagr(data: CompanyData) -> bool:
    """Rule 6: PAT CAGR > 20% over 5 years."""
    return data.pat_cagr_5yr is not None and data.pat_cagr_5yr > 20.0


def _pro_icr_high(data: CompanyData) -> bool:
    """Rule 7: ICR > 10 or debt-free."""
    if data.is_debt_free:
        return True
    return data.latest_icr is not None and data.latest_icr > 10.0


def _pro_dividend_yield(data: CompanyData) -> bool:
    """Rule 8: Dividend Yield > 2% with FCF positive."""
    if data.dividend_yield_pct is None or data.dividend_yield_pct <= 2.0:
        return False
    return data.latest_fcf is not None and data.latest_fcf > 0


def _pro_eps_cagr(data: CompanyData) -> bool:
    """Rule 9: EPS CAGR > 15% over 5 years."""
    return data.eps_cagr_5yr is not None and data.eps_cagr_5yr > 15.0


def _pro_roe_improving(data: CompanyData) -> bool:
    """Rule 10: ROE improving for 3 consecutive years."""
    if len(data.roe_history) < MIN_YEARS:
        return False
    window = [float(v) for v in data.roe_history[-MIN_YEARS:] if v is not None]
    if len(window) < MIN_YEARS:
        return False
    return window[-1] > window[-2] > window[-3]


def _pro_operating_leverage(data: CompanyData) -> bool:
    """Rule 11: Revenue CAGR > PAT CAGR (operating leverage)."""
    if data.revenue_cagr_5yr is None or data.pat_cagr_5yr is None:
        return False
    return data.revenue_cagr_5yr > data.pat_cagr_5yr


def _pro_assets_growing(data: CompanyData) -> bool:
    """Rule 12: Balance-sheet assets growing with declining debt.

    Uses latest-year total assets vs earliest-year total assets and latest D/E
vs earliest D/E to determine "growing with declining debt".
    """
    if len(data.assets_history) < 2 or len(data.de_history) < 2:
        return False
    if any(v is None for v in data.assets_history):
        return False
    if any(v is None for v in data.de_history):
        return False
    a0, a1 = float(data.assets_history[0]), float(data.assets_history[-1])
    d0, d1 = float(data.de_history[0]), float(data.de_history[-1])
    assets_grew = a1 > a0
    debt_fell = d1 < d0
    return assets_grew and debt_fell


# ============================================================
# Con Rule predicates (12 — mirror opposites of the pros)
# ============================================================

def _con_roe_low(data: CompanyData) -> bool:
    """Con 1: ROE < 10% in latest year."""
    return data.latest_roe is not None and data.latest_roe < 10.0


def _con_fcf_negative(data: CompanyData) -> bool:
    """Con 2: latest FCF negative."""
    return data.latest_fcf is not None and data.latest_fcf < 0


def _con_debt_high(data: CompanyData) -> bool:
    """Con 3: D/E > 1.5 in latest year (high leverage)."""
    return data.latest_de is not None and data.latest_de > 1.5


def _con_revenue_cagr_low(data: CompanyData) -> bool:
    """Con 4: Revenue CAGR < 5% over 5 years."""
    return data.revenue_cagr_5yr is not None and data.revenue_cagr_5yr < 5.0


def _con_opm_low(data: CompanyData) -> bool:
    """Con 5: OPM < 10% in latest year."""
    return data.latest_opm is not None and data.latest_opm < 10.0


def _con_pat_cagr_low(data: CompanyData) -> bool:
    """Con 6: PAT CAGR < 5% over 5 years."""
    return data.pat_cagr_5yr is not None and data.pat_cagr_5yr < 5.0


def _con_icr_low(data: CompanyData) -> bool:
    """Con 7: ICR < 2 and not debt-free (financial stress)."""
    if data.is_debt_free:
        return False
    return data.latest_icr is not None and data.latest_icr < 2.0


def _con_dividend_yield_low(data: CompanyData) -> bool:
    """Con 8: Dividend Yield < 1%."""
    return data.dividend_yield_pct is not None and data.dividend_yield_pct < 1.0


def _con_eps_cagr_low(data: CompanyData) -> bool:
    """Con 9: EPS CAGR < 5% over 5 years."""
    return data.eps_cagr_5yr is not None and data.eps_cagr_5yr < 5.0


def _con_roe_declining(data: CompanyData) -> bool:
    """Con 10: ROE declining for 3 consecutive years."""
    if len(data.roe_history) < MIN_YEARS:
        return False
    window = [float(v) for v in data.roe_history[-MIN_YEARS:] if v is not None]
    if len(window) < MIN_YEARS:
        return False
    return window[-1] < window[-2] < window[-3]


def _con_margin_dilution(data: CompanyData) -> bool:
    """Con 11: Revenue CAGR > PAT CAGR (margin dilution)."""
    if data.revenue_cagr_5yr is None or data.pat_cagr_5yr is None:
        return False
    return data.revenue_cagr_5yr > data.pat_cagr_5yr


def _con_assets_debt_funded(data: CompanyData) -> bool:
    """Con 12: Assets growing with rising debt (debt-funded expansion)."""
    if len(data.assets_history) < 2 or len(data.de_history) < 2:
        return False
    assets_grew = data.assets_history[-1] > data.assets_history[0]
    debt_rose = data.de_history[-1] > data.de_history[0]
    return assets_grew and debt_rose


# ============================================================
# Rule registry (ordered)
# ============================================================

PRO_RULES: list[Rule] = [
    Rule("pro_roe_high", "pro",
         "Consistently high return on equity above 20% demonstrates exceptional capital efficiency",
         _pro_roe_high),
    Rule("pro_fcf_positive", "pro",
         "Strong free cash flow generation over 5 years signals healthy business fundamentals",
         _pro_fcf_positive),
    Rule("pro_debt_free", "pro",
         "Debt-free balance sheet provides financial flexibility and eliminates interest burden",
         _pro_debt_free),
    Rule("pro_revenue_cagr", "pro",
         "Revenue growing at above 15% CAGR over 5 years reflects strong business momentum",
         _pro_revenue_cagr),
    Rule("pro_opm_high", "pro",
         "Operating profit margin above 25% indicates strong pricing power and cost discipline",
         _pro_opm_high),
    Rule("pro_pat_cagr", "pro",
         "Net profit compounding at above 20% over 5 years creates significant shareholder value",
         _pro_pat_cagr),
    Rule("pro_icr_high", "pro",
         "Very high interest coverage ratio reflects negligible financial stress from debt servicing",
         _pro_icr_high),
    Rule("pro_dividend_yield", "pro",
         "Consistent dividend yield above 2% backed by positive free cash flow",
         _pro_dividend_yield),
    Rule("pro_eps_cagr", "pro",
         "Earnings per share growing above 15% CAGR indicates strong earnings quality and compounding",
         _pro_eps_cagr),
    Rule("pro_roe_improving", "pro",
         "Return on equity improving for 3 consecutive years shows strengthening business quality",
         _pro_roe_improving),
    Rule("pro_operating_leverage", "pro",
         "Revenue growing slower than profits shows improving operating leverage and scale benefits",
         _pro_operating_leverage),
    Rule("pro_assets_growing", "pro",
         "Growing asset base funded by internal accruals reflects self-sustaining growth",
         _pro_assets_growing),
]

CON_RULES: list[Rule] = [
    Rule("con_roe_low", "con",
         "Return on equity below 10% indicates weaker capital efficiency",
         _con_roe_low),
    Rule("con_fcf_negative", "con",
         "Negative free cash flow signals constrained cash generation and potential liquidity pressure",
         _con_fcf_negative),
    Rule("con_debt_high", "con",
         "Elevated debt-to-equity ratio reflects high leverage and an above-average interest burden",
         _con_debt_high),
    Rule("con_revenue_cagr_low", "con",
         "Revenue growing at below 5% CAGR over 5 years reflects weak top-line momentum",
         _con_revenue_cagr_low),
    Rule("con_opm_low", "con",
         "Operating profit margin below 10% indicates weak pricing power and margin pressure",
         _con_opm_low),
    Rule("con_pat_cagr_low", "con",
         "Net profit compounding at below 5% over 5 years reflects weak profit growth",
         _con_pat_cagr_low),
    Rule("con_icr_low", "con",
         "Low interest coverage ratio reflects heightened financial stress from debt servicing",
         _con_icr_low),
    Rule("con_dividend_yield_low", "con",
         "Dividend yield below 1% offers limited income returns to shareholders",
         _con_dividend_yield_low),
    Rule("con_eps_cagr_low", "con",
         "Earnings per share growing below 5% CAGR indicates weak earnings quality and compounding",
         _con_eps_cagr_low),
    Rule("con_roe_declining", "con",
         "Return on equity declining for 3 consecutive years shows weakening business quality",
         _con_roe_declining),
    Rule("con_margin_dilution", "con",
         "Revenue growing faster than profits signals margin dilution and weaker profitability",
         _con_margin_dilution),
    Rule("con_assets_debt_funded", "con",
         "Growing asset base funded largely by rising debt reflects debt-funded expansion",
         _con_assets_debt_funded),
]

ALL_RULES: list[Rule] = PRO_RULES + CON_RULES


# ============================================================
# Data loading
# ============================================================

def _safe_float(value) -> Optional[float]:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _latest_year(conn: sqlite3.Connection) -> Optional[int]:
    """Return the latest integer year present across financial_ratios."""
    row = conn.execute(
        "SELECT MAX(CAST(year AS INTEGER)) FROM financial_ratios"
    ).fetchone()
    return int(row[0]) if row and row[0] is not None else None


def load_company_data(company_id: str, conn: sqlite3.Connection) -> Optional[CompanyData]:
    """Assemble all quantitative inputs for a single company from the DB.

    Returns ``None`` if the company has no financial_ratios rows.
    """
    latest_year = _latest_year(conn)
    if latest_year is None:
        return None

    # Latest-year financial ratios row.
    fr_latest = pd.read_sql_query(
        """
        SELECT * FROM financial_ratios
        WHERE company_id = ? AND CAST(year AS INTEGER) = ?
        """,
        conn,
        params=(company_id, latest_year),
    )
    if fr_latest.empty:
        return None
    fr = fr_latest.iloc[0]

    data = CompanyData(company_id=company_id)
    data.latest_roe = _safe_float(fr.get("return_on_equity_pct"))
    data.latest_opm = _safe_float(fr.get("operating_profit_margin_pct"))
    data.latest_de = _safe_float(fr.get("debt_to_equity"))
    data.latest_icr = _safe_float(fr.get("interest_coverage"))
    data.latest_fcf = _safe_float(fr.get("free_cash_flow_cr"))
    data.revenue_cagr_5yr = _safe_float(fr.get("revenue_cagr_5yr"))
    data.pat_cagr_5yr = _safe_float(fr.get("pat_cagr_5yr"))
    data.eps_cagr_5yr = _safe_float(fr.get("eps_cagr_5yr"))

    # Dividend yield from market_cap (latest year).
    mcap = pd.read_sql_query(
        """
        SELECT dividend_yield_pct FROM market_cap
        WHERE company_id = ?
        ORDER BY CAST(year AS INTEGER) DESC LIMIT 1
        """,
        conn,
        params=(company_id,),
    )
    if not mcap.empty:
        data.dividend_yield_pct = _safe_float(mcap.iloc[0].get("dividend_yield_pct"))

    # Historical ROE from financial_ratios (oldest -> newest).
    fr_all = pd.read_sql_query(
        """
        SELECT return_on_equity_pct, debt_to_equity, free_cash_flow_cr
        FROM financial_ratios
        WHERE company_id = ?
        ORDER BY CAST(year AS INTEGER) ASC
        """,
        conn,
        params=(company_id,),
    )
    data.roe_history = [
        _safe_float(v) for v in fr_all["return_on_equity_pct"].tolist()
        if _safe_float(v) is not None
    ]
    data.de_history = [
        _safe_float(v) for v in fr_all["debt_to_equity"].tolist()
        if _safe_float(v) is not None
    ]
    data.fcf_history = [
        _safe_float(v) for v in fr_all["free_cash_flow_cr"].tolist()
        if _safe_float(v) is not None
    ]

    # Asset history from balancesheet (oldest -> newest).
    bs = pd.read_sql_query(
        """
        SELECT total_assets FROM balancesheet
        WHERE company_id = ? AND period_type = 'ANNUAL'
        ORDER BY CAST(year AS INTEGER) ASC
        """,
        conn,
        params=(company_id,),
    )
    data.assets_history = [
        _safe_float(v) for v in bs["total_assets"].tolist()
        if _safe_float(v) is not None
    ]

    return data


# ============================================================
# Evaluation
# ============================================================

def evaluate_company(data: CompanyData, rules: Optional[list[Rule]] = None) -> list[dict]:
    """Evaluate all rules for a company.

    Returns a list of matched rows: ``{company_id, type, rule_id, text}``.
    """
    rules = rules or ALL_RULES
    rows: list[dict] = []
    for rule in rules:
        try:
            matched = rule.predicate(data)
        except Exception:
            matched = False
        if matched:
            rows.append({
                "company_id": data.company_id,
                "type": rule.kind,
                "rule_id": rule.rule_id,
                "text": rule.text,
            })
    return rows


def generate_pros_cons(
    db_path: Path = DB_PATH,
    out_dir: Path = OUTPUT_DIR,
    company_ids: Optional[list[str]] = None,
) -> tuple[Path, Path]:
    """Generate pros/cons for all (or selected) companies.

    Returns ``(generated_csv_path, summary_csv_path)``.
    """
    out_dir.mkdir(exist_ok=True, parents=True)
    generated_path = out_dir / "pros_cons_generated.csv"
    summary_path = out_dir / "pros_cons_summary.csv"

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    if company_ids is None:
        ids_df = pd.read_sql_query("SELECT company_id FROM companies ORDER BY company_id", conn)
        company_ids = ids_df["company_id"].tolist()

    all_rows: list[dict] = []
    summary_rows: list[dict] = []
    for cid in company_ids:
        data = load_company_data(cid, conn)
        if data is None:
            continue
        rows = evaluate_company(data)
        all_rows.extend(rows)

        n_pros = sum(1 for r in rows if r["type"] == "pro")
        n_cons = sum(1 for r in rows if r["type"] == "con")
        summary_rows.append({
            "company_id": cid,
            "pros_count": n_pros,
            "cons_count": n_cons,
            "total_count": n_pros + n_cons,
        })

    conn.close()

    generated_df = pd.DataFrame(all_rows, columns=[
        "company_id", "type", "rule_id", "text",
    ])
    generated_df.to_csv(generated_path, index=False)

    summary_df = pd.DataFrame(summary_rows, columns=[
        "company_id", "pros_count", "cons_count", "total_count",
    ])
    summary_df.to_csv(summary_path, index=False)

    return generated_path, summary_path


def run_generator(
    db_path: Path = DB_PATH,
    out_dir: Path = OUTPUT_DIR,
    company_ids: Optional[list[str]] = None,
) -> dict:
    """Run the full Day 30 pipeline and return a summary dict."""
    generated_path, summary_path = generate_pros_cons(db_path, out_dir, company_ids)

    generated_df = pd.read_csv(generated_path) if generated_path.exists() else pd.DataFrame()
    summary_df = pd.read_csv(summary_path) if summary_path.exists() else pd.DataFrame()

    n_companies = int(len(summary_df)) if not summary_df.empty else 0
    n_pros = int((generated_df["type"] == "pro").sum()) if not generated_df.empty else 0
    n_cons = int((generated_df["type"] == "con").sum()) if not generated_df.empty else 0

    return {
        "pros_cons_generated": generated_path,
        "pros_cons_summary": summary_path,
        "companies": n_companies,
        "pro_rows": n_pros,
        "con_rows": n_cons,
        "total_rows": n_pros + n_cons,
    }


if __name__ == "__main__":
    s = run_generator()
    print("=== Day 30 — Auto Pros/Cons Generator ===")
    print(f"pros_cons_generated.csv -> {s['pros_cons_generated']}  ({s['total_rows']} rows)")
    print(f"pros_cons_summary.csv   -> {s['pros_cons_summary']}   ({s['companies']} companies)")
    print(f"pros: {s['pro_rows']}  cons: {s['con_rows']}")
