import re
from typing import Any, Dict, List, Optional
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException

from src.core.base import BaseExtractor
from src.core.models import BidResult
from src.core.schema_validator import SchemaValidator
from src.core.error_handler import ScraperExtractionException
from src.utils.logger import get_logger


class BidDetailExtractor(BaseExtractor):
    """
    Production-grade detail page DOM parser targeting the GeM Bids Portal detail views.
    Extracts deep procurement results including Technical/Financial evaluation tables.
    """

    def __init__(self) -> None:
        super().__init__()
        self.schema_validator = SchemaValidator()
        self.logger = get_logger("bid_detail_extractor")

    def _extract_text_by_xpath(self, driver: WebDriver, xpath: str, fallback_default: str = "N/A") -> str:
        """Helper to extract text or textContent safely using XPath."""
        try:
            el = driver.find_element(By.XPATH, xpath)
            text = el.text.strip()
            if not text:
                text = el.get_attribute("textContent").strip()
            return text if text else fallback_default
        except NoSuchElementException:
            return fallback_default

    def extract_item(self, driver: WebDriver) -> Dict[str, Any]:
        """
        Parses the active Selenium WebDriver detail page and extracts a BidResult dictionary.
        Enforces defensive tries and custom fallbacks for all fields.
        """
        try:
            # Expand collapsible sections if they are not already open (to ensure visibility)
            for section_id in ["#collapseOne", "#collapseTwo", "#collapseThree"]:
                try:
                    section = driver.find_element(By.CSS_SELECTOR, f"a[href='{section_id}']")
                    aria_expanded = section.get_attribute("aria-expanded")
                    if aria_expanded == "false" or not aria_expanded:
                        self.logger.info(f"Expanding section {section_id} via click...")
                        driver.execute_script("arguments[0].click();", section)
                except Exception as ex:
                    self.logger.debug(f"Could not expand {section_id}: {ex}")

            # 1. Extract Bid ID & Bid Link
            bid_id = "N/A"
            try:
                # Find anchor containing Bid Number in header
                bid_id_text = self._extract_text_by_xpath(
                    driver, "//div[contains(@class, 'block_bid_no')]//span/b"
                )
                if bid_id_text == "N/A":
                    bid_id_text = self._extract_text_by_xpath(
                        driver, "//a[contains(@href, 'collapseOne')]"
                    )
                
                # Match standard GeM ID pattern (GEM/YYYY/[B|R]/xxxxx)
                match = re.search(r"GEM/\d{4}/[A-Z]/\d+", bid_id_text)
                if match:
                    bid_id = match.group(0)
                else:
                    bid_id = bid_id_text.replace("1. BID DETAILS -", "").strip()
            except Exception:
                pass

            # 2. Extract core Bid details
            bid_status = self._extract_text_by_xpath(driver, "//strong[contains(text(), 'Bid Status')]/following-sibling::span")
            bid_validity = self._extract_text_by_xpath(driver, "//strong[contains(text(), 'Bid Validity')]/following-sibling::span")
            start_date = self._extract_text_by_xpath(driver, "//strong[contains(text(), 'Bid Start Date')]/following-sibling::span")
            end_date = self._extract_text_by_xpath(driver, "//strong[contains(text(), 'Bid End Date')]/following-sibling::span")
            opening_date = self._extract_text_by_xpath(driver, "//strong[contains(text(), 'Bid Opening Date')]/following-sibling::span")
            contract_duration = self._extract_text_by_xpath(driver, "//strong[contains(text(), 'Contract Duration')]/following-sibling::span")

            # 3. Extract Buyer organisation details
            ministry = self._extract_text_by_xpath(driver, "//strong[contains(text(), 'Ministry')]/following-sibling::span")
            department = self._extract_text_by_xpath(driver, "//strong[contains(text(), 'Department')]/following-sibling::span")
            organisation = self._extract_text_by_xpath(driver, "//strong[contains(text(), 'Organisation')]/following-sibling::span")
            office = self._extract_text_by_xpath(driver, "//strong[contains(text(), 'Office')]/following-sibling::span")

            # 4. Technical Evaluation Sellers (collapseTwo)
            technical_sellers = []
            try:
                # Find all table rows in collapseTwo body
                rows = driver.find_elements(By.XPATH, "//div[@id='collapseTwo']//table/tbody/tr")
                for row in rows:
                    try:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        if len(cells) >= 4:
                            s_no_text = cells[0].text.strip()
                            seller_name = cells[1].text.strip()
                            # Strip out any badges like 'Under PMA' from the seller name
                            seller_name = seller_name.split("\n")[0].strip()
                            participated_on = cells[2].text.strip()
                            mse_mii = cells[3].text.strip()
                            status = cells[4].text.strip() if len(cells) > 4 else "N/A"
                            
                            technical_sellers.append({
                                "s_no": int(s_no_text) if s_no_text.isdigit() else 0,
                                "seller_name": seller_name,
                                "participated_on": participated_on,
                                "mse_mii_status": mse_mii,
                                "status": status
                            })
                    except Exception as row_ex:
                        self.logger.debug(f"Skipping technical evaluation row anomaly: {row_ex}")
            except Exception as e:
                self.logger.warning(f"Technical evaluation parse warning: {e}")

            # 5. Financial Evaluation Sellers (collapseThree)
            financial_sellers = []
            winner_name = ""
            awarded_value = 0.0
            
            try:
                rows = driver.find_elements(By.XPATH, "//div[@id='collapseThree']//table/tbody/tr")
                for row in rows:
                    try:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        if len(cells) >= 4:
                            s_no_text = cells[0].text.strip()
                            seller_name = cells[1].text.strip()
                            seller_name = seller_name.split("\n")[0].strip()
                            offered_item = cells[2].text.strip()
                            price_text = cells[3].text.strip()
                            
                            # Clean total price text from currency symbols and spaces
                            price_cleaned = price_text.replace("`", "").replace("Rs.", "").replace(",", "").strip()
                            total_price = 0.0
                            try:
                                total_price = float(price_cleaned)
                            except ValueError:
                                pass
                                
                            rank = cells[4].text.strip() if len(cells) > 4 else "N/A"
                            rank = rank.split("\n")[0].strip() # Clean rank formatting
                            
                            financial_sellers.append({
                                "s_no": int(s_no_text) if s_no_text.isdigit() else 0,
                                "seller_name": seller_name,
                                "offered_item": offered_item,
                                "total_price": total_price,
                                "rank": rank
                            })
                            
                            # If seller is L1, identify as winner and awarded value
                            if rank == "L1":
                                winner_name = seller_name
                                awarded_value = total_price
                    except Exception as row_ex:
                        self.logger.debug(f"Skipping financial evaluation row anomaly: {row_ex}")
            except Exception as e:
                self.logger.warning(f"Financial evaluation parse warning: {e}")

            # Fallback for winner/value if no L1 rank was found but we have financial list
            if not winner_name and financial_sellers:
                # Find seller with lowest rank or first index
                l1_candidates = [s for s in financial_sellers if "L1" in s["rank"]]
                if l1_candidates:
                    winner_name = l1_candidates[0]["seller_name"]
                    awarded_value = l1_candidates[0]["total_price"]
                else:
                    winner_name = financial_sellers[0]["seller_name"]
                    awarded_value = financial_sellers[0]["total_price"]

            # 6. Construct unified BidResult
            result = BidResult(
                bid_id=bid_id,
                bid_status=bid_status,
                bid_validity=bid_validity,
                start_date=start_date,
                end_date=end_date,
                opening_date=opening_date,
                contract_duration=contract_duration,
                ministry=ministry,
                department=department,
                organisation=organisation,
                office=office,
                technical_sellers=technical_sellers,
                financial_sellers=financial_sellers,
                winner_name=winner_name,
                awarded_value=awarded_value
            )

            return result.to_dict()

        except StaleElementReferenceException as e:
            self.logger.error("Stale WebElement reference encountered during detail extraction.")
            raise ScraperExtractionException(
                message="Stale element encountered during detailed item extraction.",
                details=str(e)
            ) from e
        except Exception as e:
            self.logger.error(f"Unexpected detailed bid extraction anomaly: {e}", exc_info=True)
            return {}

    def extract_batch(self, raw_collection: List[Any]) -> List[Dict[str, Any]]:
        """Placeholder matching BaseExtractor."""
        raise NotImplementedError("Use extract_item(driver) for detailed page parsing.")

    def validate(self, extracted_record: Dict[str, Any]) -> bool:
        """
        Runs schema validation checking for presence of bid_number, winner_name, and awarded_value.
        """
        report = self.schema_validator.validate_bid_result(extracted_record)
        if not report.is_valid:
            self.logger.error(f"Detailed Schema Validation Failures: {report.errors}")
            return False
        
        if report.warnings:
            self.logger.warning(f"Detailed Schema Validation Warnings: {report.warnings}")
        return True
