import time
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

from selenium.webdriver.remote.webdriver import WebDriver

from src.config import OUTPUT_PATHS
from src.utils.logger import get_logger

logger = get_logger("dom_debug")


class DOMDebugger:
    """
    Diagnostic assistant to troubleshoot dynamic, asynchronous DOM adjustments in Headless sessions.
    Allows capturing full raw DOM page dumps and executing test queries on target elements.
    """

    @staticmethod
    def dump_page_source(driver: WebDriver, prefix: str = "failed_page") -> Optional[Path]:
        """
        Saves the current raw document page source to the logs directory.
        """
        log_dir = OUTPUT_PATHS.get("LOGS", Path("logs"))
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"{prefix}_{timestamp}.html"
            dest_path = log_dir / filename

            with open(dest_path, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            
            logger.info(f"DOM Debugger: Staged active HTML dump at: {dest_path}")
            return dest_path
        except Exception as e:
            logger.warning(f"DOM Debugger: Failed to write active page source to disc: {e}")
            return None

    @staticmethod
    def validate_selector(driver: WebDriver, selector: Tuple[str, str]) -> Dict[str, Any]:
        """
        Queries the DOM with a locator tuple, evaluating visibility, matches count, and text summaries.
        Useful for dynamic element audits.
        """
        by_strategy, expression = selector
        logger.debug(f"Auditing selector query strategy '{by_strategy}' using path: '{expression}'")
        
        report: Dict[str, Any] = {
            "selector": selector,
            "match_count": 0,
            "visible_count": 0,
            "elements": []
        }

        try:
            elements = driver.find_elements(by_strategy, expression)
            report["match_count"] = len(elements)

            for idx, el in enumerate(elements[:5]):  # Process top 5 matches
                is_displayed = False
                text = ""
                tag_name = ""
                try:
                    is_displayed = el.is_displayed()
                    text = el.text[:50]  # First 50 chars of inner text
                    tag_name = el.tag_name
                    if is_displayed:
                        report["visible_count"] += 1
                except Exception:
                    pass

                report["elements"].append({
                    "index": idx,
                    "tag_name": tag_name,
                    "is_displayed": is_displayed,
                    "text_snippet": text,
                    "class_name": el.get_attribute("class") or ""
                })

            logger.info(
                f"DOM Auditor: Selector {selector} -> Matches: {report['match_count']}, "
                f"Visible: {report['visible_count']}"
            )
            
            if report["match_count"] > 0:
                for entry in report["elements"]:
                    logger.debug(
                        f"  [{entry['index']}] <{entry['tag_name']}> Class: '{entry['class_name']}' | "
                        f"Visible: {entry['is_displayed']} | Text: '{entry['text_snippet']}'"
                    )

        except Exception as e:
            logger.error(f"DOM Auditor: Query parsing threw an error for selector {selector}. Error: {e}")

        return report

    @classmethod
    def run_multi_selector_diagnostics(
        cls,
        driver: WebDriver,
        named_selectors: Dict[str, Tuple[str, str]]
    ) -> None:
        """
        Takes a list of selector mappings, checks all of them, and logs visibility statuses.
        """
        logger.info("=== DOM SELECTORS TRACING DIAGNOSTICS ===")
        for name, locator in named_selectors.items():
            logger.info(f"Tracing element: '{name}'")
            cls.validate_selector(driver, locator)
        logger.info("=========================================")
