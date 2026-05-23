import logging
from typing import Tuple, Optional
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from src.config import TIMEOUTS
from src.utils.logger import get_logger

logger = get_logger("wait_utils")

DEFAULT_TIMEOUT = TIMEOUTS.get("EXPLICIT_WAIT", 15.0)
POLL_FREQUENCY = TIMEOUTS.get("POLL_FREQUENCY", 0.5)


def wait_for_element_presence(
    driver: WebDriver,
    locator: Tuple[str, str],
    timeout: Optional[float] = None
) -> WebElement:
    """
    Waits for an element to be present in the DOM.
    Returns the WebElement if present; raises TimeoutException otherwise.
    """
    t = timeout if timeout is not None else DEFAULT_TIMEOUT
    logger.debug(f"Waiting for element presence of locator: {locator} for {t}s")
    try:
        wait = WebDriverWait(driver, timeout=t, poll_frequency=POLL_FREQUENCY)
        element = wait.until(EC.presence_of_element_located(locator))
        return element
    except TimeoutException as e:
        logger.error(f"Timeout occurred waiting for presence of locator: {locator} after {t} seconds.")
        raise TimeoutException(f"Element presence timeout: {locator}") from e


def wait_for_visibility(
    driver: WebDriver,
    locator: Tuple[str, str],
    timeout: Optional[float] = None
) -> WebElement:
    """
    Waits for an element to be visible in the DOM.
    Returns the WebElement if visible; raises TimeoutException otherwise.
    """
    t = timeout if timeout is not None else DEFAULT_TIMEOUT
    logger.debug(f"Waiting for visibility of locator: {locator} for {t}s")
    try:
        wait = WebDriverWait(driver, timeout=t, poll_frequency=POLL_FREQUENCY)
        element = wait.until(EC.visibility_of_element_located(locator))
        return element
    except TimeoutException as e:
        logger.error(f"Timeout occurred waiting for visibility of locator: {locator} after {t} seconds.")
        raise TimeoutException(f"Element visibility timeout: {locator}") from e


def wait_for_clickable(
    driver: WebDriver,
    locator: Tuple[str, str],
    timeout: Optional[float] = None
) -> WebElement:
    """
    Waits for an element to be visible and enabled for clicking.
    Returns the WebElement if clickable; raises TimeoutException otherwise.
    """
    t = timeout if timeout is not None else DEFAULT_TIMEOUT
    logger.debug(f"Waiting for clickability of locator: {locator} for {t}s")
    try:
        wait = WebDriverWait(driver, timeout=t, poll_frequency=POLL_FREQUENCY)
        element = wait.until(EC.element_to_be_clickable(locator))
        return element
    except TimeoutException as e:
        logger.error(f"Timeout occurred waiting for clickability of locator: {locator} after {t} seconds.")
        raise TimeoutException(f"Element clickability timeout: {locator}") from e
