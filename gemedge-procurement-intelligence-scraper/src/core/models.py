from dataclasses import dataclass, asdict, field
from typing import Dict, Any, List, Optional


@dataclass
class BidListing:
    """
    Unified dataclass representing a parsed procurement Bid listing record from the GeM portal.
    Encapsulates core listing attributes for downstream analytics.
    """
    bid_id: str
    item_category: str
    department: str
    buyer_name: str
    quantity: int
    bid_value: float
    start_date: str
    end_date: str
    bid_status: str
    bid_link: str

    @property
    def bid_number(self) -> str:
        """Compatibility property matching SchemaValidator's naming expectations."""
        return self.bid_id

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the dataclass instance to a dictionary representation.
        Enriches outputs to seamlessly align with the schema validation engine.
        """
        data = asdict(self)
        data["bid_number"] = self.bid_id
        # Split categories to construct standard items array for SchemaValidator check
        data["items"] = [cat.strip() for cat in self.item_category.split(",") if cat.strip()]
        return data


@dataclass
class BidResult:
    """
    Unified dataclass representing detailed bid results parsed from GeM detail views.
    Includes buyer details, technical evaluation sellers, and financial evaluation ranks.
    """
    bid_id: str
    bid_status: str
    bid_validity: str
    start_date: str
    end_date: str
    opening_date: str
    contract_duration: str
    ministry: str
    department: str
    organisation: str
    office: str
    technical_sellers: List[Dict[str, Any]]
    financial_sellers: List[Dict[str, Any]]
    winner_name: str = ""
    awarded_value: float = 0.0

    @property
    def bid_number(self) -> str:
        """Compatibility property matching SchemaValidator's naming expectations."""
        return self.bid_id

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the dataclass instance to a dictionary representation.
        Enriches outputs to seamlessly align with the schema validation engine.
        """
        data = asdict(self)
        data["bid_number"] = self.bid_id
        return data


@dataclass
class VendorDetail:
    """
    Intelligence-ready dataclass representing a single vendor's evaluation record
    extracted from GeM procurement bid evaluation tables.

    Captures vendor identity, qualification status, pricing, rank, and anomaly flags
    for downstream procurement analytics and competition intelligence.
    """
    bid_id: str
    vendor_name: str
    vendor_rank: str                      # e.g. "L1", "L2", "L3", "N/A"
    quoted_price: float                   # Cleaned decimal price in INR
    technically_qualified: bool           # True if seller passed technical evaluation
    financially_qualified: bool           # True if seller reached financial round
    bid_status: str                       # Overall bid status at extraction time
    remarks: str                          # Any status text / disqualification notes
    evaluation_round: str                 # "Technical" | "Financial" | "Both"
    awarded_flag: bool                    # True only for L1 winner

    # Pricing spread analytics (populated by VendorEvaluationExtractor)
    l1_price: float = 0.0
    l1_vs_vendor_diff: float = 0.0       # Absolute price gap vs L1
    l1_vs_vendor_pct: float = 0.0        # % difference from L1 price
    avg_quote: float = 0.0               # Average quoted price in this bid
    price_spread_pct: float = 0.0        # (max - min) / min * 100

    # Anomaly detection flags
    anomaly_single_vendor: bool = False
    anomaly_duplicate_price: bool = False
    anomaly_missing_rank: bool = False
    anomaly_abnormal_spread: bool = False
    anomaly_low_participation: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Converts dataclass to a flat analytics-ready dictionary."""
        return asdict(self)
