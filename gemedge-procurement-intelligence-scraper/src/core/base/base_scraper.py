from abc import ABC, abstractmethod
from typing import Any
from selenium.webdriver.remote.webdriver import WebDriver

from src.utils.logger import get_logger


class BaseScraper(ABC):
    """
    Abstract base class establishing the contract for all procurement scrapers.
    Guarantees consistent orchestration lifecycle patterns.
    """

    def __init__(self, driver: WebDriver) -> None:
        self.driver = driver
        self.logger = get_logger(self.__class__.__name__)

    @abstractmethod
    def start(self) -> None:
        """
        Executes pre-execution boots, folder validations, and state synchronization.
        """
        pass

    @abstractmethod
    def navigate_to_target(self, url: str) -> None:
        """
        Navigates the driver instance to the specified scraping URL target.
        """
        pass

    @abstractmethod
    def scrape_data(self) -> Any:
        """
        Executes the scraping orchestration (e.g., pagination, raw page retrieval).
        """
        pass

    @abstractmethod
    def validate(self) -> bool:
        """
        Runs sanity validations on the target scraping environment (DOM loaded, filters present).
        """
        pass
