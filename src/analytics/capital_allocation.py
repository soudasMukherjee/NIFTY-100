from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional


@dataclass(frozen=True)
class CapitalAllocationPattern:
    cfo_sign: str
    cfi_sign: str
    cff_sign: str
    pattern_label: str


def _sign_symbol(v: float) -> str:
    if v > 0:
        return "+"
    if v < 0:
        return "-"
    return "0"


def _pattern_label(cfo: float, cfi: float, cff: float, *, cfo_quality_score: Optional[float] = None) -> str:
    """Assign pattern label based on CFO/CFI/CFF signs.

    Spec mapping (exactly as provided):
      - (+,-,-) = Reinvestor
      - (+,-,-) with high CFO/PAT = Shareholder Returns
      - (+,+,-) = Liquidating Assets
      - (-,+,+) = Distress Signal
      - (-,-,+) = Growth Funded by Debt
      - (+,+,+) = Cash Accumulator
      - (-,-,-) = Pre-Revenue
      - (+,-,+) = Mixed

    Note: Only the specific (+,-,-) case is refined using CFO/PAT.
    """

    cfo_s = _sign_symbol(cfo)
    cfi_s = _sign_symbol(cfi)
    cff_s = _sign_symbol(cff)

    # If any value is exactly 0, map to Mixed by default.
    # This avoids creating new labels beyond the spec.
    if "0" in (cfo_s, cfi_s, cff_s):
        return "Mixed"

    if (cfo_s, cfi_s, cff_s) == ("+", "-", "-"):
        if cfo_quality_score is not None and cfo_quality_score > 1.0:
            return "Shareholder Returns"
        return "Reinvestor"

    if (cfo_s, cfi_s, cff_s) == ("+", "+", "-"):
        return "Liquidating Assets"

    if (cfo_s, cfi_s, cff_s) == ("-", "+", "+"):
        return "Distress Signal"

    if (cfo_s, cfi_s, cff_s) == ("-", "-", "+"):
        return "Growth Funded by Debt"

    if (cfo_s, cfi_s, cff_s) == ("+", "+", "+"):
        return "Cash Accumulator"

    if (cfo_s, cfi_s, cff_s) == ("-", "-", "-"):
        return "Pre-Revenue"

    if (cfo_s, cfi_s, cff_s) == ("+", "-", "+"):
        return "Mixed"

    # Fallback for unexpected combinations (shouldn't happen with +/- only).
    return "Mixed"


def classify_capital_allocation_patterns(
    *,
    rows: Iterable[dict],
) -> list[dict]:
    """Classify patterns from an iterable of row dicts.

    Each row dict should contain:
      - company_id
      - year
      - cfo (operating_activity)
      - cfi (investing_activity)
      - cff (financing_activity)
      - optionally: cfo_quality_score (float)

    Returns list of dicts with required columns.
    """
    out: list[dict] = []

    for r in rows:
        cfo = float(r["cfo"])
        cfi = float(r["cfi"])
        cff = float(r["cff"])
        cfo_quality = r.get("cfo_quality_score")
        label = _pattern_label(cfo, cfi, cff, cfo_quality_score=cfo_quality)

        out.append(
            {
                "company_id": r["company_id"],
                "year": r["year"],
                "cfo_sign": _sign_symbol(cfo),
                "cfi_sign": _sign_symbol(cfi),
                "cff_sign": _sign_symbol(cff),
                "pattern_label": label,
            }
        )

    return out

