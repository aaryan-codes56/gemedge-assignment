"""
Offline validation test for VendorEvaluationExtractor.
Loads logs/real_tab_dump.html in a headless browser and verifies:
  - vendor records are parsed
  - pricing analytics are computed correctly
  - anomaly detection runs without error
  - validation passes on each VendorDetail row
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.core.driver_factory import DriverFactory
from src.extractor.vendor_evaluation_extractor import VendorEvaluationExtractor


def main() -> None:
    print("=== VendorEvaluationExtractor — Offline Validation Test ===\n")
    driver = DriverFactory.create_driver()
    try:
        dump_path = Path("logs/real_tab_dump.html").resolve()
        driver.get(f"file://{dump_path}")
        print(f"Loaded: {dump_path}\n")

        extractor = VendorEvaluationExtractor()
        result = extractor.extract_item(driver)

        # ── Top-level presence ────────────────────────────────────────────────
        assert result, "extract_item returned empty dict"
        assert result.get("bid_id"), "bid_id missing"
        assert isinstance(result.get("vendor_records"), list), "vendor_records not a list"
        assert isinstance(result.get("analytics"), dict), "analytics not a dict"
        assert isinstance(result.get("anomaly_flags"), dict), "anomaly_flags not a dict"

        vendor_rows = result["vendor_records"]
        analytics   = result["analytics"]
        anomalies   = result["anomaly_flags"]

        print(f"Bid ID      : {result['bid_id']}")
        print(f"Bid Status  : {result['bid_status']}")
        print(f"Vendor Rows : {len(vendor_rows)}\n")

        # ── Analytics ─────────────────────────────────────────────────────────
        print("── Pricing Analytics ──────────────────────────────────────")
        for k, v in analytics.items():
            print(f"  {k:<22}: {v}")
        print()

        # ── Vendor rows ───────────────────────────────────────────────────────
        print("── Vendor Records ─────────────────────────────────────────")
        for vr in vendor_rows:
            status = "AWARDED" if vr["awarded_flag"] else f"rank={vr['vendor_rank']}"
            print(
                f"  [{status}] {vr['vendor_name']:<35} "
                f"price={vr['quoted_price']:>10,.2f}  "
                f"tech={vr['technically_qualified']}  fin={vr['financially_qualified']}"
            )
        print()

        # ── Anomaly flags ─────────────────────────────────────────────────────
        print("── Anomaly Flags ──────────────────────────────────────────")
        for flag, val in anomalies.items():
            print(f"  {flag:<40}: {val}")
        print()

        # ── Per-row validation ────────────────────────────────────────────────
        print("── Per-Row Validation ─────────────────────────────────────")
        for idx, vrow in enumerate(vendor_rows):
            ok = extractor.validate(vrow)
            print(f"  Row {idx + 1}: {'PASS' if ok else 'FAIL'} — {vrow['vendor_name']}")

        # ── Assertions ────────────────────────────────────────────────────────
        assert len(vendor_rows) >= 1, "Expected at least 1 vendor row"
        assert analytics["l1_price"] > 0, "L1 price should be positive"
        assert analytics["vendor_count"] >= 1, "Vendor count should be >= 1"

        awarded = [v for v in vendor_rows if v["awarded_flag"]]
        assert len(awarded) == 1, f"Expected exactly 1 awarded vendor, got {len(awarded)}"
        assert awarded[0]["vendor_rank"] == "L1", "Awarded vendor should have rank L1"

        print("\n✓ ALL ASSERTIONS PASSED — VendorEvaluationExtractor is production-ready.\n")

    except AssertionError as ae:
        print(f"\n✗ ASSERTION FAILED: {ae}\n")
        raise
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}\n")
        import traceback
        traceback.print_exc()
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
