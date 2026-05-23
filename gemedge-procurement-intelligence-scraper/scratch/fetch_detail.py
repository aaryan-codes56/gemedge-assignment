import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.core.driver_factory import DriverFactory

def main():
    print("Initializing headless driver...")
    driver = DriverFactory.create_driver()
    try:
        url = "https://bidplus.gem.gov.in/bidding/bid/getBidResultView/9350689"
        print(f"Loading URL: {url}")
        driver.get(url)
        
        # Give it a few seconds to load AJAX/DOM elements
        import time
        time.sleep(5)
        
        source = driver.page_source
        dest_path = Path("logs/detail_page_dump.html")
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_text(source, encoding="utf-8")
        
        print(f"Successfully saved DOM to {dest_path.resolve()}")
        print(f"Total HTML characters: {len(source)}")
    except Exception as e:
        print(f"Error fetching page: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
