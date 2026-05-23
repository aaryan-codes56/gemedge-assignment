"""
run_reports.py
==============
CLI entry-point for the procurement intelligence reporting engine.
Loads cleaned datasets, runs all analytics modules, and generates:
  - vendor_intelligence_report.json/csv
  - ministry_intelligence_report.json/csv
  - pricing_intelligence_report.json/csv
  - anomaly_report.json/csv
  - category_intelligence_report.json/csv
  - procurement_intelligence_dashboard.html
  - executive_summary.md

Usage:
    ./venv/bin/python run_reports.py
"""

import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))

import pandas as pd
from src.insights.procurement_report_generator import ProcurementReportGenerator
from src.utils.logger import get_logger

logger = get_logger("run_reports")

CLEANED_DIR = Path("data/cleaned")
OUTPUTS_DIR = Path("outputs")


def _load_csv(name: str) -> pd.DataFrame:
    path = CLEANED_DIR / name
    if not path.exists():
        logger.warning(f"Cleaned file not found: {path}. Using empty DataFrame.")
        return pd.DataFrame()
    df = pd.read_csv(path)
    logger.info(f"Loaded {len(df)} rows from {path}")
    return df


def main() -> None:
    logger.info("=" * 60)
    logger.info("  PROCUREMENT INTELLIGENCE REPORTING ENGINE — START")
    logger.info("=" * 60)

    listings_df    = _load_csv("cleaned_bid_listings.csv")
    results_df     = _load_csv("cleaned_bid_results.csv")
    evaluations_df = _load_csv("cleaned_vendor_evaluations.csv")

    generator = ProcurementReportGenerator(output_dir=OUTPUTS_DIR)
    master    = generator.run_full_pipeline(listings_df, results_df, evaluations_df)

    valid = generator.validate(master)
    logger.info(f"Report validation: {'PASSED' if valid else 'FAILED'}")

    logger.info("=" * 60)
    logger.info(f"  Summary: {master['summary']}")
    logger.info(f"  Anomaly risk level: {master['anomalies'].get('anomaly_risk_level','N/A')}")
    logger.info("  REPORTING ENGINE — COMPLETE")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
