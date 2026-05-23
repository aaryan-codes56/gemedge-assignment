from dataclasses import dataclass, asdict
from typing import Dict, Any, List


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
