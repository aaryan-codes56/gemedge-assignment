import time
import json
from typing import Dict, List, Tuple, Optional, Any
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    TimeoutException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
    ElementNotInteractableException
)

from src.core.base import BaseScraper
from src.config import BASE_URL, TIMEOUTS, GeMSelectors, get_selector_fallback, DEVELOPER_MODE
from src.core.wait_utils import wait_for_element_presence, wait_for_visibility, wait_for_clickable
from src.core.retry_utils import retry
from src.core.error_handler import (
    ErrorHandler,
    ScraperNavigationException,
    ScraperTimeoutException,
    ScraperExtractionException,
    ScraperStaleElementException
)
from src.core.state_manager import StateManager
from src.core.schema_validator import SchemaValidator
from src.utils.metrics import MetricsTracker
from src.utils.dom_debug import DOMDebugger


class GemPortalScraper(BaseScraper):
    """
    Enterprise-grade Selenium scraping workflow targeting the Government e-Marketplace (GeM) Bids Portal.
    Orchestrates robust portal navigation, explicit waits, fallback selector mappings,
    stale element recovery, paginated listing extraction, and safe incremental file persistence.
    """

    def __init__(self, driver: WebDriver) -> None:
        super().__init__(driver)
        self.metrics = MetricsTracker()
        self.state_manager = StateManager()
        self.schema_validator = SchemaValidator()
        self.explicit_timeout = TIMEOUTS.get("EXPLICIT_WAIT", 15.0)

    # ==================================================
    # LIFECYCLE BASE IMPLEMENTATION
    # ==================================================

    def start(self) -> None:
        """
        BaseScraper requirement: Runs initialization and boot validation.
        """
        self.initialize()

    def navigate_to_target(self, url: str) -> None:
        """
        BaseScraper requirement: Navigates the browser instance to target GeM portal.
        """
        self.open_portal(url)

    def scrape_data(self, max_pages: int = 3) -> List[Dict[str, Any]]:
        """
        BaseScraper requirement: Applies filters, traverses paginated records,
        opens detailed results tabs safely, parses deep metrics, and saves outputs.
        """
        self.logger.info("Executing scrape_data: Orchestrating filter application...")
        self.apply_status_filter()
        self.apply_outcome_filter()
        
        # Verify correctness
        if not self.validate_filter_state():
            raise ScraperExtractionException("Scraper Verification: Filters failed to apply correctly.")
            
        self.capture_success_artifacts()

        # Instantiate Extractors
        from src.extractor.listing_extractor import ListingExtractor
        from src.extractor.bid_detail_extractor import BidDetailExtractor
        from src.extractor.vendor_evaluation_extractor import VendorEvaluationExtractor

        listing_extractor = ListingExtractor()
        detail_extractor  = BidDetailExtractor()
        vendor_extractor  = VendorEvaluationExtractor()

        # Load State Checkpoint to verify starting page index
        self.state_manager.load_state()
        resume_page = self.state_manager.get_last_completed_page()
        self.logger.info(f"Initiated paginated listing extraction. Resume completed page index: {resume_page}")

        pages_scraped_this_run = 0
        all_extracted_records: List[Dict[str, Any]] = []

        while True:
            # 1. Inspect current visual page number
            current_page = self.get_current_page_number()
            self.logger.info(f"==================================================")
            self.logger.info(f"   PROCESSING LISTING PAGE: {current_page} (Active Run: {pages_scraped_this_run + 1}/{max_pages})")
            self.logger.info(f"==================================================")

            # 2. Check if page was already fully parsed in a previous run
            if current_page <= resume_page:
                self.logger.info(f"Page {current_page} already completed in previous run. Skipping extraction.")
                # Advance next
                if not self.click_next_page(current_page):
                    self.logger.info("Reached end of paginated listings during skip advance.")
                    break
                continue

            # 3. Locate dynamic listing cards
            cards = self.find_elements_with_fallback(GeMSelectors.LISTING_TABLE, "bid_blocks")
            if not cards:
                self.logger.warning(f"No bid cards resolved on page {current_page} DOM. Checking loader state...")
                self.wait_for_loader_to_disappear()
                time.sleep(1.0)
                cards = self.find_elements_with_fallback(GeMSelectors.LISTING_TABLE, "bid_blocks")
                if not cards:
                    self.logger.error(f"Page {current_page} lacks valid bid cards. Capturing page diagnostics.")
                    self.capture_failure_diagnostics(f"empty_page_{current_page}")
                    raise ScraperExtractionException(f"Zero listing cards matched on active page {current_page}.")

            # 4. Process cards, extracting listings and switching to detail tabs
            self.logger.info(f"Found {len(cards)} raw listing cards on page {current_page}. Extracting...")
            page_unique_listings    = []
            page_detailed_results   = []
            page_vendor_evaluations = []
            page_duplicates         = 0

            for idx, card in enumerate(cards):
                try:
                    # Parse basic listing attributes
                    rec = listing_extractor.extract_item(card)
                    if not rec:
                        self.logger.warning(f"Card [{idx + 1}/{len(cards)}]: Empty extraction result. Skipping.")
                        continue

                    bid_id = rec["bid_id"]

                    # Deduplication check via state manager
                    if self.state_manager.is_bid_completed(bid_id):
                        page_duplicates += 1
                        continue

                    self.logger.info(f"Processing new bid [{idx + 1}/{len(cards)}]: {bid_id}")

                    # Multi-Tab detail page switching flow
                    results_btn = None
                    try:
                        results_btn = card.find_element(
                            By.XPATH,
                            ".//a[contains(@href, 'getBidResultView') or contains(@href, 'getSinglePacketResultView')]"
                        )
                    except NoSuchElementException:
                        pass

                    if results_btn:
                        parent_handle = self.driver.current_window_handle
                        self.logger.info(f"Opening detailed result page for {bid_id} in a new tab...")
                        try:
                            # Safely click results button
                            self.robust_click(results_btn)
                            time.sleep(3.0)

                            # Locate and switch to the new window handle
                            detail_tab_opened = False
                            for handle in self.driver.window_handles:
                                if handle != parent_handle:
                                    self.driver.switch_to.window(handle)
                                    detail_tab_opened = True
                                    break

                            if detail_tab_opened:
                                self.logger.info(f"Active detail tab URL: {self.driver.current_url}")

                                # ── BidDetailExtractor ───────────────────────────────────
                                detail_record = detail_extractor.extract_item(self.driver)
                                if detail_record and detail_extractor.validate(detail_record):
                                    page_detailed_results.append(detail_record)
                                    self.logger.info(f"BidDetail extracted for {bid_id}.")
                                else:
                                    self.logger.warning(f"BidDetail empty/invalid for {bid_id}.")

                                # ── VendorEvaluationExtractor ────────────────────────────
                                try:
                                    eval_result = vendor_extractor.extract_item(self.driver)
                                    if eval_result and eval_result.get("vendor_records"):
                                        vendor_rows   = eval_result["vendor_records"]
                                        anomaly_flags = eval_result.get("anomaly_flags", {})
                                        valid_rows = []
                                        for vrow in vendor_rows:
                                            if vendor_extractor.validate(vrow):
                                                valid_rows.append(vrow)
                                            else:
                                                self.metrics.increment_malformed(1)
                                        if valid_rows:
                                            page_vendor_evaluations.extend(valid_rows)
                                            self.metrics.increment_vendor_rows(len(valid_rows))
                                        active_anomalies = sum(1 for v in anomaly_flags.values() if v)
                                        if active_anomalies:
                                            self.metrics.increment_anomalies(active_anomalies)
                                        self.logger.info(
                                            f"Vendor eval: {len(valid_rows)} valid rows, "
                                            f"{active_anomalies} anomaly flags for {bid_id}."
                                        )
                                    else:
                                        self.logger.warning(f"Vendor eval yielded no rows for {bid_id}.")
                                except Exception as ve_err:
                                    self.logger.error(f"VendorEvaluation error for {bid_id}: {ve_err}")
                                    self.metrics.increment_malformed(1)

                                # Close detail tab
                                self.driver.close()
                            else:
                                self.logger.warning(f"Could not open detail results tab for {bid_id}.")
                        except Exception as detail_err:
                            self.logger.error(f"Error during deep detail extraction for {bid_id}: {detail_err}")
                            self.metrics.increment_failures(1)
                            # Cleanup open window handles
                            for handle in self.driver.window_handles:
                                if handle != parent_handle:
                                    self.driver.switch_to.window(handle)
                                    self.driver.close()
                        finally:
                            # Re-focus parent tab
                            self.driver.switch_to.window(parent_handle)
                            time.sleep(1.0) # Layout stabilization wait

                    # Save and track completed listing
                    page_unique_listings.append(rec)
                    self.state_manager.completed_bid_ids.add(bid_id)

                except StaleElementReferenceException:
                    self.logger.warning(f"Listing card index {idx + 1} became stale during page processing. Skipping.")
                    continue
                except Exception as e:
                    self.logger.error(f"Error parsing card index {idx + 1}: {e}")
                    continue

            # Update duplicate counts
            if page_duplicates > 0:
                self.logger.info(f"Deduplication: Skipped {page_duplicates} duplicate records already parsed.")
                self.metrics.increment_duplicates(page_duplicates)

            # 5. Persist listings, results, and vendor evaluations incrementally
            if page_unique_listings:
                self.persist_records_incrementally(page_unique_listings)
                all_extracted_records.extend(page_unique_listings)
                self.metrics.increment_bids(len(page_unique_listings))

            if page_detailed_results:
                self.persist_results_incrementally(page_detailed_results)

            if page_vendor_evaluations:
                self.persist_evaluations_incrementally(page_vendor_evaluations)

            # 6. Save page checkpoint to disk
            self.state_manager.save_state(current_page)
            self.logger.info(f"Page {current_page} progress checkpoint successfully saved to disk.")

            # 7. Update run session telemetries
            self.metrics.increment_pages(1)
            pages_scraped_this_run += 1

            # Assert limits checking
            if pages_scraped_this_run >= max_pages:
                self.logger.info(f"Scrape limit reached: completed requested run batch of {max_pages} pages.")
                break

            # 8. Click Next page to continue traversal
            if not self.click_next_page(current_page):
                self.logger.info("Reached final listing page of Government e-Marketplace portal.")
                break

        return all_extracted_records

    def validate(self) -> bool:
        """
        BaseScraper requirement: Asserts page DOM readiness and filters visibility.
        """
        try:
            self.validate_page_load()
            return True
        except Exception as e:
            self.logger.error(f"Scraper validation checks failed: {e}")
            return False

    # ==================================================
    # PORTAL SCRApER DOM INTERACTION METHODS
    # ==================================================

    def initialize(self) -> None:
        """
        Bootstraps telemetries, cleans old runs state, and verifies settings configuration.
        """
        self.logger.info("Initializing GeM Portal Scraper and synchronizing state.")
        self.metrics.reset()
        self.state_manager.load_state()
        self.schema_validator.reset()

    def open_portal(self, url: Optional[str] = None) -> None:
        """
        Safely loads the target portal address, tracking duration via MetricsTracker.
        """
        target_url = url if url else BASE_URL
        self.logger.info(f"Opening GeM Bids Portal: {target_url}")
        
        start_time = time.time()
        try:
            self.driver.get(target_url)
            # Track page load telemetry duration
            duration = time.time() - start_time
            self.logger.info(f"GeM Portal homepage loaded in {duration:.2f} seconds.")
            
            # Run page readiness checks
            self.validate_page_load()
            self.metrics.increment_pages(1)
            
        except Exception as e:
            self.logger.error(f"Failed to navigate to target portal homepage: {e}")
            # Diagnostic capture on loading failures
            self.capture_failure_diagnostics("open_portal_failure")
            raise ScraperNavigationException(
                message=f"GeM portal homepage loading was unsuccessful for: {target_url}",
                details=str(e)
            ) from e

    def validate_page_load(self) -> None:
        """
        Verifies standard landing DOM parameters (Logo presence, Title correctness, Table existence).
        """
        self.logger.info("Executing comprehensive page load validation checks...")
        
        # 1. Page Title Verification
        title = self.driver.title
        if "GeM" not in title and "Bid" not in title:
            self.logger.warning(f"Unexpected page title encountered: '{title}'")
            
        # 2. Check for Logo Presence with fallbacks
        logo_el = self.find_element_with_fallback(GeMSelectors.LANDING, "logo")
        if not logo_el.is_displayed():
            self.logger.warning("Portal brand logo resolved in DOM but is currently invisible.")
            
        # 3. Check for Listing Table or Bid Blocks presence
        table_container = self.find_element_with_fallback(GeMSelectors.FILTERS, "filter_container")
        if not table_container:
            raise ScraperExtractionException("Scraper Validation: Key Filter navigation container is missing.")

        self.logger.info("Page load validation check complete: DOM structure is READY.")

    @retry(max_attempts=3, delay=2.0, exceptions=(StaleElementReferenceException, TimeoutException))
    def apply_status_filter(self) -> None:
        """
        Applies the 'By Bid/RA Status' category filter robustly.
        Uses explicit wait, Javascript fallbacks, and automatic stale element retries.
        """
        self.logger.info("Applying Status filter: 'By Bid/RA Status'...")
        start_time = time.time()
        
        try:
            # 1. Locate the Status input checkbox using fallback strategy
            checkbox = self.find_element_with_fallback(GeMSelectors.FILTERS, "status_bid_ra_checkbox")
            
            # 2. Assert and apply check trigger
            if not self.is_checkbox_selected(checkbox, "status_bid_ra_checkbox"):
                self.logger.info("Status 'Bid/RA' is not active. Clicking status checkbox...")
                self.robust_click(checkbox)
                
                # Wait for any loader/spinner to complete and let DOM update
                self.wait_for_loader_to_disappear()
                time.sleep(1.0) # Graceful DOM layout stabilization
            else:
                self.logger.info("Status 'Bid/RA' filter checkbox is already selected.")
                
            self.logger.info(f"Status filter applied successfully in {time.time() - start_time:.2f}s.")
            
        except Exception as e:
            self.metrics.increment_failures(1)
            self.capture_failure_diagnostics("status_filter_error")
            raise ScraperExtractionException(
                message="Error applying Portal Status 'Bid/RA' filter",
                details=str(e)
            ) from e

    @retry(max_attempts=3, delay=2.0, exceptions=(StaleElementReferenceException, TimeoutException))
    def apply_outcome_filter(self) -> None:
        """
        Applies the 'Bid /RA Awarded' outcome sub-filter category.
        """
        self.logger.info("Applying Outcome filter: 'Bid /RA Awarded'...")
        start_time = time.time()
        
        try:
            # 1. Locate outcome checkbox
            checkbox = self.find_element_with_fallback(GeMSelectors.FILTERS, "outcome_awarded_checkbox")
            
            # 2. Check and click
            if not self.is_checkbox_selected(checkbox, "outcome_awarded_checkbox"):
                self.logger.info("Outcome 'Awarded' is not active. Clicking outcome checkbox...")
                self.robust_click(checkbox)
                
                # Wait for dynamic query spinner loader
                self.wait_for_loader_to_disappear()
                time.sleep(1.0)
            else:
                self.logger.info("Outcome 'Awarded' filter checkbox is already selected.")

            self.logger.info(f"Outcome filter applied successfully in {time.time() - start_time:.2f}s.")
            
        except Exception as e:
            self.metrics.increment_failures(1)
            self.capture_failure_diagnostics("outcome_filter_error")
            raise ScraperExtractionException(
                message="Error applying Portal Outcome 'Bid /RA Awarded' filter",
                details=str(e)
            ) from e

    def validate_filter_state(self) -> bool:
        """
        Verifies that both Status and Outcome checkboxes are actively selected in the DOM.
        """
        self.logger.info("Verifying active filter checkboxes selection states...")
        try:
            status_box = self.find_element_with_fallback(GeMSelectors.FILTERS, "status_bid_ra_checkbox")
            outcome_box = self.find_element_with_fallback(GeMSelectors.FILTERS, "outcome_awarded_checkbox")
            
            status_ok = self.is_checkbox_selected(status_box, "status_bid_ra_checkbox")
            outcome_ok = self.is_checkbox_selected(outcome_box, "outcome_awarded_checkbox")
            
            self.logger.info(f"Filter State Validation: Status Checked={status_ok}, Outcome Checked={outcome_ok}")
            return status_ok and outcome_ok
            
        except Exception as e:
            self.logger.error(f"Failed to inspect active filter checkbox selection states: {e}")
            return False

    def capture_success_artifacts(self) -> None:
        """
        Saves visual proof of successful filter execution.
        """
        self.logger.info("Workflow completed. Saving verification artifacts...")
        path = ErrorHandler.capture_diagnostic_screenshot(self.driver, prefix="filter_success")
        if path:
            self.metrics.increment_screenshots(1)
            self.logger.info(f"Verification success artifact stored at: {path}")

        if DEVELOPER_MODE:
            DOMDebugger.dump_page_source(self.driver, prefix="filter_success_dom")

    def shutdown(self) -> None:
        """
        Safely shuts down the active WebDriver session.
        """
        self.logger.info("Terminating scraper session and releasing web browser...")
        if self.driver is not None:
            try:
                self.driver.quit()
                self.logger.info("Scraper session shutdown completed safely.")
            except Exception as e:
                self.logger.warning(f"Error encountered during driver quit: {e}")

    # ==================================================
    # PRIVATE PAGINATION & INCREMENTAL PERSISTENCE METHODS
    # ==================================================

    def get_current_page_number(self) -> int:
        """Reads the active page number from the pagination bar defensively."""
        locators = GeMSelectors.PAGINATION["active_page"]
        for loc in locators:
            try:
                elements = self.driver.find_elements(*loc)
                if elements and elements[0].is_displayed():
                    txt = elements[0].text.strip()
                    num_txt = "".join(ch for ch in txt if ch.isdigit())
                    if num_txt:
                        return int(num_txt)
            except Exception:
                continue
        return 1

    def click_next_page(self, current_page: int) -> bool:
        """
        Attempts to click the next page button and verifies page transition has completed.
        Returns True if successful, False if last page is reached or transition fails.
        """
        next_btn = None
        locators = GeMSelectors.PAGINATION["next_button"]
        
        for loc in locators:
            try:
                elements = self.driver.find_elements(*loc)
                if elements and elements[0].is_displayed():
                    # Check for parent disables or direct disabled classes
                    parent_class = ""
                    try:
                        parent = elements[0].find_element(By.XPATH, "./..")
                        parent_class = parent.get_attribute("class") or ""
                    except Exception:
                        pass
                    
                    btn_class = elements[0].get_attribute("class") or ""
                    if "disabled" in btn_class or "disabled" in parent_class:
                        self.logger.info("Next page button exists but is disabled (last page reached).")
                        return False
                        
                    next_btn = elements[0]
                    break
            except Exception:
                continue

        if not next_btn:
            self.logger.info("Next page button was not found in the DOM (last page reached).")
            return False

        # Attempt safe robust click sequence with transitions validation
        max_clicks = 3
        for attempt in range(max_clicks):
            try:
                self.logger.info(f"Clicking next page button (Attempt {attempt + 1}/{max_clicks})...")
                self.robust_click(next_btn)
                self.wait_for_loader_to_disappear()
                time.sleep(1.5) # Dynamic DOM repaint buffer

                # Assert page validation
                new_page = self.get_current_page_number()
                if new_page > current_page:
                    self.logger.info(f"Page transition successful: advanced from page {current_page} to page {new_page}.")
                    return True
                else:
                    self.logger.warning(f"Page number did not advance (remained at {new_page}). Retrying next-click...")
                    self.metrics.increment_retries(1)
            except Exception as e:
                self.logger.error(f"Error during next page click attempt: {e}")
                self.metrics.increment_retries(1)
                time.sleep(2.0)

        self.logger.error("Page transition validation failed: maximum click attempts exhausted.")
        self.capture_failure_diagnostics(f"pagination_failure_page_{current_page}")
        return False

    def persist_records_incrementally(self, new_records: List[Dict[str, Any]]) -> None:
        """
        Saves extracted records incrementally to raw JSON and CSV output paths.
        Saves under 'data/raw' as configured in central settings.
        """
        if not new_records:
            return

        from src.utils.file_utils import save_json, save_csv

        data_dir = self.state_manager.state_dir
        json_path = data_dir / "bid_listings.json"
        csv_path = data_dir / "bid_listings.csv"

        # Load existing json records
        existing_records = []
        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    existing_records = json.load(f)
            except Exception as e:
                self.logger.warning(f"Could not load pre-existing JSON at {json_path}: {e}. Creating new array.")
        
        # Merge & deduplicate
        seen_ids = {r["bid_id"] for r in existing_records}
        added_count = 0
        for rec in new_records:
            if rec["bid_id"] not in seen_ids:
                existing_records.append(rec)
                seen_ids.add(rec["bid_id"])
                added_count += 1

        if added_count > 0:
            save_json(existing_records, json_path)
            save_csv(existing_records, csv_path)
            self.logger.info(f"Incrementally appended {added_count} new records to {json_path} and {csv_path}.")

    def persist_results_incrementally(self, new_results: List[Dict[str, Any]]) -> None:
        """
        Saves detailed bid results incrementally to raw JSON and CSV output paths.
        Saves under 'data/raw' as configured in central settings.
        """
        if not new_results:
            return

        from src.utils.file_utils import save_json, save_csv

        data_dir = self.state_manager.state_dir
        json_path = data_dir / "bid_results.json"
        csv_path = data_dir / "bid_results.csv"

        # Load existing json records
        existing_records = []
        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    existing_records = json.load(f)
            except Exception as e:
                self.logger.warning(f"Could not load pre-existing JSON at {json_path}: {e}. Creating new array.")
        
        # Merge & deduplicate
        seen_ids = {r["bid_id"] for r in existing_records}
        added_count = 0
        for rec in new_results:
            if rec["bid_id"] not in seen_ids:
                existing_records.append(rec)
                seen_ids.add(rec["bid_id"])
                added_count += 1

        if added_count > 0:
            save_json(existing_records, json_path)
            save_csv(existing_records, csv_path)
            self.logger.info(f"Incrementally appended {added_count} new detailed results to {json_path} and {csv_path}.")

    def persist_evaluations_incrementally(self, new_evaluations: List[Dict[str, Any]]) -> None:
        """
        Saves vendor evaluation rows incrementally to vendor_evaluations.json and .csv.
        Deduplicates on composite key (bid_id, vendor_name) to prevent double-writing.
        """
        if not new_evaluations:
            return

        from src.utils.file_utils import save_json, save_csv

        data_dir  = self.state_manager.state_dir
        json_path = data_dir / "vendor_evaluations.json"
        csv_path  = data_dir / "vendor_evaluations.csv"

        # Load existing records
        existing_records: List[Dict[str, Any]] = []
        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    existing_records = json.load(f)
            except Exception as e:
                self.logger.warning(f"Could not load {json_path}: {e}. Starting fresh.")

        # Deduplicate on (bid_id, vendor_name) composite key
        seen_keys = {
            (r["bid_id"], r["vendor_name"])
            for r in existing_records
        }
        added_count = 0
        for rec in new_evaluations:
            key = (rec.get("bid_id", ""), rec.get("vendor_name", ""))
            if key not in seen_keys:
                existing_records.append(rec)
                seen_keys.add(key)
                added_count += 1

        if added_count > 0:
            save_json(existing_records, json_path)
            save_csv(existing_records, csv_path)
            self.logger.info(
                f"Incrementally appended {added_count} vendor evaluation rows "
                f"to {json_path} and {csv_path}."
            )

    # ==================================================
    # PRIVATE ROBUST SELENIUM UTILITY HELPERS
    # ==================================================

    def find_element_with_fallback(
        self,
        category_map: Dict[str, List[Tuple[str, str]]],
        key: str
    ) -> WebElement:
        """
        Finds an element by trying the list of fallback selectors sequentially.
        """
        locators = get_selector_fallback(category_map, key)
        if not locators:
            raise ScraperExtractionException(f"Configuration Error: No locators registered under key '{key}'")

        for idx, loc in enumerate(locators):
            try:
                self.logger.debug(f"Attempting locator fallback ({idx + 1}/{len(locators)}): {loc}")
                # Use standard explicit visibility/presence waits
                element = wait_for_element_presence(self.driver, loc, timeout=5.0)
                # Success!
                self.logger.debug(f"Locator succeeded: {loc}")
                return element
            except Exception as e:
                self.logger.debug(f"Locator fallback failed: {loc} | Exception: {type(e).__name__}")
                continue

        # All fallbacks failed
        raise ScraperTimeoutException(
            message=f"Selector Resolution Exhausted: All fallback locators for key '{key}' timed out.",
            details=f"Attempted list: {locators}"
        )

    def find_elements_with_fallback(
        self,
        category_map: Dict[str, List[Tuple[str, str]]],
        key: str
    ) -> List[WebElement]:
        """
        Finds a list of matching WebElements using fallback selectors.
        """
        locators = get_selector_fallback(category_map, key)
        if not locators:
            return []

        for idx, loc in enumerate(locators):
            try:
                self.logger.debug(f"Attempting batch selector fallback ({idx + 1}/{len(locators)}): {loc}")
                elements = self.driver.find_elements(*loc)
                if elements:
                    self.logger.debug(f"Resolved {len(elements)} elements using locator: {loc}")
                    return elements
            except Exception:
                continue
        return []

    def robust_click(self, element: WebElement) -> None:
        """
        Performs a click action on a WebElement.
        If standard Selenium click is intercepted or blocked, uses Javascript click fallback.
        """
        try:
            # 1. Scroll element into active viewport view
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(0.5)
            
            # 2. Try clickability wait
            self.logger.debug("Attempting standard web element click...")
            element.click()
            self.logger.debug("Standard web element click executed successfully.")
        except (ElementClickInterceptedException, ElementNotInteractableException) as e:
            self.logger.warning(
                f"Standard element click intercepted or not interactable: {type(e).__name__}. "
                "Executing Javascript click fallback..."
            )
            self.driver.execute_script("arguments[0].click();", element)
            self.logger.info("Javascript click fallback executed successfully.")
        except StaleElementReferenceException as e:
            self.logger.error("Stale WebElement reference encountered during click execution.")
            raise ScraperStaleElementException(
                message="Stale reference during click execution",
                details=str(e)
            ) from e

    def is_checkbox_selected(self, element: WebElement, key: str) -> bool:
        """
        Detects if a checkbox input is selected.
        Handles nested styled wrappers (like iCheck where class 'checked' is applied to parent div).
        """
        # 1. Direct attribute check
        if element.is_selected():
            return True
            
        checked_attr = element.get_attribute("checked")
        if checked_attr is not None and checked_attr.lower() in ("true", "checked"):
            return True
            
        # 2. Check parent/wrapper elements (jQuery iCheck wrappers)
        try:
            parent = element.find_element(By.XPATH, "./..")
            class_name = parent.get_attribute("class") or ""
            if "checked" in class_name:
                return True
        except Exception:
            pass

        return False

    def wait_for_loader_to_disappear(self) -> None:
        """
        Waits for the dynamic star spinner/loader `div.loader` overlay to fully disappear.
        """
        self.logger.debug("Synchronization check: Waiting for dynamic spinner loader to complete...")
        locators = get_selector_fallback(GeMSelectors.FILTERS, "spinner_loader")
        if not locators:
            return

        from selenium.webdriver.support.wait import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        for loc in locators:
            try:
                # Use short wait to check presence first
                WebDriverWait(self.driver, timeout=2.0).until(EC.presence_of_element_located(loc))
                # Wait for invisibility
                self.logger.info(f"Loader spinner detected in DOM ({loc}). Waiting for loading invisibility...")
                WebDriverWait(self.driver, timeout=self.explicit_timeout).until(EC.invisibility_of_element_located(loc))
                self.logger.debug("Loader spinner has disappeared cleanly.")
                break
            except TimeoutException:
                # Loader might not be active or disappeared rapidly
                continue
            except Exception:
                continue

    def capture_failure_diagnostics(self, prefix: str) -> None:
        """
        Utility to record diagnostics when a method action fails.
        """
        self.logger.error(f"Recording failure diagnostics with prefix: '{prefix}'")
        try:
            path = ErrorHandler.capture_diagnostic_screenshot(self.driver, prefix=prefix)
            if path:
                self.metrics.increment_screenshots(1)
            DOMDebugger.dump_page_source(self.driver, prefix=prefix)
        except Exception as err:
            self.logger.warning(f"Error capturing failure diagnostics trace: {err}")
