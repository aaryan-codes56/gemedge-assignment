"""
run_normalizer.py
=================
Standalone CLI script to execute the full DataNormalizer pipeline against
all available raw datasets in data/raw/, producing cleaned outputs and a
data quality report.

Usage:
    ./venv/bin/python run_normalizer.py
"""

import json
import sys
from pathlib import Path

# Add project root to PYTHONPATH
sys.path.append(str(Path(__file__).resolve().parent))

from src.cleaner.data_normalizer import DataNormalizer
from src.utils.file_utils import save_json, save_csv
from src.utils.logger import get_logger

logger = get_logger("run_normalizer")

RAW_DIR     = Path("data/raw")
CLEANED_DIR = Path("data/cleaned")
OUTPUTS_DIR = Path("outputs")


def load_json_safe(path: Path) -> list:
    """Loads a JSON file and returns a list; returns [] if missing or malformed."""
    if not path.exists():
        logger.warning(f"Raw file not found: {path}. Skipping.")
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"Loaded {len(data)} records from {path}")
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.error(f"Failed to load {path}: {e}")
        return []


def main() -> None:
    logger.info("=" * 60)
    logger.info("  DATA NORMALIZATION PIPELINE — STARTING")
    logger.info("=" * 60)

    CLEANED_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    normalizer = DataNormalizer(decimal_precision=2)

    # ── 1. Load raw datasets ──────────────────────────────────────────────────
    raw_listings    = load_json_safe(RAW_DIR / "bid_listings.json")
    raw_results     = load_json_safe(RAW_DIR / "bid_results.json")
    raw_evaluations = load_json_safe(RAW_DIR / "vendor_evaluations.json")

    # ── 2. Normalize ──────────────────────────────────────────────────────────
    listings_df    = normalizer.normalize_listings(raw_listings)
    results_df     = normalizer.normalize_results(raw_results)
    evaluations_df = normalizer.normalize_evaluations(raw_evaluations)

    # ── 3. Integrity checks ───────────────────────────────────────────────────
    normalizer.run_integrity_checks(listings_df, results_df, evaluations_df)

    # ── 4. Persist cleaned outputs ────────────────────────────────────────────
    if not listings_df.empty:
        save_csv(listings_df,  CLEANED_DIR / "cleaned_bid_listings.csv")
        save_json(listings_df.to_dict(orient="records"), CLEANED_DIR / "cleaned_bid_listings.json")

    if not results_df.empty:
        save_csv(results_df,   CLEANED_DIR / "cleaned_bid_results.csv")
        save_json(results_df.to_dict(orient="records"), CLEANED_DIR / "cleaned_bid_results.json")

    if not evaluations_df.empty:
        save_csv(evaluations_df, CLEANED_DIR / "cleaned_vendor_evaluations.csv")
        save_json(evaluations_df.to_dict(orient="records"), CLEANED_DIR / "cleaned_vendor_evaluations.json")

    # ── 5. Save quality report ────────────────────────────────────────────────
    normalizer.save_quality_report(OUTPUTS_DIR)

    # ── 6. Print summary ──────────────────────────────────────────────────────
    report = normalizer.get_quality_report()
    logger.info("=" * 60)
    logger.info("  NORMALIZATION SUMMARY")
    logger.info("=" * 60)
    for section in ("bid_listings", "bid_results", "vendor_evaluations"):
        s = report[section]
        logger.info(
            f"  [{section}] "
            f"in={s['input_count']}  out={s['output_count']}  "
            f"dupes_removed={s['duplicates_removed']}  "
            f"malformed={s['malformed_rows']}"
        )
    warnings = report.get("normalization_warnings", [])
    if warnings:
        logger.warning(f"  Normalization warnings ({len(warnings)}): {warnings[:5]}")
    integrity = report.get("integrity", {})
    if integrity.get("details"):
        logger.warning(f"  Integrity issues: {integrity['details'][:3]}")
    else:
        logger.info("  Integrity: OK — no cross-dataset issues.")
    logger.info("=" * 60)
    logger.info("  DATA NORMALIZATION PIPELINE — COMPLETE")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
