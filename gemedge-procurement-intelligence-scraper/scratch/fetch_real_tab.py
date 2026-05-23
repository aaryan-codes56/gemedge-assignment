import sys
import time
from pathlib import Path
from selenium.webdriver.common.by import By

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.core.driver_factory import DriverFactory
from src.scraper.gem_portal_scraper import GemPortalScraper

def main():
    print("Launching Selenium driver via DriverFactory...")
    driver = DriverFactory.create_driver()
    
    print("Instantiating GemPortalScraper...")
    scraper = GemPortalScraper(driver=driver)
    try:
        print("Initializing scraper session...")
        scraper.initialize()
        
        print("Opening portal...")
        scraper.open_portal()
        
        # Apply filters to ensure we are looking at completed bids
        scraper.apply_status_filter()
        scraper.apply_outcome_filter()
        
        # Find the first "View BID Results" link
        print("Locating View BID Results button...")
        results_btn = scraper.find_element_with_fallback({
            "btn": [
                (By.CSS_SELECTOR, "a[href*='getBidResultView']"),
                (By.CSS_SELECTOR, "a[href*='getSinglePacketResultView']"),
                (By.XPATH, "//a[contains(@href, 'getBidResultView')]")
            ]
        }, "btn")
        
        parent_handle = scraper.driver.current_window_handle
        print("Opening Bid Result detail page in a new tab...")
        scraper.robust_click(results_btn)
        time.sleep(6) # Wait for page load
        
        # Switch to new tab
        print("Switching window handles...")
        for handle in scraper.driver.window_handles:
            if handle != parent_handle:
                scraper.driver.switch_to.window(handle)
                break
                
        print(f"Active tab URL: {scraper.driver.current_url}")
        
        source = scraper.driver.page_source
        dest_path = Path("logs/real_tab_dump.html")
        dest_path.write_text(source, encoding="utf-8")
        print(f"Successfully saved true detail DOM to {dest_path.resolve()}")
        print(f"Total HTML characters in detail tab: {len(source)}")
        
    except Exception as e:
        print(f"Error during tab extraction: {e}")
    finally:
        scraper.shutdown()

if __name__ == "__main__":
    main()
