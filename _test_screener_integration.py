"""
Day 15 — Screener Engine Integration Test
Tests the engine with actual nifty100.db database.
"""

from __future__ import annotations

import sys
import logging
from pathlib import Path

# Setup
ROOT = Path(__file__).resolve().parents[0]
sys.path.insert(0, str(ROOT))

from src.screener.engine import ScreenerEngine, ScreenerRequest, screen_with_preset

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_screener_with_real_db():
    """Test screener with actual nifty100.db."""
    db_path = ROOT / "nifty100.db"
    config_path = ROOT / "src" / "screener" / "screener_config.yaml"

    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        return False

    if not config_path.exists():
        logger.error(f"Config not found: {config_path}")
        return False

    try:
        logger.info("Initializing screener engine...")
        screener = ScreenerEngine(db_path=db_path, config_path=config_path)

        # Print available presets
        print("\n" + "="*60)
        print("AVAILABLE PRESETS")
        print("="*60)
        for preset_id, preset_name in screener.list_presets():
            print(f"  {preset_id:25} → {preset_name}")

        # Test each preset
        print("\n" + "="*60)
        print("SCREENING WITH EACH PRESET")
        print("="*60)

        for preset_id, preset_name in screener.list_presets():
            try:
                logger.info(f"\nScreening with preset: {preset_id} ({preset_name})")
                filters = screener.get_preset_filters(preset_id)
                request = ScreenerRequest(
                    filters=filters,
                    preset_name=preset_id
                )
                result = screener.screen(request)
                print(f"\n{preset_id}:")
                print(f"  → {len(result)} companies matched")

                if len(result) > 0:
                    # Show top 5
                    cols = ["company_id", "return_on_equity_pct", "debt_to_equity",
                           "revenue_cagr_5yr", "composite_quality_score"]
                    available_cols = [c for c in cols if c in result.columns]
                    print(f"\n  Top 5 companies:")
                    for idx, (_, row) in enumerate(result[available_cols].head(5).iterrows(), 1):
                        print(f"    {idx}. {row['company_id']:10} " +
                              " | ".join(f"{c}={row[c]:.2f}" for c in available_cols[1:] if pd.notna(row[c])))

            except Exception as e:
                logger.error(f"Error screening with preset {preset_id}: {e}")

        # Custom filter example
        print("\n" + "="*60)
        print("CUSTOM FILTER EXAMPLE")
        print("="*60)
        print("\nCustom filters: ROE >= 15%, D/E <= 1.0, Dividend Yield >= 2.5%")
        custom_filters = {
            "roe_min": 15.0,
            "de_max": 1.0,
            "dividend_yield_min": 2.5,
        }
        request = ScreenerRequest(filters=custom_filters)
        result = screener.screen(request)
        print(f"  → {len(result)} companies matched")

        if len(result) > 0:
            cols = ["company_id", "return_on_equity_pct", "debt_to_equity",
                   "dividend_yield_pct", "composite_quality_score"]
            available_cols = [c for c in cols if c in result.columns]
            print(f"\n  Top 10 companies:")
            for idx, (_, row) in enumerate(result[available_cols].head(10).iterrows(), 1):
                print(f"    {idx:2}. {row['company_id']:10} " +
                      " | ".join(f"{c}={row[c]:.2f}" for c in available_cols[1:] if pd.notna(row[c])))

        screener.close()
        return True

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    import pandas as pd
    success = test_screener_with_real_db()
    sys.exit(0 if success else 1)
