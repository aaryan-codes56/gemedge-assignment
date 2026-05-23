import json
import logging
import threading
from pathlib import Path
from typing import Dict, Any, List, Set, Optional

from src.config import OUTPUT_PATHS
from src.core.error_handler import ScraperStatePersistenceException
from src.utils.logger import get_logger

logger = get_logger("state_manager")


class StateManager:
    """
    Manages lightweight JSON execution checkpoints for crash recovery.
    Tracks successfully completed page numbers and bid IDs to allow seamless resume.
    """
    _lock = threading.Lock()

    def __init__(self, state_filename: str = "scraper_state.json") -> None:
        self.state_dir = OUTPUT_PATHS.get("DATA_RAW", Path("data/raw"))
        self.state_file = self.state_dir / state_filename
        
        self.last_completed_page: int = 0
        self.completed_bid_ids: Set[str] = set()
        
        # Load state on instantiation
        self.load_state()

    def load_state(self) -> None:
        """
        Loads checkpoint state from the JSON persistence file.
        """
        with self._lock:
            if not self.state_file.exists():
                logger.info("No checkpoint file detected. Initiating empty execution state.")
                self.last_completed_page = 0
                self.completed_bid_ids = set()
                return

            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                self.last_completed_page = data.get("last_completed_page", 0)
                self.completed_bid_ids = set(data.get("completed_bid_ids", []))
                
                logger.info(
                    f"Successfully loaded checkpoint: resuming from page {self.last_completed_page + 1}. "
                    f"Already parsed bids count: {len(self.completed_bid_ids)}."
                )
            except Exception as e:
                logger.error(f"Failed to load checkpoint file at {self.state_file}: {e}")
                raise ScraperStatePersistenceException(
                    message=f"Failed to read execution state file: {self.state_file}",
                    details=str(e)
                ) from e

    def save_state(self, page_number: int) -> None:
        """
        Saves current page progress and completed bid IDs to persistence storage.
        """
        with self._lock:
            try:
                self.last_completed_page = page_number
                
                # Prepare parent path
                self.state_file.parent.mkdir(parents=True, exist_ok=True)
                
                state_data = {
                    "last_completed_page": self.last_completed_page,
                    "completed_bid_ids": list(self.completed_bid_ids),
                    "last_updated": Path(self.state_file).resolve().stat().st_mtime if self.state_file.exists() else 0.0
                }

                with open(self.state_file, "w", encoding="utf-8") as f:
                    json.dump(state_data, f, ensure_ascii=False, indent=4)
                
                logger.debug(f"Saved checkpoint progress to {self.state_file}. Page: {page_number}")
            except Exception as e:
                logger.error(f"Failed to persist checkpoint file at {self.state_file}: {e}")
                raise ScraperStatePersistenceException(
                    message=f"Failed to save execution state file: {self.state_file}",
                    details=str(e)
                ) from e

    def mark_bid_completed(self, bid_id: str) -> None:
        """
        Appends a completed bid ID to state, saving immediately to file.
        """
        if not bid_id:
            return
        
        self.completed_bid_ids.add(bid_id)
        # Periodic autosave state
        self.save_state(self.last_completed_page)

    def is_bid_completed(self, bid_id: str) -> bool:
        """
        Returns True if the specified bid ID has already been parsed.
        """
        return bid_id in self.completed_bid_ids

    def get_last_completed_page(self) -> int:
        """
        Returns the last fully processed page number.
        """
        return self.last_completed_page

    def clear_state(self) -> None:
        """
        Removes the local checkpoint file and resets current session progress.
        """
        with self._lock:
            self.last_completed_page = 0
            self.completed_bid_ids = set()
            try:
                if self.state_file.exists():
                    self.state_file.unlink()
                    logger.info("Local scraper checkpoint cleared and deleted.")
            except Exception as e:
                logger.warning(f"Error while deleting checkpoint state file: {e}")
