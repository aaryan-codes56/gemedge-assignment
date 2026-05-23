"""
Vendor Evaluation Extractor
============================
Production-grade procurement intelligence layer that:
  - Parses technical and financial evaluation tables from GeM detail pages
  - Maps dynamic column headers defensively (no hardcoded column indexes)
  - Computes pricing spread analytics (L1 gap, bid spread %, avg quote)
  - Detects procurement anomalies (single-vendor, duplicate price, etc.)
  - Validates extracted evaluation records via SchemaValidator
  - Returns intelligence-ready VendorDetail records
"""

import re
from typing import Any, Dict, List, Tuple
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException

from src.core.base import BaseExtractor
from src.core.models import VendorDetail
from src.core.error_handler import ScraperExtractionException
from src.utils.logger import get_logger

# ─── Constants ────────────────────────────────────────────────────────────────

# Header synonyms for dynamic column mapping (case-insensitive partial match)
_TECH_COL_SYNONYMS: Dict[str, List[str]] = {
    "s_no":             ["s.no", "s no", "sr", "serial", "#"],
    "seller_name":      ["seller", "vendor", "firm", "company", "bidder", "name"],
    "participated_on":  ["participated", "date", "bid date", "submission"],
    "mse_mii_status":   ["mse", "mii", "msme", "make in india", "startup"],
    "tech_status":      ["status", "result", "qualified", "evaluation"],
}

_FIN_COL_SYNONYMS: Dict[str, List[str]] = {
    "s_no":             ["s.no", "s no", "sr", "serial", "#"],
    "seller_name":      ["seller", "vendor", "firm", "company", "bidder", "name"],
    "offered_item":     ["item", "offered", "product", "description", "category"],
    "quoted_price":     ["price", "amount", "total", "value", "quote", "bid price"],
    "rank":             ["rank", "l1", "position", "order"],
}

# Anomaly thresholds
_LOW_PARTICIPATION_THRESHOLD = 3     # flag if fewer than N vendors participate
_ABNORMAL_SPREAD_THRESHOLD_PCT = 100 # flag if price spread > N%


