from typing import Any, Dict, List, Optional
from urllib.parse import urljoin
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException

from src.core.base import BaseExtractor
from src.core.models import BidListing
from src.core.schema_validator import SchemaValidator
from src.core.error_handler import ScraperExtractionException


class ListingExtractor(BaseExtractor):
    """
    Production-grade DOM parser targeting the GeM Bids Portal tabular listings.
    Extracts structured tender datasets from raw Selenium WebElement cards.
    """

    def __init__(self) -> None:
        super().__init__()
        self.schema_validator = SchemaValidator()

    def extract_item(self, raw_element: WebElement) -> Dict[str, Any]:
        """
        Parses a single raw GeM listing card and extracts a BidListing dictionary representation.
        Enforces defensive try-except captures to support partial/missing fields gracefully.
        """
        try:
            # 1. Extract Bid ID & Bid Link
            bid_id = "N/A"
            bid_link = "N/A"
            try:
                # Find anchor containing the Bid number
                bid_anchor = raw_element.find_element(By.CSS_SELECTOR, "a.bid_no_hover")
                bid_id = bid_anchor.text.strip()
                relative_link = bid_anchor.get_attribute("href") or ""
                bid_link = urljoin("https://bidplus.gem.gov.in", relative_link)
            except NoSuchElementException:
                # Fallback to general anchor lookup
                try:
                    bid_anchor = raw_element.find_element(By.XPATH, ".//a[contains(@href, 'showbidDocument') or contains(@href, 'showBidDocument')]")
                    bid_id = bid_anchor.text.strip()
                    relative_link = bid_anchor.get_attribute("href") or ""
                    bid_link = urljoin("https://bidplus.gem.gov.in", relative_link)
                except NoSuchElementException:
                    pass

            # 2. Extract Items/Category (Complete untruncated popovers support)
            item_category = "N/A"
            try:
                items_el = raw_element.find_element(By.XPATH, ".//strong[contains(text(), 'Items')]/..")
                # Look for anchor tag carrying popover descriptions
                popover_anchors = items_el.find_elements(By.TAG_NAME, "a")
                if popover_anchors:
                    popover_content = popover_anchors[0].get_attribute("data-content")
                    if popover_content:
                        item_category = popover_content.strip()
                    else:
                        item_category = popover_anchors[0].text.strip()
                else:
                    item_category = items_el.text.replace("Items:", "").strip()
            except NoSuchElementException:
                pass

            # 3. Extract Quantity
            quantity = 0
            try:
                qty_el = raw_element.find_element(By.XPATH, ".//strong[contains(text(), 'Quantity')]/..")
                qty_text = qty_el.text.replace("Quantity:", "").strip()
                # Clean up any non-numeric suffixes or formatting
                qty_text = "".join(ch for ch in qty_text if ch.isdigit())
                if qty_text:
                    quantity = int(qty_text)
            except (NoSuchElementException, ValueError):
                pass

            # 4. Extract Department and Buyer Name
            department = "N/A"
            buyer_name = "N/A"
            try:
                # Target the Ministry / Address content in col-md-5 layout
                try:
                    dept_el = raw_element.find_element(By.XPATH, ".//strong[contains(text(), 'Department Name And Address')]/../following-sibling::div")
                    department = dept_el.text.strip().replace("\n", " / ")
                except NoSuchElementException:
                    # Sibling traversal fallback
                    col_5 = raw_element.find_element(By.CSS_SELECTOR, "div.col-md-5")
                    department = col_5.text.replace("Department Name And Address:", "").strip().replace("\n", " / ")
                
                # Derive Buyer Name from address hierarchy
                if department and department != "N/A":
                    parts = [p.strip() for p in department.split("/") if p.strip()]
                    if parts:
                        buyer_name = parts[-1] # Set to specific office unit
            except NoSuchElementException:
                pass

            # 5. Extract Start Date & End Date
            start_date = "N/A"
            end_date = "N/A"
            try:
                start_el = raw_element.find_element(By.CSS_SELECTOR, "span.start_date")
                start_date = start_el.text.strip()
            except NoSuchElementException:
                try:
                    start_el = raw_element.find_element(By.XPATH, ".//span[contains(@class, 'start_date')]")
                    start_date = start_el.text.strip()
                except NoSuchElementException:
                    pass

            try:
                end_el = raw_element.find_element(By.CSS_SELECTOR, "span.end_date")
                end_date = end_el.text.strip()
            except NoSuchElementException:
                try:
                    end_el = raw_element.find_element(By.XPATH, ".//span[contains(@class, 'end_date')]")
                    end_date = end_el.text.strip()
                except NoSuchElementException:
                    pass

            # 6. Extract Status
            bid_status = "N/A"
            try:
                status_el = raw_element.find_element(By.XPATH, ".//p[contains(@class, 'pull-right')]")
                bid_status = status_el.text.replace("Status:", "").strip()
            except NoSuchElementException:
                try:
                    status_el = raw_element.find_element(By.CSS_SELECTOR, "span.text-success")
                    bid_status = status_el.text.strip()
                except NoSuchElementException:
                    pass

            # 7. Extract Bid Value (Default to 0.0 unless specified)
            bid_value = 0.0

            # 8. Construct unified Dataclass Object
            listing = BidListing(
                bid_id=bid_id,
                item_category=item_category,
                department=department,
                buyer_name=buyer_name,
                quantity=quantity,
                bid_value=bid_value,
                start_date=start_date,
                end_date=end_date,
                bid_status=bid_status,
                bid_link=bid_link
            )

            # Return raw dictionary representation populated with SchemaValidator bindings
            return listing.to_dict()

        except StaleElementReferenceException as e:
            self.logger.error("Stale WebElement reference encountered during card extraction.")
            raise ScraperExtractionException(
                message="Stale element encountered during item extraction.",
                details=str(e)
            ) from e
        except Exception as e:
            self.logger.error(f"Unexpected card row parsing anomaly: {e}", exc_info=True)
            return {}

    def extract_batch(self, raw_collection: List[WebElement]) -> List[Dict[str, Any]]:
        """
        Parses a batch collection of raw WebElements, running validation on each.
        """
        self.logger.info(f"Extracting batch of {len(raw_collection)} listing cards...")
        results = []
        
        for idx, el in enumerate(raw_collection):
            try:
                record = self.extract_item(el)
                if not record:
                    self.logger.warning(f"Batch Row [{idx + 1}]: Skipped due to empty extraction results.")
                    continue
                
                # Enforce Schema Validation
                if self.validate(record):
                    results.append(record)
                else:
                    self.logger.warning(f"Batch Row [{idx + 1}]: Failed schema validation rules. Skipping record.")
            except StaleElementReferenceException:
                self.logger.warning(f"Batch Row [{idx + 1}]: Stale reference detected mid-extraction. Skipping row.")
                continue
            except Exception as e:
                self.logger.error(f"Batch Row [{idx + 1}]: Extraction failed unexpectedly. Error: {e}")
                continue

        return results

    def validate(self, extracted_record: Dict[str, Any]) -> bool:
        """
        Runs comprehensive data hygiene validation using SchemaValidator.
        """
        report = self.schema_validator.validate_bid_listing(extracted_record)
        if not report.is_valid:
            self.logger.error(f"Schema Validation Failures: {report.errors}")
            return False
        
        if report.warnings:
            self.logger.warning(f"Schema Validation Warnings: {report.warnings}")
        return True
