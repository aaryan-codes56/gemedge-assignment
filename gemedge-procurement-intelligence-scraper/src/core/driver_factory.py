import logging
from typing import Optional
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager

from src.config import HEADLESS_MODE, WINDOW_SIZE, USER_AGENT, TIMEOUTS
from src.utils.logger import get_logger

logger = get_logger("driver_factory")


class DriverFactory:
    """
    A factory class for producing and configuring Selenium WebDriver instances.
    Implements production-ready Chrome options for anti-detection and stability.
    """

    @staticmethod
    def get_chrome_options() -> ChromeOptions:
        """
        Creates and returns highly robust Chrome options tuned for reliable scraping.
        """
        options = ChromeOptions()

        # Headless Configuration
        if HEADLESS_MODE:
            logger.info("Initializing browser in HEADLESS mode.")
            # Use '--headless=new' which is Chrome's modern, fully featured headless engine
            options.add_argument("--headless=new")
        else:
            logger.info("Initializing browser in ACTIVE GUI mode.")

        # Performance & Container Safety Arguments
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument(f"--window-size={WINDOW_SIZE[0]},{WINDOW_SIZE[1]}")
        options.add_argument(f"user-agent={USER_AGENT}")

        # Evade standard webdriver detection flags
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        return options

    @classmethod
    def create_driver(cls) -> webdriver.Chrome:
        """
        Initializes and returns a fully configured Chrome WebDriver instance.
        """
        try:
            options = cls.get_chrome_options()
            
            logger.debug("Downloading/resolving Chrome driver via webdriver-manager...")
            service = ChromeService(ChromeDriverManager().install())
            
            logger.debug("Instantiating Chrome WebDriver instance...")
            driver = webdriver.Chrome(service=service, options=options)

            # Apply standard orchestration timeouts
            driver.set_page_load_timeout(TIMEOUTS.get("PAGE_LOAD", 30.0))
            driver.set_script_timeout(TIMEOUTS.get("SCRIPT_TIMEOUT", 30.0))
            
            # Keep implicit wait at 0.0 (we use wait_utils explicit waits exclusively)
            driver.implicitly_wait(TIMEOUTS.get("IMPLICIT_WAIT", 0.0))

            logger.info("Selenium WebDriver created successfully.")
            return driver

        except Exception as e:
            logger.error(f"Critical error occurred during WebDriver creation: {e}", exc_info=True)
            raise RuntimeError(f"WebDriver Initialization Failed: {e}") from e

    @staticmethod
    def close_driver(driver: Optional[webdriver.Chrome]) -> None:
        """
        Safely shuts down the provided WebDriver instance.
        Prevents lingering chromedriver processes from leaking system resources.
        """
        if driver is not None:
            try:
                logger.info("Initiating browser shutdown sequence...")
                driver.close()
                driver.quit()
                logger.info("Browser shut down safely and resources released.")
            except Exception as e:
                logger.warning(f"Error encountered during browser shutdown: {e}")
        else:
            logger.debug("Close driver called on null/undefined instance.")
