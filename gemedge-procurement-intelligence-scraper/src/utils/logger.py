import logging
import os
import sys
import threading
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional

from src.config import LOG_LEVEL, LOG_FORMAT, LOG_DATE_FORMAT, OUTPUT_PATHS


class ScraperLogger:
    """
    A thread-safe Singleton Logger Manager that configures standard logging.
    Supports console logging and daily/session rotating file logging.
    """
    _instance: Optional['ScraperLogger'] = None
    _lock = threading.Lock()
    _logger: Optional[logging.Logger] = None

    def __new__(cls) -> 'ScraperLogger':
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(ScraperLogger, cls).__new__(cls)
        return cls._instance

    def initialize(
        self,
        name: str = "gemedge_scraper",
        log_level: Optional[str] = None,
        log_to_file: bool = True
    ) -> logging.Logger:
        """
        Initializes the logger configuration. If already initialized, returns the existing logger.
        """
        with self._lock:
            if self._logger is not None:
                return self._logger

            # Determine logging level
            level = getattr(logging, log_level.upper() if log_level else LOG_LEVEL, logging.INFO)

            logger = logging.getLogger(name)
            logger.setLevel(level)
            logger.propagate = False  # Avoid duplicate logging up the hierarchy

            # Formatter definition
            formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

            # 1. Console Handler
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(level)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

            # 2. File Handler (If enabled)
            if log_to_file:
                log_dir = OUTPUT_PATHS.get("LOGS", Path("logs"))
                try:
                    log_dir.mkdir(parents=True, exist_ok=True)
                    log_file = log_dir / "scraper_run.log"
                    
                    # 10 MB limit per file, keep 5 back-ups
                    file_handler = RotatingFileHandler(
                        filename=log_file,
                        maxBytes=10 * 1024 * 1024,
                        backupCount=5,
                        encoding="utf-8"
                    )
                    file_handler.setLevel(level)
                    file_handler.setFormatter(formatter)
                    logger.addHandler(file_handler)
                except Exception as e:
                    # Fallback if logs directory is not writable
                    print(f"Warning: Failed to set up file logging. Error: {e}", file=sys.stderr)

            self._logger = logger
            return self._logger

    def get_logger(self) -> logging.Logger:
        """
        Returns the configured logger. Initializes standard settings if not yet initialized.
        """
        if self._logger is None:
            return self.initialize()
        return self._logger


def get_logger(name: str = "gemedge_scraper") -> logging.Logger:
    """
    Convenience function to get the central singleton logger.
    """
    return ScraperLogger().initialize(name=name)
