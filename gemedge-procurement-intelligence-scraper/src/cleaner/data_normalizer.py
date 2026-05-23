"""
Data Normalizer — Unified Analytics-Ready Cleaning Pipeline
=============================================================
Inherits from BaseCleaner and provides a single entry-point for normalizing
all three GeM procurement datasets:

  1. bid_listings       — paginated listing records
  2. bid_results        — deep detail extraction results
  3. vendor_evaluations — vendor competition intelligence

Key normalizations applied:
  - Datetime → ISO 8601 (YYYY-MM-DDTHH:MM:SS), raw value preserved on failure
  - Currency / numeric → float with configurable precision, null-safe
  - Text → unicode-cleaned, consistent Title Case, whitespace collapsed
  - Missing values → None (JSON null), empty strings → None
  - Boolean fields → strict Python bool
  - Duplicate detection on bid_id / (bid_id, vendor_name)

Outputs:
  data/cleaned/cleaned_bid_listings.{csv,json}
  data/cleaned/cleaned_bid_results.{csv,json}
  data/cleaned/cleaned_vendor_evaluations.{csv,json}
  outputs/data_quality_report.json
"""

import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from src.core.base import BaseCleaner
from src.utils.logger import get_logger
from src.utils.file_utils import save_json

logger = get_logger("data_normalizer")

# ─── Configuration ─────────────────────────────────────────────────────────────

DECIMAL_PRECISION: int = 2
NULL_SENTINEL: str = "N/A"          # raw string treated as missing
ISO_OUTPUT_FORMAT: str = "%Y-%m-%dT%H:%M:%S"

# All datetime input patterns seen in GeM portal outputs (most specific first)
_DATE_PATTERNS: List[str] = [
    "%d-%m-%Y %I:%M %p",       # "19-05-2026 4:14 PM"  (no leading zero)
    "%d-%m-%Y %I:%M:%S %p",    # "19-05-2026 04:14:00 PM"
    "%d-%m-%Y %H:%M:%S",       # "13-05-2026 18:23:13"
    "%d-%m-%Y %H:%M",          # "13-05-2026 18:23"
    "%d-%m-%Y",                 # "13-05-2026"
    "%Y-%m-%dT%H:%M:%S",       # already ISO
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
]

# ── Column schema definitions (stable column order for analytics exports) ──────

_LISTING_COLUMNS: List[str] = [
    "bid_id", "bid_number", "item_category", "items_count",
    "department", "ministry", "buyer_name",
    "quantity", "bid_value", "bid_status",
    "start_date", "end_date",
    "bid_link",
]

_RESULT_COLUMNS: List[str] = [
    "bid_id", "bid_number", "bid_status", "bid_validity",
    "start_date", "end_date", "opening_date", "contract_duration",
    "ministry", "department", "organisation", "office",
    "winner_name", "awarded_value",
    "technical_sellers_count", "financial_sellers_count",
]

_VENDOR_COLUMNS: List[str] = [
    "bid_id", "vendor_name", "vendor_rank",
    "quoted_price", "technically_qualified", "financially_qualified",
    "bid_status", "remarks", "evaluation_round", "awarded_flag",
    "l1_price", "l1_vs_vendor_diff", "l1_vs_vendor_pct",
    "avg_quote", "price_spread_pct",
    "anomaly_single_vendor", "anomaly_duplicate_price",
    "anomaly_missing_rank", "anomaly_abnormal_spread",
    "anomaly_low_participation",
]


# ─── DataNormalizer ─────────────────────────────────────────────────────────────

