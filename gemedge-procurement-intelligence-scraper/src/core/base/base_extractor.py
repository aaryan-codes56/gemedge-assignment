from abc import ABC, abstractmethod
from typing import Any, Dict, List

from src.utils.logger import get_logger


class BaseExtractor(ABC):
    """
    Abstract base class for extracting intelligence information from raw page contents (HTML/JSON).
    Decoupled from browser manipulation logic.
    """

    def __init__(self) -> None:
        self.logger = get_logger(self.__class__.__name__)

    @abstractmethod
    def extract_item(self, raw_element: Any) -> Dict[str, Any]:
        """
        Parses a single raw block or element and extracts a key-value record map.
        """
        pass

    @abstractmethod
    def extract_batch(self, raw_collection: List[Any]) -> List[Dict[str, Any]]:
        """
        Converts a list of raw elements or raw structures into a list of structured records.
        """
        pass

    @abstractmethod
    def validate(self, extracted_record: Dict[str, Any]) -> bool:
        """
        Validates structural format, ensuring no data loss occurred during raw parsing.
        """
        pass
