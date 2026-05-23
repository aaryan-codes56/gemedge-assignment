import sys
import time
from src.config import BASE_URL, OUTPUT_PATHS, DEVELOPER_MODE, GeMSelectors
from src.core import (
    DriverFactory,
    HealthChecker,
    ErrorHandler,
)
from src.scraper import GemPortalScraper
from src.utils import (
    get_logger,
    create_directories,
    MetricsTracker,
    DOMDebugger,
)

def main() -> None:
    # 1. Bootstrap folders and verify writable disk access
    directories = list(OUTPUT_PATHS.values())
    create_directories(directories)

    # 2. Get singleton logger
    logger = get_logger("orchestrator")
    logger.info("Initializing gemedge-procurement-intelligence-scraper platform...")

    # 3. Pre-flight health checking
    if not HealthChecker.run_preflight_checks():
        logger.critical("Pre-flight health checks failed. Aborting execution startup.")
        sys.exit(1)

    # 4. Telemetry bootstrapping
    metrics = MetricsTracker()
    metrics.reset()

    driver = None
    scraper = None
    try:
        # 5. Launch secure browser
        logger.info("Launching secure automation browser instance...")
        driver = DriverFactory.create_driver()

        # 6. Instantiate Portal Navigation Scraper
        logger.info("Instantiating GeM Portal Scraper...")
        scraper = GemPortalScraper(driver)
        scraper.initialize()

        # 7. Open portal home target
        scraper.open_portal(BASE_URL)

        # 8. Run filter and listing extraction automation workflow
        logger.info("Applying Status/Outcome filters and executing paginated listing extraction...")
        start_filter_time = time.time()
        scraper.scrape_data(max_pages=1)
        filter_duration = time.time() - start_filter_time
        logger.info(f"Paginated extraction workflow completed successfully in {filter_duration:.2f} seconds.")

        # 9. Developer Mode Diagnostics Checks (If configured active)
        if DEVELOPER_MODE:
            logger.info("=== DEVELOPER DIAGNOSTICS MODE ENABLED ===")
            logger.info("Capturing checkpoints diagnostics screenshot...")
            ErrorHandler.capture_diagnostic_screenshot(driver, prefix="dev_checkpoint")
            
            logger.info("Capturing active DOM HTML source snapshot...")
            DOMDebugger.dump_page_source(driver, prefix="dev_dom_dump")

            # Check a few elements to verify DOM rendering stability
            test_locators = {
                "Portal Logo": GeMSelectors.LANDING["logo"][0],
                "Search Box": GeMSelectors.FILTERS["search_input"][0],
                "Status Checkbox": GeMSelectors.FILTERS["status_bid_ra_checkbox"][0],
                "Outcome Checkbox": GeMSelectors.FILTERS["outcome_awarded_checkbox"][0]
            }
            DOMDebugger.run_multi_selector_diagnostics(driver, test_locators)
            logger.info("===========================================")

        # Log session final stats
        metrics.end_session()
        metrics.log_metrics_summary()

    except Exception as e:
        # 10. Translate exceptions, capture failure snapshot and advice recovery plan
        metrics.increment_failures(1)
        recommendation = ErrorHandler.handle_error(driver, e)
        logger.critical(
            f"Orchestration failure in scraper lifecycle. "
            f"Recommended Recovery Actions: {recommendation.recommendations}"
        )
        sys.exit(1)

    finally:
        # 11. Clean and safe driver shutdown
        if scraper is not None:
            scraper.shutdown()
        elif driver is not None:
            DriverFactory.close_driver(driver)
        logger.info("System foundation terminated and cleaned up successfully.")


if __name__ == "__main__":
    main()