class DataNormalizer(BaseCleaner):
    """
    Production-grade normalization pipeline for GeM procurement intelligence datasets.
    Implements all BaseCleaner abstract methods and exposes dataset-specific entry-points.
    """

    def __init__(self, decimal_precision: int = DECIMAL_PRECISION) -> None:
        super().__init__()
        self.decimal_precision = decimal_precision
        self._quality_report: Dict[str, Any] = self._blank_quality_report()

    # ══════════════════════════════════════════════════════════════════════════
    # PUBLIC — DATASET ENTRY-POINTS
    # ══════════════════════════════════════════════════════════════════════════

    def normalize_listings(self, records: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Normalizes bid listing records and returns an analytics-ready DataFrame.
        """
        self.logger.info(f"Normalizing {len(records)} bid listing records...")
        section = "bid_listings"
        self._quality_report[section]["input_count"] = len(records)

        cleaned: List[Dict[str, Any]] = []
        for idx, rec in enumerate(records):
            try:
                cleaned.append(self.clean_record(rec, dataset="listing"))
            except Exception as e:
                self.logger.warning(f"[listing row {idx}] Clean error: {e}")
                self._quality_report[section]["malformed_rows"] += 1

        df = self.process_to_dataframe(cleaned, columns=_LISTING_COLUMNS)
        df = self._deduplicate(df, key="bid_id", section=section)
        self.validate(df)
        self._quality_report[section]["output_count"] = len(df)
        self.logger.info(f"Listings: {len(df)} clean rows after dedup.")
        return df

    def normalize_results(self, records: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Normalizes bid result records and returns an analytics-ready DataFrame.
        """
        self.logger.info(f"Normalizing {len(records)} bid result records...")
        section = "bid_results"
        self._quality_report[section]["input_count"] = len(records)

        cleaned: List[Dict[str, Any]] = []
        for idx, rec in enumerate(records):
            try:
                cleaned.append(self.clean_record(rec, dataset="result"))
            except Exception as e:
                self.logger.warning(f"[result row {idx}] Clean error: {e}")
                self._quality_report[section]["malformed_rows"] += 1

        df = self.process_to_dataframe(cleaned, columns=_RESULT_COLUMNS)
        df = self._deduplicate(df, key="bid_id", section=section)
        self.validate(df)
        self._quality_report[section]["output_count"] = len(df)
        self.logger.info(f"Results: {len(df)} clean rows after dedup.")
        return df

    def normalize_evaluations(self, records: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Normalizes vendor evaluation records and returns an analytics-ready DataFrame.
        """
        self.logger.info(f"Normalizing {len(records)} vendor evaluation records...")
        section = "vendor_evaluations"
        self._quality_report[section]["input_count"] = len(records)

        cleaned: List[Dict[str, Any]] = []
        for idx, rec in enumerate(records):
            try:
                cleaned.append(self.clean_record(rec, dataset="vendor"))
            except Exception as e:
                self.logger.warning(f"[vendor row {idx}] Clean error: {e}")
                self._quality_report[section]["malformed_rows"] += 1

        df = self.process_to_dataframe(cleaned, columns=_VENDOR_COLUMNS)
        df = self._deduplicate_composite(df, keys=["bid_id", "vendor_name"], section=section)
        self.validate(df)
        self._quality_report[section]["output_count"] = len(df)
        self.logger.info(f"Evaluations: {len(df)} clean rows after dedup.")
        return df

    # ══════════════════════════════════════════════════════════════════════════
    # BASE CLEANER IMPLEMENTATIONS
    # ══════════════════════════════════════════════════════════════════════════

    def clean_record(self, raw_record: Dict[str, Any], dataset: str = "listing") -> Dict[str, Any]:
        """
        Dispatches record cleaning to the appropriate dataset-specific cleaner.
        """
        if dataset == "listing":
            return self._clean_listing_record(raw_record)
        elif dataset == "result":
            return self._clean_result_record(raw_record)
        elif dataset == "vendor":
            return self._clean_vendor_record(raw_record)
        else:
            raise ValueError(f"Unknown dataset type: '{dataset}'")

    def process_to_dataframe(
        self,
        records: List[Dict[str, Any]],
        columns: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Converts cleaned dicts to a DataFrame with stable column ordering.
        Columns not present in data are added as None for schema consistency.
        """
        if not records:
            df = pd.DataFrame(columns=columns or [])
            return df

        df = pd.DataFrame(records)

        if columns:
            # Ensure all required columns exist, add missing as None
            for col in columns:
                if col not in df.columns:
                    df[col] = None
            # Reorder and select only defined schema columns
            extra = [c for c in df.columns if c not in columns]
            df = df[columns + extra]

        return df

    def validate(self, df: pd.DataFrame) -> bool:
        """
        Validates DataFrame is non-empty, has bid_id if present, and counts null fields.
        """
        if df.empty:
            self.logger.warning("Validation: DataFrame is empty — no records to validate.")
            return False

        if "bid_id" in df.columns:
            null_ids = df["bid_id"].isna().sum()
            if null_ids:
                self.logger.warning(f"Validation: {null_ids} rows have null bid_id.")

        # Count missing values per column and record in quality report
        null_counts = df.isnull().sum().to_dict()
        self.logger.debug(f"Null counts per column: {null_counts}")
        return True

    # ══════════════════════════════════════════════════════════════════════════
    # PRIVATE — DATASET-SPECIFIC CLEANERS
    # ══════════════════════════════════════════════════════════════════════════

    def _clean_listing_record(self, r: Dict[str, Any]) -> Dict[str, Any]:
        """Normalizes a single bid listing record."""
        items_raw = r.get("items", [])

        # Extract ministry from department hierarchy (Ministry / Department)
        dept_raw   = self._clean_text(r.get("department"))
        ministry   = None
        if dept_raw and "/" in dept_raw:
            parts    = [p.strip() for p in dept_raw.split("/", 1)]
            ministry = parts[0] if parts else None
            dept_raw = parts[1] if len(parts) > 1 else dept_raw

        out: Dict[str, Any] = {
            "bid_id":        self._clean_text(r.get("bid_id")),
            "bid_number":    self._clean_text(r.get("bid_number")),
            "item_category": self._clean_text(r.get("item_category")),
            "items_count":   len(items_raw) if isinstance(items_raw, list) else 0,
            "department":    dept_raw,
            "ministry":      ministry,
            "buyer_name":    self._clean_text(r.get("buyer_name")),
            "quantity":      self._clean_int(r.get("quantity")),
            "bid_value":     self._clean_float(r.get("bid_value")),
            "bid_status":    self._clean_text(r.get("bid_status")),
            "start_date":    self._clean_datetime(r.get("start_date"), "start_date"),
            "end_date":      self._clean_datetime(r.get("end_date"), "end_date"),
            "bid_link":      self._clean_text(r.get("bid_link")),
        }
        self._record_missing(out, "bid_listings")
        return out

    def _clean_result_record(self, r: Dict[str, Any]) -> Dict[str, Any]:
        """Normalizes a single bid result record."""
        tech = r.get("technical_sellers", [])
        fin  = r.get("financial_sellers", [])
        out: Dict[str, Any] = {
            "bid_id":                    self._clean_text(r.get("bid_id")),
            "bid_number":                self._clean_text(r.get("bid_number")),
            "bid_status":                self._clean_text(r.get("bid_status")),
            "bid_validity":              self._clean_text(r.get("bid_validity")),
            "start_date":                self._clean_datetime(r.get("start_date"), "start_date"),
            "end_date":                  self._clean_datetime(r.get("end_date"), "end_date"),
            "opening_date":              self._clean_datetime(r.get("opening_date"), "opening_date"),
            "contract_duration":         self._clean_text(r.get("contract_duration")),
            "ministry":                  self._clean_text(r.get("ministry")),
            "department":                self._clean_text(r.get("department")),
            "organisation":              self._clean_text(r.get("organisation")),
            "office":                    self._clean_text(r.get("office")),
            "winner_name":               self._clean_text(r.get("winner_name")),
            "awarded_value":             self._clean_float(r.get("awarded_value")),
            "technical_sellers_count":   len(tech) if isinstance(tech, list) else 0,
            "financial_sellers_count":   len(fin)  if isinstance(fin,  list) else 0,
        }
        self._record_missing(out, "bid_results")
        return out

    def _clean_vendor_record(self, r: Dict[str, Any]) -> Dict[str, Any]:
        """Normalizes a single vendor evaluation record."""
        out: Dict[str, Any] = {
            "bid_id":                   self._clean_text(r.get("bid_id")),
            "vendor_name":              self._clean_text(r.get("vendor_name")),
            "vendor_rank":              self._clean_text(r.get("vendor_rank")),
            "quoted_price":             self._clean_float(r.get("quoted_price")),
            "technically_qualified":    self._clean_bool(r.get("technically_qualified")),
            "financially_qualified":    self._clean_bool(r.get("financially_qualified")),
            "bid_status":               self._clean_text(r.get("bid_status")),
            "remarks":                  self._clean_text(r.get("remarks")),
            "evaluation_round":         self._clean_text(r.get("evaluation_round")),
            "awarded_flag":             self._clean_bool(r.get("awarded_flag")),
            "l1_price":                 self._clean_float(r.get("l1_price")),
            "l1_vs_vendor_diff":        self._clean_float(r.get("l1_vs_vendor_diff")),
            "l1_vs_vendor_pct":         self._clean_float(r.get("l1_vs_vendor_pct")),
            "avg_quote":                self._clean_float(r.get("avg_quote")),
            "price_spread_pct":         self._clean_float(r.get("price_spread_pct")),
            "anomaly_single_vendor":    self._clean_bool(r.get("anomaly_single_vendor")),
            "anomaly_duplicate_price":  self._clean_bool(r.get("anomaly_duplicate_price")),
            "anomaly_missing_rank":     self._clean_bool(r.get("anomaly_missing_rank")),
            "anomaly_abnormal_spread":  self._clean_bool(r.get("anomaly_abnormal_spread")),
            "anomaly_low_participation":self._clean_bool(r.get("anomaly_low_participation")),
        }
        self._record_missing(out, "vendor_evaluations")
        return out

    # ══════════════════════════════════════════════════════════════════════════
    # PRIVATE — ATOMIC NORMALIZERS
    # ══════════════════════════════════════════════════════════════════════════

    def _clean_datetime(self, raw: Any, field_hint: str = "") -> Optional[str]:
        """
        Parses a raw date string into ISO 8601 format (YYYY-MM-DDTHH:MM:SS).
        Returns None and logs a warning on failure; preserves None inputs silently.
        """
        if raw is None:
            return None
        raw_str = str(raw).strip()
        if not raw_str or raw_str in (NULL_SENTINEL, "null", "None", ""):
            return None

        # Already ISO 8601?
        if re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", raw_str):
            return raw_str

        for pattern in _DATE_PATTERNS:
            try:
                dt = datetime.strptime(raw_str, pattern)
                return dt.strftime(ISO_OUTPUT_FORMAT)
            except ValueError:
                continue

        # All patterns failed — log and return None
        self.logger.warning(
            f"datetime parse failed for field '{field_hint}': raw='{raw_str}'. "
            f"Storing as None."
        )

        self._quality_report.setdefault("normalization_warnings", []).append(
            f"datetime: '{raw_str}' ({field_hint})"
        )
        return None

    def _clean_float(self, raw: Any) -> Optional[float]:
        """
        Cleans currency / numeric strings to float with configured precision.
        Handles ₹, Rs., commas, whitespace. Returns None for unparseable values.
        """
        if raw is None:
            return None
        if isinstance(raw, (int, float)):
            return round(float(raw), self.decimal_precision)
        raw_str = re.sub(r"[₹`\$£€,\s]", "", str(raw))
        raw_str = raw_str.replace("Rs.", "").replace("INR", "").strip()
        if not raw_str or raw_str in (NULL_SENTINEL, "null", "None"):
            return None
        try:
            return round(float(raw_str), self.decimal_precision)
        except ValueError:
            self.logger.debug(f"float parse failed: '{raw}'")
            return None

    def _clean_int(self, raw: Any) -> Optional[int]:
        """Coerces to int, returns None on failure."""
        if raw is None:
            return None
        try:
            return int(float(str(raw).replace(",", "").strip()))
        except (ValueError, TypeError):
            return None

    def _clean_bool(self, raw: Any) -> Optional[bool]:
        """Normalises truthy / falsy values to strict Python bool."""
        if raw is None:
            return None
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, (int, float)):
            return bool(raw)
        s = str(raw).strip().lower()
        if s in ("true", "yes", "1", "qualified"):
            return True
        if s in ("false", "no", "0", "disqualified", "n/a", ""):
            return False
        return None

    def _clean_text(self, raw: Any) -> Optional[str]:
        """
        Normalises a text field:
          1. Unicode NFKC normalisation (removes zero-width chars, homoglyphs)
          2. Collapses internal whitespace
          3. Strips leading/trailing whitespace
          4. Null-sentinel → None
          5. Strips common badge noise (e.g. "Under PMA", "MSE" badge suffixes)
        Text capitalization is left as-is (Title Case would break acronyms).
        """
        if raw is None:
            return None
        # Handle list inputs (e.g. items)
        if isinstance(raw, list):
            return None
        s = unicodedata.normalize("NFKC", str(raw))
        s = re.sub(r"[ \t]+", " ", s).strip()

        # Strip badge noise lines (text after first newline, common in portal exports)
        s = s.split("\n")[0].strip()

        if not s or s in (NULL_SENTINEL, "null", "None", "N/A", "na", "NA"):
            return None
        return s

    # ══════════════════════════════════════════════════════════════════════════
    # PRIVATE — DEDUPLICATION
    # ══════════════════════════════════════════════════════════════════════════

    def _deduplicate(
        self, df: pd.DataFrame, key: str, section: str
    ) -> pd.DataFrame:
        """Deduplicates on a single primary key column."""
        before = len(df)
        df = df.drop_duplicates(subset=[key], keep="first").reset_index(drop=True)
        removed = before - len(df)
        if removed:
            self.logger.warning(f"[{section}] Removed {removed} duplicate rows on '{key}'.")
            self._quality_report[section]["duplicates_removed"] += removed
        return df

    def _deduplicate_composite(
        self, df: pd.DataFrame, keys: List[str], section: str
    ) -> pd.DataFrame:
        """Deduplicates on a composite key (all keys columns)."""
        before = len(df)
        df = df.drop_duplicates(subset=keys, keep="first").reset_index(drop=True)
        removed = before - len(df)
        if removed:
            self.logger.warning(f"[{section}] Removed {removed} duplicate rows on {keys}.")
            self._quality_report[section]["duplicates_removed"] += removed
        return df

    # ══════════════════════════════════════════════════════════════════════════
    # PRIVATE — INTEGRITY CHECKS
    # ══════════════════════════════════════════════════════════════════════════

    def run_integrity_checks(
        self,
        listings_df: pd.DataFrame,
        results_df: pd.DataFrame,
        vendors_df: pd.DataFrame,
    ) -> Dict[str, Any]:
        """
        Cross-dataset integrity validation:
          - Orphan vendor evaluations (bid_id not in results)
          - Inconsistent awarded_vendor vs winner_name
          - Listings with no matching results
        Returns an integrity diagnostics dict appended to quality report.
        """
        integrity: Dict[str, Any] = {
            "orphan_vendor_evaluations": 0,
            "inconsistent_awarded_vendors": 0,
            "listings_without_results": 0,
            "details": [],
        }

        result_bid_ids  = set(results_df["bid_id"].dropna()) if not results_df.empty else set()
        listing_bid_ids = set(listings_df["bid_id"].dropna()) if not listings_df.empty else set()

        # Orphan vendor evaluations
        if not vendors_df.empty and "bid_id" in vendors_df.columns:
            orphan_mask = ~vendors_df["bid_id"].isin(result_bid_ids)
            orphan_count = int(orphan_mask.sum())
            integrity["orphan_vendor_evaluations"] = orphan_count
            if orphan_count:
                orphan_ids = vendors_df.loc[orphan_mask, "bid_id"].unique().tolist()
                integrity["details"].append(
                    f"Orphan vendor bid_ids (no matching result): {orphan_ids[:5]}"
                )

        # Listings without results
        if result_bid_ids and listing_bid_ids:
            no_results = listing_bid_ids - result_bid_ids
            integrity["listings_without_results"] = len(no_results)
            if no_results:
                integrity["details"].append(
                    f"Listings without result records: {list(no_results)[:5]}"
                )

        # Inconsistent awarded vendors (winner_name vs L1 vendor_name)
        if not results_df.empty and not vendors_df.empty:
            if "winner_name" in results_df.columns and "awarded_flag" in vendors_df.columns:
                l1_vendors = vendors_df[vendors_df["awarded_flag"]][["bid_id", "vendor_name"]]
                for _, row in l1_vendors.iterrows():
                    match = results_df[results_df["bid_id"] == row["bid_id"]]
                    if not match.empty:
                        result_winner = match.iloc[0].get("winner_name")
                        if result_winner and result_winner != row["vendor_name"]:
                            integrity["inconsistent_awarded_vendors"] += 1
                            integrity["details"].append(
                                f"Inconsistent winner for {row['bid_id']}: "
                                f"result='{result_winner}' vs vendor L1='{row['vendor_name']}'"
                            )

        self._quality_report["integrity"] = integrity
        if integrity["details"]:
            self.logger.warning(f"Integrity issues found: {integrity}")
        else:
            self.logger.info("Integrity checks passed — no cross-dataset issues detected.")

        return integrity

    # ══════════════════════════════════════════════════════════════════════════
    # PRIVATE — QUALITY REPORT
    # ══════════════════════════════════════════════════════════════════════════

    def _record_missing(self, record: Dict[str, Any], section: str) -> None:
        """Increments missing field counts in the quality report for a cleaned record."""
        for field, val in record.items():
            if val is None:
                self._quality_report[section]["missing_field_counts"][field] = (
                    self._quality_report[section]["missing_field_counts"].get(field, 0) + 1
                )

    def _blank_quality_report(self) -> Dict[str, Any]:
        """Returns a fresh quality report skeleton."""
        def section() -> Dict[str, Any]:
            return {
                "input_count":        0,
                "output_count":       0,
                "malformed_rows":     0,
                "duplicates_removed": 0,
                "missing_field_counts": {},
            }
        return {
            "bid_listings":         section(),
            "bid_results":          section(),
            "vendor_evaluations":   section(),
            "normalization_warnings": [],
            "integrity": {},
            "generated_at": datetime.now().strftime(ISO_OUTPUT_FORMAT),
        }

    def get_quality_report(self) -> Dict[str, Any]:
        """Returns the accumulated quality report dictionary."""
        return self._quality_report

    def save_quality_report(self, output_dir: Path) -> None:
        """Writes the quality report to outputs/data_quality_report.json."""
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / "data_quality_report.json"
        save_json(self._quality_report, report_path)
        self.logger.info(f"Data quality report saved to: {report_path}")