class VendorEvaluationExtractor(BaseExtractor):
    """
    Intelligence-grade evaluation table parser for GeM Bids Portal detail pages.

    Supports:
    - Dynamic column header mapping (no hardcoded indexes)
    - Variable column counts and absent optional sections
    - Pricing competition analytics (L1 gap, spread %, avg quote)
    - Procurement anomaly detection
    - Full validation and safe defaults
    """

    def __init__(self) -> None:
        super().__init__()
        self.logger = get_logger("vendor_evaluation_extractor")

    # ══════════════════════════════════════════════════════════════════════════
    # PUBLIC INTERFACE
    # ══════════════════════════════════════════════════════════════════════════

    def extract_item(self, driver: WebDriver) -> Dict[str, Any]:
        """
        Parses evaluation tables from the active detail page driver instance.
        Returns a dict containing 'vendor_records' (List[Dict]) and 'analytics' dict.
        """
        try:
            self._ensure_panels_expanded(driver)
            bid_id = self._extract_bid_id(driver)
            bid_status = self._extract_bid_status(driver)

            # ── Technical evaluation ─────────────────────────────────────────
            tech_col_map, tech_rows = self._parse_table_section(
                driver,
                section_id="collapseTwo",
                col_synonyms=_TECH_COL_SYNONYMS
            )
            tech_records = self._build_tech_records(tech_rows, tech_col_map)

            # ── Financial evaluation ─────────────────────────────────────────
            fin_col_map, fin_rows = self._parse_table_section(
                driver,
                section_id="collapseThree",
                col_synonyms=_FIN_COL_SYNONYMS
            )
            fin_records = self._build_fin_records(fin_rows, fin_col_map)

            # ── Merge into VendorDetail records ──────────────────────────────
            vendor_records = self._merge_evaluations(
                bid_id, bid_status, tech_records, fin_records
            )

            # ── Pricing analytics ────────────────────────────────────────────
            analytics = self._compute_pricing_analytics(vendor_records)

            # ── Annotate analytics into each record ──────────────────────────
            for rec in vendor_records:
                rec["l1_price"]          = analytics["l1_price"]
                rec["avg_quote"]         = analytics["avg_quote"]
                rec["price_spread_pct"]  = analytics["price_spread_pct"]
                quoted = rec["quoted_price"]
                if analytics["l1_price"] > 0 and quoted > 0:
                    rec["l1_vs_vendor_diff"] = round(quoted - analytics["l1_price"], 2)
                    rec["l1_vs_vendor_pct"]  = round(
                        (quoted - analytics["l1_price"]) / analytics["l1_price"] * 100, 2
                    )

            # ── Anomaly detection ────────────────────────────────────────────
            anomaly_flags = self._detect_anomalies(vendor_records, analytics)
            for rec in vendor_records:
                rec.update(anomaly_flags)

            return {
                "bid_id": bid_id,
                "bid_status": bid_status,
                "vendor_records": vendor_records,
                "analytics": analytics,
                "anomaly_flags": anomaly_flags,
            }

        except StaleElementReferenceException as e:
            raise ScraperExtractionException(
                message="Stale element during vendor evaluation extraction.",
                details=str(e)
            ) from e
        except Exception as e:
            self.logger.error(f"Vendor evaluation extraction failed: {e}", exc_info=True)
            return {}

    def extract_batch(self, raw_collection: List[Any]) -> List[Dict[str, Any]]:
        """Not applicable for page-level extraction; use extract_item(driver)."""
        raise NotImplementedError("Use extract_item(driver) for page-level parsing.")

    def validate(self, extracted_record: Dict[str, Any]) -> bool:
        """
        Validates a single VendorDetail dict for required fields and type sanity.
        Returns True if valid, logs warnings and returns False if not.
        """
        errors: List[str] = []
        warnings: List[str] = []

        required = ["bid_id", "vendor_name", "vendor_rank", "quoted_price",
                    "evaluation_round"]
        for field in required:
            if field not in extracted_record or extracted_record[field] is None:
                errors.append(f"Missing required field: '{field}'")
            elif isinstance(extracted_record[field], str) and not extracted_record[field].strip():
                errors.append(f"Required field '{field}' is blank.")

        # Numeric sanity
        price = extracted_record.get("quoted_price", -1)
        try:
            if float(price) < 0:
                errors.append(f"quoted_price cannot be negative: {price}")
        except (ValueError, TypeError):
            errors.append(f"quoted_price is not numeric: {price!r}")

        # Rank format check
        rank = extracted_record.get("vendor_rank", "")
        if rank not in ("N/A", "") and not re.match(r"^L\d+$", str(rank)):
            warnings.append(f"Unexpected vendor_rank format: '{rank}'")

        # Duplicate vendor name warning
        if extracted_record.get("anomaly_duplicate_price"):
            warnings.append("Vendor has identical quoted price to another participant — possible collusion risk.")

        if errors:
            self.logger.error(f"VendorDetail validation failed — Errors: {errors}")
            return False
        if warnings:
            self.logger.warning(f"VendorDetail validation warnings: {warnings}")
        return True

    # ══════════════════════════════════════════════════════════════════════════
    # PRIVATE — DOM HELPERS
    # ══════════════════════════════════════════════════════════════════════════

    def _ensure_panels_expanded(self, driver: WebDriver) -> None:
        """Clicks any collapsed accordion panels so table content is visible."""
        for section_href in ["#collapseOne", "#collapseTwo", "#collapseThree"]:
            try:
                toggle = driver.find_element(By.CSS_SELECTOR, f"a[href='{section_href}']")
                if toggle.get_attribute("aria-expanded") in ("false", None, ""):
                    driver.execute_script("arguments[0].click();", toggle)
                    self.logger.debug(f"Expanded panel: {section_href}")
            except NoSuchElementException:
                self.logger.debug(f"Panel toggle not found: {section_href} — skipping.")
            except Exception as ex:
                self.logger.debug(f"Could not expand {section_href}: {ex}")

    def _extract_bid_id(self, driver: WebDriver) -> str:
        """Extracts bid ID from page header with multi-strategy fallback."""
        candidates = [
            "//div[contains(@class, 'block_bid_no')]//span/b",
            "//a[contains(@href, 'collapseOne')]",
            "//h4[contains(@class,'panel-title')]//a",
        ]
        for xpath in candidates:
            try:
                el = driver.find_element(By.XPATH, xpath)
                text = (el.text or el.get_attribute("textContent") or "").strip()
                match = re.search(r"GEM/\d{4}/[A-Z]/\d+", text)
                if match:
                    return match.group(0)
            except NoSuchElementException:
                continue
        return "N/A"

    def _extract_bid_status(self, driver: WebDriver) -> str:
        """Extracts bid status from the Bid Details panel."""
        try:
            el = driver.find_element(
                By.XPATH,
                "//strong[contains(text(),'Bid Status')]/following-sibling::span"
            )
            return (el.text or "").strip() or "N/A"
        except NoSuchElementException:
            return "N/A"

    # ══════════════════════════════════════════════════════════════════════════
    # PRIVATE — DYNAMIC TABLE PARSING
    # ══════════════════════════════════════════════════════════════════════════

    def _parse_table_section(
        self,
        driver: WebDriver,
        section_id: str,
        col_synonyms: Dict[str, List[str]],
    ) -> Tuple[Dict[str, int], List[List[str]]]:
        """
        Parses an evaluation table section.
        Returns (col_index_map, data_rows) where col_index_map maps
        semantic field names → actual column index in the DOM table.
        """
        try:
            # Locate header row
            header_cells = driver.find_elements(
                By.XPATH,
                f"//div[@id='{section_id}']//table//th"
            )
            if not header_cells:
                # Some tables use <td> for headers in thead
                header_cells = driver.find_elements(
                    By.XPATH,
                    f"//div[@id='{section_id}']//table//thead//td"
                )

            headers = [c.text.strip().lower() for c in header_cells]
            self.logger.debug(f"[{section_id}] Raw headers: {headers}")

            col_map = self._map_columns(headers, col_synonyms)
            self.logger.debug(f"[{section_id}] Column map: {col_map}")

            # Extract all data rows
            row_elements = driver.find_elements(
                By.XPATH,
                f"//div[@id='{section_id}']//table/tbody/tr"
            )
            data_rows: List[List[str]] = []
            for row_el in row_elements:
                cells = row_el.find_elements(By.TAG_NAME, "td")
                row_text = [c.text.strip() for c in cells]
                if any(row_text):   # skip fully empty rows
                    data_rows.append(row_text)

            self.logger.info(
                f"[{section_id}] Parsed {len(data_rows)} data rows with "
                f"{len(col_map)} mapped columns."
            )
            return col_map, data_rows

        except Exception as e:
            self.logger.warning(f"[{section_id}] Table parse failed: {e}")
            return {}, []

    def _map_columns(
        self,
        headers: List[str],
        synonyms: Dict[str, List[str]]
    ) -> Dict[str, int]:
        """
        Dynamically maps semantic field names to their column index
        by matching header text against synonym lists.
        Unknown columns are safely ignored.
        """
        col_map: Dict[str, int] = {}
        for idx, header in enumerate(headers):
            header_clean = header.lower().strip()
            for field_name, field_synonyms in synonyms.items():
                if field_name in col_map:
                    continue  # already mapped
                if any(syn in header_clean for syn in field_synonyms):
                    col_map[field_name] = idx
                    break
        return col_map

    def _safe_cell(
        self, row: List[str], col_map: Dict[str, int], field: str, default: str = "N/A"
    ) -> str:
        """Safely retrieves a cell value by semantic field name."""
        idx = col_map.get(field)
        if idx is None or idx >= len(row):
            return default
        val = row[idx].strip()
        return val if val else default

    def _clean_price(self, raw: str) -> float:
        """Strips currency symbols, commas, and whitespace then casts to float."""
        cleaned = re.sub(r"[₹`\$£€,\s]", "", raw)
        cleaned = cleaned.replace("Rs.", "").replace("INR", "").strip()
        try:
            return round(float(cleaned), 2)
        except ValueError:
            return 0.0

    # ══════════════════════════════════════════════════════════════════════════
    # PRIVATE — RECORD BUILDERS
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tech_records(
        self,
        rows: List[List[str]],
        col_map: Dict[str, int]
    ) -> List[Dict[str, Any]]:
        """Converts raw technical-evaluation table rows into structured dicts."""
        records: List[Dict[str, Any]] = []
        for row in rows:
            try:
                name = self._safe_cell(row, col_map, "seller_name")
                if name in ("N/A", ""):
                    continue
                # First cell of the row often contains s_no even without a header
                name = name.split("\n")[0].strip()
                status_raw = self._safe_cell(row, col_map, "tech_status", "N/A")
                qualified = "qualified" in status_raw.lower()
                records.append({
                    "seller_name":      name,
                    "participated_on":  self._safe_cell(row, col_map, "participated_on"),
                    "mse_mii_status":   self._safe_cell(row, col_map, "mse_mii_status"),
                    "tech_status_raw":  status_raw,
                    "technically_qualified": qualified,
                })
            except Exception as ex:
                self.logger.debug(f"Tech row parse error: {ex}")
        return records

    def _build_fin_records(
        self,
        rows: List[List[str]],
        col_map: Dict[str, int]
    ) -> List[Dict[str, Any]]:
        """Converts raw financial-evaluation table rows into structured dicts."""
        records: List[Dict[str, Any]] = []
        for row in rows:
            try:
                name = self._safe_cell(row, col_map, "seller_name")
                if name in ("N/A", ""):
                    continue
                name = name.split("\n")[0].strip()
                price_raw = self._safe_cell(row, col_map, "quoted_price", "0")
                rank_raw  = self._safe_cell(row, col_map, "rank", "N/A")
                rank      = rank_raw.split("\n")[0].strip()
                records.append({
                    "seller_name":   name,
                    "offered_item":  self._safe_cell(row, col_map, "offered_item"),
                    "quoted_price":  self._clean_price(price_raw),
                    "rank":          rank,
                })
            except Exception as ex:
                self.logger.debug(f"Financial row parse error: {ex}")
        return records

    # ══════════════════════════════════════════════════════════════════════════
    # PRIVATE — MERGE & INTELLIGENCE LAYER
    # ══════════════════════════════════════════════════════════════════════════

    def _merge_evaluations(
        self,
        bid_id: str,
        bid_status: str,
        tech_records: List[Dict[str, Any]],
        fin_records: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Merges technical and financial evaluation data into VendorDetail dicts.
        Uses seller_name as the join key (case-insensitive).
        """
        # Build lookup from tech records
        tech_by_name: Dict[str, Dict[str, Any]] = {
            r["seller_name"].lower(): r for r in tech_records
        }

        vendor_records: List[Dict[str, Any]] = []

        # Determine L1 vendor for awarded_flag
        l1_name = ""
        for fr in fin_records:
            if fr["rank"] == "L1":
                l1_name = fr["seller_name"].lower()
                break

        for fr in fin_records:
            name_lower = fr["seller_name"].lower()
            tech = tech_by_name.get(name_lower, {})

            vendor = VendorDetail(
                bid_id                = bid_id,
                vendor_name           = fr["seller_name"],
                vendor_rank           = fr["rank"],
                quoted_price          = fr["quoted_price"],
                technically_qualified = tech.get("technically_qualified", False),
                financially_qualified = True,   # if in fin table, cleared fin round
                bid_status            = bid_status,
                remarks               = tech.get("tech_status_raw", "N/A"),
                evaluation_round      = "Both" if tech else "Financial",
                awarded_flag          = (name_lower == l1_name),
            )
            vendor_records.append(vendor.to_dict())

        # Append tech-only vendors (disqualified before financial round)
        fin_names = {fr["seller_name"].lower() for fr in fin_records}
        for tr in tech_records:
            if tr["seller_name"].lower() not in fin_names:
                vendor = VendorDetail(
                    bid_id                = bid_id,
                    vendor_name           = tr["seller_name"],
                    vendor_rank           = "N/A",
                    quoted_price          = 0.0,
                    technically_qualified = tr.get("technically_qualified", False),
                    financially_qualified = False,
                    bid_status            = bid_status,
                    remarks               = tr.get("tech_status_raw", "N/A"),
                    evaluation_round      = "Technical",
                    awarded_flag          = False,
                )
                vendor_records.append(vendor.to_dict())

        self.logger.info(
            f"Merged {len(vendor_records)} VendorDetail records "
            f"({len(fin_records)} fin + {len(tech_records) - len(fin_names.intersection({t['seller_name'].lower() for t in tech_records}))} tech-only)."
        )
        return vendor_records

    # ══════════════════════════════════════════════════════════════════════════
    # PRIVATE — PRICING ANALYTICS
    # ══════════════════════════════════════════════════════════════════════════

    def _compute_pricing_analytics(
        self, vendor_records: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Computes pricing competition analytics from all financially-qualified records.

        Returns:
            l1_price          — lowest quoted price
            l2_price          — second-lowest quoted price
            l1_vs_l2_diff     — absolute gap between L1 and L2
            l1_vs_l2_pct      — percentage gap L1→L2
            avg_quote         — mean quoted price
            max_quote         — highest quote
            min_quote         — lowest quote (== l1_price)
            price_spread_pct  — (max - min) / min * 100
            vendor_count      — total financially-qualified vendors
        """
        prices = [
            r["quoted_price"]
            for r in vendor_records
            if r["financially_qualified"] and r["quoted_price"] > 0
        ]

        if not prices:
            return {
                "l1_price": 0.0, "l2_price": 0.0,
                "l1_vs_l2_diff": 0.0, "l1_vs_l2_pct": 0.0,
                "avg_quote": 0.0, "max_quote": 0.0, "min_quote": 0.0,
                "price_spread_pct": 0.0, "vendor_count": 0,
            }

        sorted_prices = sorted(prices)
        l1 = sorted_prices[0]
        l2 = sorted_prices[1] if len(sorted_prices) > 1 else l1
        avg = round(sum(prices) / len(prices), 2)
        mx  = sorted_prices[-1]
        spread = round((mx - l1) / l1 * 100, 2) if l1 > 0 else 0.0
        l1_l2_diff = round(l2 - l1, 2)
        l1_l2_pct  = round((l2 - l1) / l1 * 100, 2) if l1 > 0 else 0.0

        analytics = {
            "l1_price":         round(l1, 2),
            "l2_price":         round(l2, 2),
            "l1_vs_l2_diff":    l1_l2_diff,
            "l1_vs_l2_pct":     l1_l2_pct,
            "avg_quote":        avg,
            "max_quote":        round(mx, 2),
            "min_quote":        round(l1, 2),
            "price_spread_pct": spread,
            "vendor_count":     len(prices),
        }
        self.logger.info(
            f"Pricing analytics — L1: {l1}, L2: {l2}, Spread: {spread}%, "
            f"Avg: {avg}, Vendors: {len(prices)}"
        )
        return analytics

    # ══════════════════════════════════════════════════════════════════════════
    # PRIVATE — ANOMALY DETECTION
    # ══════════════════════════════════════════════════════════════════════════

    def _detect_anomalies(
        self,
        vendor_records: List[Dict[str, Any]],
        analytics: Dict[str, Any],
    ) -> Dict[str, bool]:
        """
        Detects procurement anomaly conditions across the vendor set.

        Flags:
            anomaly_single_vendor     — only 1 vendor participated
            anomaly_duplicate_price   — two or more vendors quoted identical prices
            anomaly_missing_rank      — L1 vendor cannot be identified
            anomaly_abnormal_spread   — price spread exceeds threshold
            anomaly_low_participation — fewer than N vendors participated
        """
        flags: Dict[str, bool] = {
            "anomaly_single_vendor":     False,
            "anomaly_duplicate_price":   False,
            "anomaly_missing_rank":      False,
            "anomaly_abnormal_spread":   False,
            "anomaly_low_participation": False,
        }

        vendor_count = analytics.get("vendor_count", 0)

        # Single vendor
        if vendor_count == 1:
            flags["anomaly_single_vendor"] = True
            self.logger.warning("ANOMALY: Single-vendor bid detected.")

        # Low participation
        if 0 < vendor_count < _LOW_PARTICIPATION_THRESHOLD:
            flags["anomaly_low_participation"] = True
            self.logger.warning(
                f"ANOMALY: Low participation — only {vendor_count} vendor(s)."
            )

        # Duplicate prices
        prices = [
            r["quoted_price"]
            for r in vendor_records
            if r["financially_qualified"] and r["quoted_price"] > 0
        ]
        if len(prices) != len(set(prices)):
            flags["anomaly_duplicate_price"] = True
            self.logger.warning("ANOMALY: Duplicate quoted prices detected.")

        # Missing L1 rank
        ranked_vendors = [r for r in vendor_records if r["vendor_rank"] == "L1"]
        if vendor_count > 0 and not ranked_vendors:
            flags["anomaly_missing_rank"] = True
            self.logger.warning("ANOMALY: No L1 rank identified in financial evaluation.")

        # Abnormal spread
        spread = analytics.get("price_spread_pct", 0.0)
        if spread > _ABNORMAL_SPREAD_THRESHOLD_PCT:
            flags["anomaly_abnormal_spread"] = True
            self.logger.warning(
                f"ANOMALY: Abnormal price spread detected — {spread:.1f}% "
                f"(threshold: {_ABNORMAL_SPREAD_THRESHOLD_PCT}%)."
            )

        detected = [k for k, v in flags.items() if v]
        if detected:
            self.logger.warning(f"Total anomalies detected: {len(detected)} — {detected}")
        else:
            self.logger.info("No procurement anomalies detected.")

        return flags
