import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.core.driver_factory import DriverFactory
from src.extractor.bid_detail_extractor import BidDetailExtractor

def main():
    print("Launching Selenium driver for offline testing...")
    driver = DriverFactory.create_driver()
    try:
        # Load local HTML dump
        dump_path = Path("logs/real_tab_dump.html").resolve()
        file_url = f"file://{dump_path}"
        print(f"Loading offline page: {file_url}")
        driver.get(file_url)
        
        # Instantiate extractor
        print("Instantiating BidDetailExtractor...")
        extractor = BidDetailExtractor()
        
        # Parse items
        print("Extracting bid details...")
        record = extractor.extract_item(driver)
        
        print("\n==================================================")
        print("EXTRACTION RESULTS:")
        print("==================================================")
        for k, v in record.items():
            if k in ["technical_sellers", "financial_sellers"]:
                print(f"{k}: {len(v)} sellers parsed successfully.")
                for s in v[:2]:
                    print(f"  - {s}")
            else:
                print(f"{k}: {v}")
        print("==================================================\n")
        
        # Run validations
        print("Running schema validation checks...")
        is_valid = extractor.validate(record)
        print(f"Schema Validation Result: {is_valid}")
        
        # Assertions to ensure staffing-level correctness
        assert record["bid_id"] == "GEM/2026/B/7537433", "Bid ID mismatch!"
        assert record["bid_status"] == "Active", "Bid Status mismatch!"
        assert record["ministry"] == "Ministry Of Defence", "Ministry mismatch!"
        assert len(record["technical_sellers"]) == 3, "Technical sellers count mismatch!"
        assert len(record["financial_sellers"]) == 3, "Financial sellers count mismatch!"
        assert record["winner_name"] == "EVERSHINE ENTERPRISES", "Winner name mismatch!"
        assert record["awarded_value"] == 23482.0, "Awarded value mismatch!"
        
        print("\nALL PARSING AND VALIDATION ASSERTIONS PASSED TRIUMPHANTLY!")
        
    except Exception as e:
        print(f"Testing failed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
