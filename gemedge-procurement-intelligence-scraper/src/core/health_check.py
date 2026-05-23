import os
import socket
import sys
from pathlib import Path
from typing import List, Dict

from src.config import OUTPUT_PATHS, LOG_LEVEL
from src.utils.logger import get_logger

logger = get_logger("health_check")


class HealthChecker:
    """
    Validates host execution suitability during the system boot sequence.
    Detects connectivity drops, filesystem blocks, or browser tool compatibility.
    """

    @staticmethod
    def check_internet_connectivity(host: str = "bidplus.gem.gov.in", port: int = 443, timeout: float = 3.0) -> bool:
        """
        Verifies external connection viability by opening a lightweight socket connection.
        """
        logger.debug(f"Health Check: Testing socket connection to {host}:{port}...")
        try:
            # Resolve DNS and establish TCP connection
            socket.setdefaulttimeout(timeout)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((host, port))
            logger.info("Health Check: Active Internet Connection verified.")
            return True
        except (socket.timeout, socket.gaierror, ConnectionRefusedError) as e:
            logger.error(f"Health Check CRITICAL: Host connection test failed. Unable to reach {host}:{port}. Error: {e}")
            return False

    @staticmethod
    def check_writable_directories() -> bool:
        """
        Ensures that every defined system directory is present and fully writable.
        """
        logger.debug("Health Check: Evaluating disk write permissions...")
        all_passed = True
        
        for name, dir_path in OUTPUT_PATHS.items():
            path_obj = Path(dir_path)
            try:
                # Ensure directory exists
                path_obj.mkdir(parents=True, exist_ok=True)
                
                # Test write capability
                test_file = path_obj / ".health_check_temp"
                with open(test_file, "w", encoding="utf-8") as f:
                    f.write("health_check_ok")
                
                # Delete test file
                if test_file.exists():
                    test_file.unlink()
                    
                logger.debug(f"Health Check: Path {name} ({dir_path}) is WRITABLE.")
            except Exception as e:
                logger.error(f"Health Check CRITICAL: Path {name} ({dir_path}) is NOT writable. Error: {e}")
                all_passed = False

        return all_passed

    @staticmethod
    def check_chrome_availability() -> bool:
        """
        Asserts that Google Chrome or Chromium is present in standard macOS paths.
        """
        logger.debug("Health Check: Scanning host environment for Google Chrome executable...")
        
        # Standard macOS installations
        mac_paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
            # User level applications
            str(Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        ]

        # Check path executables
        for path in mac_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                logger.info(f"Health Check: Google Chrome executable located at: {path}")
                return True

        # Fallback check standard shell executable flags
        for binary in ["google-chrome", "google-chrome-stable", "chromium-browser", "chromium"]:
            try:
                import subprocess
                result = subprocess.run(["which", binary], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if result.returncode == 0 and result.stdout.strip():
                    path = result.stdout.strip()
                    logger.info(f"Health Check: Google Chrome found via shell query at: {path}")
                    return True
            except Exception:
                pass

        logger.error(
            "Health Check CRITICAL: Google Chrome executable could not be resolved. "
            "Please ensure Google Chrome is installed on the macOS host under /Applications/."
        )
        return False

    @classmethod
    def run_preflight_checks(cls) -> bool:
        """
        Orchestrates the entire preflight execution sequence.
        Returns True if all checks succeed; returns False otherwise.
        """
        logger.info("Executing Scraper System Preflight Health Checks...")
        
        directories_ok = cls.check_writable_directories()
        internet_ok = cls.check_internet_connectivity()
        chrome_ok = cls.check_chrome_availability()
        
        # Log-level checking
        logger.info(f"Health Check: Scraper LOG_LEVEL set to '{LOG_LEVEL}'")
        
        if directories_ok and internet_ok and chrome_ok:
            logger.info("==================================================")
            logger.info("      ALL PREFLIGHT HEALTH CHECKS PASSED          ")
            logger.info("==================================================")
            return True
        else:
            logger.critical("==================================================")
            logger.critical("     PREFLIGHT HEALTH CHECKS FAILED               ")
            logger.critical("   Please review above logs before proceeding     ")
            logger.critical("==================================================")
            return False
