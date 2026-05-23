import os
from pathlib import Path
from typing import Dict, Any, Tuple

# Project Root Resolution (3 levels up from gemedge-procurement-intelligence-scraper/src/config/settings.py)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Base Scraping Targets
BASE_URL = os.getenv("SCRAPER_BASE_URL", "https://bidplus.gem.gov.in/all-bids")

# Automation / Browser Settings
HEADLESS_MODE = os.getenv("SCRAPER_HEADLESS", "True").lower() in ("true", "1", "yes")
WINDOW_SIZE: Tuple[int, int] = (1920, 1080)
USER_AGENT = os.getenv(
    "SCRAPER_USER_AGENT",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Centralized Automation Timeouts (Seconds)
TIMEOUTS: Dict[str, float] = {
    "IMPLICIT_WAIT": float(os.getenv("TIMEOUT_IMPLICIT", "0.0")),  # Explicit wait preferred, set implicit to 0
    "EXPLICIT_WAIT": float(os.getenv("TIMEOUT_EXPLICIT", "15.0")),
    "PAGE_LOAD": float(os.getenv("TIMEOUT_PAGE_LOAD", "30.0")),
    "SCRIPT_TIMEOUT": float(os.getenv("TIMEOUT_SCRIPT", "30.0")),
    "POLL_FREQUENCY": float(os.getenv("TIMEOUT_POLL", "0.5")),
}

# Retry Strategy Configuration
RETRY_CONFIG: Dict[str, Any] = {
    "MAX_ATTEMPTS": int(os.getenv("RETRY_MAX_ATTEMPTS", "3")),
    "DELAY_SECONDS": float(os.getenv("RETRY_DELAY", "2.0")),
    "BACKOFF_FACTOR": float(os.getenv("RETRY_BACKOFF", "2.0")),
}

# Production Logger Settings
LOG_LEVEL = os.getenv("SCRAPER_LOG_LEVEL", "INFO").upper()
LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s:%(filename)s:%(lineno)d] - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Directory Structure Paths (Auto-generated relative to PROJECT_ROOT)
OUTPUT_PATHS: Dict[str, Path] = {
    "DATA_RAW": PROJECT_ROOT / "data" / "raw",
    "DATA_PROCESSED": PROJECT_ROOT / "data" / "processed",
    "OUTPUTS": PROJECT_ROOT / "outputs",
    "SCREENSHOTS": PROJECT_ROOT / "screenshots",
    "LOGS": PROJECT_ROOT / "logs",
}
