from abc import ABC, abstractmethod
from typing import Any, Dict
import pandas as pd

from src.utils.logger import get_logger


class BaseInsightsGenerator(ABC):
    """
    Abstract base class for extracting business intelligence insights, trends,
    or generating summary analytics reports from the cleaned procurement datasets.
    """

    def __init__(self) -> None:
        self.logger = get_logger(self.__class__.__name__)

    @abstractmethod
    def generate_report(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Processes a cleaned DataFrame and returns statistical or strategic key-value insights.
        """
        pass

    @abstractmethod
    def validate(self, report: Dict[str, Any]) -> bool:
        """
        Sanity checks report values to prevent math anomalies or empty insights keys.
        """
        pass
