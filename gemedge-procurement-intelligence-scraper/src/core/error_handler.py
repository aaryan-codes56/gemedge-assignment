import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List

from selenium.webdriver.remote.webdriver import WebDriver

from src.config import OUTPUT_PATHS
from src.utils.logger import get_logger

logger = get_logger("error_handler")


# ==================================================
# EXCEPTION HIERARCHY
# ==================================================

class ScraperException(Exception):
    """Base exception for all procurement scraper operations."""
    def __init__(self, message: str, details: Optional[str] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or ""


class ScraperTimeoutException(ScraperException):
    """Raised when an explicit wait or page load hits a hard timeout."""
    pass


class ScraperStaleElementException(ScraperException):
    """Raised when interacting with an element that is no longer attached to the DOM."""
    pass


class ScraperNavigationException(ScraperException):
    """Raised when navigation to a URL fails or fails connection checks."""
    pass


class ScraperExtractionException(ScraperException):
    """Raised when element parsing, raw selectors, or DOM queries fail during extraction."""
    pass


class ScraperDataValidationException(ScraperException):
    """Raised when schema validation or type checks fail on scraped records."""
    pass


class ScraperStatePersistenceException(ScraperException):
    """Raised when saving or loading checkpoint files fails."""
    pass


# ==================================================
# RECOVERY MECHANISMS
# ==================================================

@dataclass
class RecoveryRecommendation:
    """Encapsulates system recovery actions when an exception occurs."""
    exception_type: str
    message: str
    recommendations: List[str]
    should_retry: bool
    should_restart_session: bool


class ErrorHandler:
    """
    Centralized handler responsible for error capturing, logging,
    screenshot diagnostics, and compiling actionable recovery steps.
    """

    @staticmethod
    def capture_diagnostic_screenshot(driver: Optional[WebDriver], prefix: str = "error") -> Optional[Path]:
        """
        Safely saves a screenshot of the active browser DOM to the screenshots/ folder.
        """
        if driver is None:
            logger.debug("Screenshot request skipped: No active WebDriver session provided.")
            return None

        screenshots_dir = OUTPUT_PATHS.get("SCREENSHOTS", Path("screenshots"))
        try:
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"{prefix}_{timestamp}.png"
            dest_path = screenshots_dir / filename

            driver.save_screenshot(str(dest_path))
            logger.info(f"Diagnostic screenshot saved to: {dest_path}")
            return dest_path
        except Exception as e:
            logger.warning(f"Failed to capture diagnostic screenshot: {e}")
            return None

    @classmethod
    def handle_error(cls, driver: Optional[WebDriver], exception: Exception) -> RecoveryRecommendation:
        """
        Processes any encountered exception, translates it to a custom ScraperException,
        takes diagnostic screenshot, logs the stack trace, and issues recovery advice.
        """
        exc_type = type(exception).__name__
        msg = str(exception)
        
        # Determine the translated scraper exception type and recovery plan
        if isinstance(exception, ScraperTimeoutException):
            rec = RecoveryRecommendation(
                exception_type=exc_type,
                message=msg,
                recommendations=["Increase EXPLICIT_WAIT timeout in settings.py", "Verify internet latency", "Verify selector presence in selectors.py"],
                should_retry=True,
                should_restart_session=False
            )
        elif isinstance(exception, ScraperStaleElementException):
            rec = RecoveryRecommendation(
                exception_type=exc_type,
                message=msg,
                recommendations=["Refresh the page DOM before locating", "Re-query the selector instead of reusing WebElement reference"],
                should_retry=True,
                should_restart_session=False
            )
        elif isinstance(exception, ScraperNavigationException):
            rec = RecoveryRecommendation(
                exception_type=exc_type,
                message=msg,
                recommendations=["Check network and host internet connectivity", "Verify GeM portal server is not down", "Review browser proxy configurations"],
                should_retry=True,
                should_restart_session=True
            )
        elif isinstance(exception, ScraperExtractionException):
            rec = RecoveryRecommendation(
                exception_type=exc_type,
                message=msg,
                recommendations=["Verify if GeM DOM portal selectors have changed", "Inspect selector fallbacks inside selectors.py"],
                should_retry=False,
                should_restart_session=False
            )
        elif isinstance(exception, ScraperDataValidationException):
            rec = RecoveryRecommendation(
                exception_type=exc_type,
                message=msg,
                recommendations=["Check for malformed data formats", "Verify parser field types inside schema_validator.py"],
                should_retry=False,
                should_restart_session=False
            )
        elif isinstance(exception, ScraperStatePersistenceException):
            rec = RecoveryRecommendation(
                exception_type=exc_type,
                message=msg,
                recommendations=["Confirm write access to data/ raw directories", "Check state JSON file syntax"],
                should_retry=False,
                should_restart_session=False
            )
        else:
            # Generic recovery plan
            rec = RecoveryRecommendation(
                exception_type=exc_type,
                message=msg,
                recommendations=["Inspect standard trace output logs", "Verify driver factory compatibility with host environment"],
                should_retry=True,
                should_restart_session=True
            )

        # 1. Capture diagnostic visual screenshot
        cls.capture_diagnostic_screenshot(driver, prefix=rec.exception_type.lower())

        # 2. Structured logging output
        logger.error(
            f"=== SCRAPER ERROR DETECTED ===\n"
            f"Type: {rec.exception_type}\n"
            f"Message: {rec.message}\n"
            f"Recommendations: {', '.join(rec.recommendations)}\n"
            f"Actionable Action: Retry={rec.should_retry}, Re-launch Session={rec.should_restart_session}\n"
            f"=============================",
            exc_info=True
        )

        return rec
