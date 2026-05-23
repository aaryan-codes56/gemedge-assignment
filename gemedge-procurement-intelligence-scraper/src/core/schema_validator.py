import re
from dataclasses import dataclass, field
from typing import Dict, Any, List, Set, Tuple

from src.utils.logger import get_logger

logger = get_logger("schema_validator")


@dataclass
class ValidationReport:
    """Holds the results of a schema validation pass."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class SchemaValidator:
    """
    Validates dynamic procurement intelligence records (listings, results, vendors)
    prior to physical persistence, guaranteeing schema alignment and high data hygiene.
    """

    def __init__(self) -> None:
        self.seen_bid_numbers: Set[str] = set()

    def reset(self) -> None:
        """Resets the state of seen bids (for isolated session runs)."""
        self.seen_bid_numbers.clear()

    def validate_bid_listing(self, record: Dict[str, Any]) -> ValidationReport:
        """
        Validates the schema for raw bid listing items captured from the GeM portal.
        """
        errors = []
        warnings = []

        # 1. Required Field Checks
        required_fields = ["bid_number", "start_date", "end_date"]
        for rf in required_fields:
            if rf not in record or record[rf] is None:
                errors.append(f"Missing required listing field: '{rf}'")
                continue
            
            # String completeness check
            if isinstance(record[rf], str) and not record[rf].strip():
                errors.append(f"Required listing field '{rf}' cannot be blank.")

        # If missing critical keys, return immediately
        if errors:
            return ValidationReport(is_valid=False, errors=errors, warnings=warnings)

        bid_no = str(record["bid_number"]).strip()

        # 2. Duplicate Check
        if bid_no in self.seen_bid_numbers:
            warnings.append(f"Duplicate bid number detected in active session dataset: {bid_no}")
        else:
            self.seen_bid_numbers.add(bid_no)

        # 3. Format/Pattern validations
        # Standard GeM Bids usually match GEM/YYYY/[B|R]/xxxxxx
        if not re.search(r"GEM/\d{4}/[A-Z]/\d+", bid_no):
            warnings.append(f"Bid number '{bid_no}' does not conform to standard GeM ID pattern (GEM/YYYY/X/digits).")

        # 4. Optional Type / Format checks
        quantity = record.get("quantity")
        if quantity is not None:
            try:
                numeric_qty = float(quantity)
                if numeric_qty < 0:
                    errors.append(f"Listing quantity cannot be negative. Value: {quantity}")
            except (ValueError, TypeError):
                errors.append(f"Invalid listing quantity type. Expected numeric, got: {type(quantity)} ({quantity})")

        # Item array completeness
        items = record.get("items")
        if items is not None:
            if not isinstance(items, list):
                errors.append(f"Listing field 'items' must be a list, got {type(items)}")
            elif not items:
                warnings.append("Bid listing matches 0 items in descriptive category list.")

        return ValidationReport(
            is_valid=(len(errors) == 0),
            errors=errors,
            warnings=warnings
        )

    def validate_bid_result(self, record: Dict[str, Any]) -> ValidationReport:
        """
        Validates the schema for final bid results (awards, winners, final contract value).
        """
        errors = []
        warnings = []

        required_fields = ["bid_number", "winner_name", "awarded_value"]
        for rf in required_fields:
            if rf not in record or record[rf] is None:
                errors.append(f"Missing required result field: '{rf}'")
                continue

            if isinstance(record[rf], str) and not record[rf].strip():
                errors.append(f"Required result field '{rf}' cannot be blank.")

        if errors:
            return ValidationReport(is_valid=False, errors=errors, warnings=warnings)

        # Awarded value sanity checks
        val = record["awarded_value"]
        try:
            numeric_val = float(val)
            if numeric_val <= 0:
                errors.append(f"Awarded price contract value must be positive. Got: {numeric_val}")
        except (ValueError, TypeError):
            errors.append(f"Malformed price contract detected. Could not parse to float: {val}")

        return ValidationReport(
            is_valid=(len(errors) == 0),
            errors=errors,
            warnings=warnings
        )

    def validate_vendor_detail(self, record: Dict[str, Any]) -> ValidationReport:
        """
        Validates the schema for vendor profiling and contact items.
        """
        errors = []
        warnings = []

        required_fields = ["vendor_id", "vendor_name"]
        for rf in required_fields:
            if rf not in record or record[rf] is None:
                errors.append(f"Missing required vendor field: '{rf}'")
                continue

            if isinstance(record[rf], str) and not record[rf].strip():
                errors.append(f"Required vendor field '{rf}' cannot be blank.")

        if errors:
            return ValidationReport(is_valid=False, errors=errors, warnings=warnings)

        # Email check warning (if present)
        email = record.get("contact_email")
        if email:
            if not re.match(r"[^@]+@[^@]+\.[^@]+", str(email)):
                warnings.append(f"Vendor contact email does not match common layout: '{email}'")

        return ValidationReport(
            is_valid=(len(errors) == 0),
            errors=errors,
            warnings=warnings
        )
