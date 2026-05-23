import time
import threading
from typing import Dict, Any, Optional

from src.utils.logger import get_logger

logger = get_logger("metrics")


class MetricsTracker:
    """
    A thread-safe Singleton telemetry engine for tracking scraper operational health.
    Captures operational metrics (pages, rows parsed, failures, duration) during runs.
    """
    _instance: Optional['MetricsTracker'] = None
    _lock = threading.RLock()

    def __new__(cls) -> 'MetricsTracker':
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(MetricsTracker, cls).__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        # Initialize variables once
        if not hasattr(self, "_initialized"):
            self.reset()
            self._initialized = True

    def reset(self) -> None:
        """Resets all metrics trackers to fresh states."""
        with self._lock:
            self.total_pages_scraped: int = 0
            self.total_bids_scraped: int = 0
            self.failed_extractions: int = 0
            self.retry_counts: int = 0
            self.start_time: float = time.time()
            self.end_time: Optional[float] = None

    def increment_pages(self, count: int = 1) -> None:
        with self._lock:
            self.total_pages_scraped += count
            logger.debug(f"Telemetry update: Pages Scraped +{count} (Total: {self.total_pages_scraped})")

    def increment_bids(self, count: int = 1) -> None:
        with self._lock:
            self.total_bids_scraped += count
            logger.debug(f"Telemetry update: Bids Parsed +{count} (Total: {self.total_bids_scraped})")

    def increment_failures(self, count: int = 1) -> None:
        with self._lock:
            self.failed_extractions += count
            logger.debug(f"Telemetry update: Extraction Failures +{count} (Total: {self.failed_extractions})")

    def increment_retries(self, count: int = 1) -> None:
        with self._lock:
            self.retry_counts += count
            logger.debug(f"Telemetry update: Retries Count +{count} (Total: {self.retry_counts})")

    def end_session(self) -> None:
        with self._lock:
            self.end_time = time.time()

    def get_execution_duration(self) -> float:
        with self._lock:
            end = self.end_time if self.end_time is not None else time.time()
            return end - self.start_time

    def get_success_rate(self) -> float:
        """
        Calculates success rate of parsed bids against failures.
        """
        with self._lock:
            total_attempts = self.total_bids_scraped + self.failed_extractions
            if total_attempts == 0:
                return 100.0
            return (self.total_bids_scraped / total_attempts) * 100.0

    def get_metrics(self) -> Dict[str, Any]:
        """
        Exports the tracked telemetry metrics as a standard dictionary representation.
        """
        with self._lock:
            duration = self.get_execution_duration()
            success_rate = self.get_success_rate()
            
            return {
                "total_pages_scraped": self.total_pages_scraped,
                "total_bids_scraped": self.total_bids_scraped,
                "failed_extractions": self.failed_extractions,
                "retry_counts": self.retry_counts,
                "execution_duration_seconds": round(duration, 2),
                "success_rate_percentage": round(success_rate, 2),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }

    def log_metrics_summary(self) -> None:
        """
        Generates a highly structured visual telemetry output inside standard logging streams.
        """
        metrics = self.get_metrics()
        logger.info(
            f"\n==================================================\n"
            f"          SCRAPER RUN METRICS SUMMARY             \n"
            f"==================================================\n"
            f" Pages Scraped      : {metrics['total_pages_scraped']}\n"
            f" Bids Scraped       : {metrics['total_bids_scraped']}\n"
            f" Failed Extractions : {metrics['failed_extractions']}\n"
            f" Total Retries      : {metrics['retry_counts']}\n"
            f" Execution Duration : {metrics['execution_duration_seconds']} seconds\n"
            f" Success Rate (%)   : {metrics['success_rate_percentage']}%\n"
            f"=================================================="
        )
