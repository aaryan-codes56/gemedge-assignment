from abc import ABC, abstractmethod
from typing import Any, List, Dict
import pandas as pd

from src.utils.logger import get_logger


class BaseCleaner(ABC):
    """
    Abstract base class for data cleaning, sanitization, and normalization pipelines.
    Guarantees clean, typed tabular structures (DataFrames) for downstream reporting.
    """

    def __init__(self) -> None:
        self.logger = get_logger(self.__class__.__name__)

    @abstractmethod
    def clean_record(self, raw_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Cleans data types, parses dates, sanitizes strings, and handles nulls for a single dictionary record.
        """
        pass

    @abstractmethod
    def process_to_dataframe(self, records: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Processes and transforms a list of dictionaries into a normalized Pandas DataFrame.
        """
        pass
