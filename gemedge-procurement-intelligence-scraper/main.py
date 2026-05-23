import sys
from src.config import BASE_URL, OUTPUT_PATHS
from src.core import DriverFactory
from src.utils import get_logger, create_directories

def main() -> None:
    # 1. Bootstrap all system folders
    directories = list(OUTPUT_PATHS.values())
    create_directories(directories)

    # 2. Initialize and retrieve singleton logger
    logger = get_logger("orchestrator")
    logger.info("Initializing gemedge-procurement-intelligence-scraper foundation...")
    
    driver = None
    try:
        # 3. Launch configured Selenium driver
        logger.info("Launching secure automation browser instance...")
        driver = DriverFactory.create_driver()

        # 4. Load targeting platform URL
        logger.info(f"Navigating to primary procurement target: {BASE_URL}")
        driver.get(BASE_URL)

        # 5. Capture verification outputs (dry-run sanity check)
        title = driver.title
        current_url = driver.current_url
        
        logger.info("==================================================")
        logger.info("       SYSTEM FOUNDATION INITIALIZED SUCCESSFULLY   ")
        logger.info("==================================================")
        logger.info(f"Verified Title : {title}")
        logger.info(f"Verified URL   : {current_url}")
        logger.info("==================================================")

    except Exception as e:
        logger.critical(f"Orchestration failure in scraper lifecycle: {e}", exc_info=True)
        sys.exit(1)
        
    finally:
        # 6. Safe and guaranteed browser teardown
        if driver is not None:
            DriverFactory.close_driver(driver)
            logger.info("System foundation terminated and cleaned up successfully.")


if __name__ == "__main__":
    main()
