"""
Sprint 3 · Day 15 — Screener Filter Engine
Loads financial_ratios, applies 15 filterable metrics with custom thresholds,
handles special cases (Financials sector for D/E, Debt Free for ICR),
and returns ranked results with composite_quality_score.
"""

from __future__ import annotations

import logging
import sqlite3
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Optional

import pandas as pd
import yaml

# Setup logging
logger = logging.getLogger(__name__)

# Project root
ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "nifty100.db"
CONFIG_PATH = ROOT / "src" / "screener" / "screener_config.yaml"


# ============================================================
# Data Classes
# ============================================================
@dataclass
class FilterConfig:
    """Configuration for a single metric filter."""
    name: str
    column: str
    table: str
    default_threshold: float
    direction: str  # higher_is_better | lower_is_better
    special_handling: Optional[str] = None  # financials_sector_skip | debt_free_as_infinity


@dataclass
class ScreenerRequest:
    """Request to screen companies with specific filter thresholds."""
    filters: dict[str, float]  # metric_key -> threshold value
    preset_name: Optional[str] = None
    use_latest_year: bool = True  # If True, use most recent year per company


# ============================================================
# Core Screener Engine
# ============================================================
class ScreenerEngine:
    """Load and execute financial screener with threshold-based filtering."""

    def __init__(self, db_path: str | Path = DB_PATH, config_path: str | Path = CONFIG_PATH):
        """Initialize screener with database and config paths."""
        self.db_path = Path(db_path)
        self.config_path = Path(config_path)
        self.conn: Optional[sqlite3.Connection] = None
        self.config: dict[str, Any] = {}
        self.metrics: dict[str, FilterConfig] = {}
        self.presets: dict[str, dict[str, Any]] = {}

        # Load configuration
        self._load_config()

    def _load_config(self) -> None:
        """Load screener_config.yaml and parse metrics + presets."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Screener config not found: {self.config_path}")

        with open(self.config_path) as f:
            self.config = yaml.safe_load(f)

        # Parse metrics from config
        for metric_key, metric_def in self.config.get("metrics", {}).items():
            self.metrics[metric_key] = FilterConfig(
                name=metric_def["name"],
                column=metric_def["column"],
                table=metric_def["table"],
                default_threshold=metric_def["default_threshold"],
                direction=metric_def["direction"],
                special_handling=metric_def.get("special_handling"),
            )

        # Parse presets from config
        self.presets = self.config.get("presets", {})

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self.conn is None:
            if not self.db_path.exists():
                raise FileNotFoundError(f"Database not found: {self.db_path}")
            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.row_factory = sqlite3.Row
        return self.conn

    def close(self) -> None:
        """Close database connection."""
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def _load_ratios_data(self) -> pd.DataFrame:
        """Load financial_ratios with latest year per company."""
        conn = self._get_connection()
        query = """
            SELECT
                fr.company_id,
                fr.year,
                fr.net_profit_margin_pct,
                fr.operating_profit_margin_pct,
                fr.return_on_equity_pct,
                fr.debt_to_equity,
                fr.interest_coverage,
                fr.asset_turnover,
                fr.free_cash_flow_cr,
                fr.fcf_conversion_rate_pct,
                fr.cash_from_operations_cr,
                fr.capex_cr,
                fr.earnings_per_share,
                fr.book_value_per_share,
                fr.dividend_payout_ratio_pct,
                fr.total_debt_cr,
                fr.revenue_cagr_3yr,
                fr.de_yoy_change_pct,
                fr.revenue_cagr_5yr,
                fr.pat_cagr_5yr,
                fr.eps_cagr_5yr,
                fr.composite_quality_score,
                s.broad_sector
            FROM financial_ratios fr
            LEFT JOIN sectors s ON fr.company_id = s.company_id
            WHERE CAST(fr.year AS INTEGER) = (
                SELECT MAX(CAST(fr2.year AS INTEGER)) FROM financial_ratios fr2
                WHERE fr2.company_id = fr.company_id
            )
            ORDER BY fr.company_id, fr.year DESC
        """
        df = pd.read_sql_query(query, conn)
        df["year"] = df["year"].astype("int64")
        return df

    def _load_market_cap_data(self) -> pd.DataFrame:
        """Load market_cap data for latest year per company."""
        conn = self._get_connection()
        query = """
            SELECT
                company_id,
                year,
                market_cap_crore,
                pe_ratio,
                pb_ratio,
                dividend_yield_pct,
                ev_ebitda,
                enterprise_value_crore
            FROM market_cap
            WHERE year = (
                SELECT MAX(year) FROM market_cap mc2
                WHERE mc2.company_id = market_cap.company_id
            )
            ORDER BY company_id, year DESC
        """
        df = pd.read_sql_query(query, conn)
        df["year"] = df["year"].astype("int64")
        return df

    def _load_profitandloss_data(self) -> pd.DataFrame:
        """Load P&L data for latest year per company."""
        conn = self._get_connection()
        query = """
            SELECT
                company_id,
                year,
                sales,
                net_profit,
                eps,
                operating_profit,
                opm_percentage
            FROM profitandloss
            WHERE period_type = 'ANNUAL'
            AND year = (
                SELECT MAX(year) FROM profitandloss pl2
                WHERE pl2.company_id = profitandloss.company_id
                AND pl2.period_type = 'ANNUAL'
            )
            ORDER BY company_id, year DESC
        """
        df = pd.read_sql_query(query, conn)
        df["year"] = df["year"].astype("int64")
        return df

    def screen(self, request: ScreenerRequest) -> pd.DataFrame:
        """
        Apply filters to financial ratios and return ranked results.

        Args:
            request: ScreenerRequest with filter thresholds and options

        Returns:
            Filtered and sorted DataFrame with composite_quality_score
        """
        # Load all relevant data
        logger.info("Loading financial data from database...")
        ratios_df = self._load_ratios_data()
        market_cap_df = self._load_market_cap_data()
        pl_df = self._load_profitandloss_data()

        # Merge datasets
        df = ratios_df.copy()
        df = df.merge(market_cap_df, on=["company_id", "year"], how="left")
        df = df.merge(pl_df[["company_id", "year", "sales", "net_profit"]],
                      on=["company_id", "year"], how="left")

        logger.info(f"Starting with {len(df)} companies")

        # Apply each filter
        filters_applied = request.filters.copy()
        for metric_key, threshold in filters_applied.items():
            if metric_key not in self.metrics:
                logger.warning(f"Unknown metric: {metric_key}, skipping")
                continue

            metric = self.metrics[metric_key]
            df = self._apply_filter(df, metric_key, metric, threshold)
            logger.info(f"After {metric_key} >= {threshold}: {len(df)} companies")

        logger.info(f"Final result: {len(df)} companies passed all filters")

        # Sort by composite_quality_score (descending)
        if "composite_quality_score" in df.columns:
            df = df.sort_values("composite_quality_score", ascending=False, na_position="last")

        return df.reset_index(drop=True)

    def _apply_filter(
        self,
        df: pd.DataFrame,
        metric_key: str,
        metric: FilterConfig,
        threshold: float,
    ) -> pd.DataFrame:
        """
        Apply a single filter with special handling for sector/debt-free cases.

        Args:
            df: Input DataFrame
            metric_key: Key of the metric being filtered
            metric: FilterConfig for this metric
            threshold: Threshold value for filtering

        Returns:
            Filtered DataFrame
        """
        column = metric.column
        direction = metric.direction

        # Handle special cases
        if metric.special_handling == "financials_sector_skip":
            # D/E filter: skip Financials sector entirely
            non_financials = df[df["broad_sector"] != "Financials"].copy()
            financials = df[df["broad_sector"] == "Financials"].copy()

            # Apply filter only to non-Financials
            if direction == "lower_is_better":
                non_financials = non_financials[non_financials[column] <= threshold]
            elif direction == "higher_is_better":
                non_financials = non_financials[non_financials[column] >= threshold]

            # Combine: Financials pass through, non-Financials filtered
            df = pd.concat([non_financials, financials], ignore_index=True)
            logger.debug(f"D/E filter (Financials skip): kept {len(financials)} Financials, "
                        f"filtered {len(non_financials)}/{len(df)-len(financials)} non-Financials")

        elif metric.special_handling == "debt_free_as_infinity":
            # ICR filter: treat "Debt Free" label as infinity (always pass)
            # This is a heuristic: if interest_coverage is None/NaN and company is debt-free
            # (which would be indicated in the data), we should pass it.
            # For now, assume NaN interest_coverage with 0 borrowings = debt-free
            if direction == "higher_is_better":
                # Keep: (1) valid ICR >= threshold, or (2) NaN/None (assumed debt-free)
                mask = (df[column].isna()) | (df[column] >= threshold)
                df = df[mask]
            elif direction == "lower_is_better":
                mask = (df[column].isna()) | (df[column] <= threshold)
                df = df[mask]

        elif metric.special_handling == "debt_free_exact":
            # D/E = 0 exact match: only keep companies with zero debt
            df = df[df[column] == threshold]
            logger.debug(f"Debt-free exact filter: kept {len(df)} zero-debt companies")

        else:
            # Standard filtering
            if direction == "lower_is_better":
                # For max thresholds: column <= threshold
                df = df[df[column] <= threshold]
            elif direction == "higher_is_better":
                # For min thresholds: column >= threshold (ignoring NaN)
                df = df[df[column].notna() & (df[column] >= threshold)]

        return df.copy()

    def get_preset_filters(self, preset_name: str) -> dict[str, float]:
        """
        Get filter thresholds for a named preset.

        Args:
            preset_name: Name of the preset (e.g., 'growth_focused')

        Returns:
            Dictionary of metric_key -> threshold
        """
        if preset_name not in self.presets:
            raise ValueError(f"Unknown preset: {preset_name}")

        preset = self.presets[preset_name]
        return preset.get("filters", {})

    def list_presets(self) -> list[tuple[str, str]]:
        """List all available preset filters."""
        return [(name, p["name"]) for name, p in self.presets.items()]

    def list_metrics(self) -> list[tuple[str, str, float]]:
        """List all available metrics with defaults."""
        return [
            (key, metric.name, metric.default_threshold)
            for key, metric in self.metrics.items()
        ]


# ============================================================
# Utility Functions
# ============================================================
def create_screener(db_path: str | Path = DB_PATH, config_path: str | Path = CONFIG_PATH) -> ScreenerEngine:
    """Create and return a ScreenerEngine instance."""
    return ScreenerEngine(db_path=db_path, config_path=config_path)


def screen_with_preset(
    preset_name: str,
    custom_overrides: Optional[dict[str, float]] = None,
    db_path: str | Path = DB_PATH,
    config_path: str | Path = CONFIG_PATH,
) -> pd.DataFrame:
    """
    Convenience function to screen with a preset and optional custom overrides.

    Args:
        preset_name: Name of the preset filter
        custom_overrides: Optional dict to override preset thresholds
        db_path: Path to the database
        config_path: Path to the config file

    Returns:
        Filtered DataFrame
    """
    screener = create_screener(db_path=db_path, config_path=config_path)
    try:
        # Get preset filters
        filters = screener.get_preset_filters(preset_name)

        # Apply custom overrides if provided
        if custom_overrides:
            filters.update(custom_overrides)

        # Create request and screen
        request = ScreenerRequest(filters=filters, preset_name=preset_name)
        return screener.screen(request)
    finally:
        screener.close()


# ============================================================
# CLI Entry Point (for testing)
# ============================================================
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    screener = create_screener()

    # List available presets
    print("\n=== Available Presets ===")
    for preset_id, preset_name in screener.list_presets():
        print(f"  {preset_id}: {preset_name}")

    # List available metrics
    print("\n=== Available Metrics (with defaults) ===")
    for metric_key, metric_name, default_threshold in screener.list_metrics():
        print(f"  {metric_key}: {metric_name} (default: {default_threshold})")

    # Example: screen with growth_focused preset
    print("\n=== Screening with 'growth_focused' preset ===")
    try:
        request = ScreenerRequest(
            filters=screener.get_preset_filters("growth_focused")
        )
        results = screener.screen(request)
        print(f"\nFound {len(results)} companies matching 'growth_focused' criteria:")
        print(results[["company_id", "return_on_equity_pct", "revenue_cagr_5yr",
                      "pat_cagr_5yr", "composite_quality_score"]].head(10))
    except Exception as e:
        logger.error(f"Screening failed: {e}", exc_info=True)
    finally:
        screener.close()
