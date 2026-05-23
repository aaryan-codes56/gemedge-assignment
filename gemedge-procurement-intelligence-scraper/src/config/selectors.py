from typing import Dict, List, Tuple
from selenium.webdriver.common.by import By


class GeMSelectors:
    """
    Unified fallback locator catalog for the Government e-Marketplace (GeM) Bids Portal.
    Organizes selectors by functional context.
    Each key holds a list of ordered fallback locators (Tuple[By, str]) to ensure anti-fragility.
    """
    VERSION: str = "v1.0.0"

    # 1. Portal Landing/Common Elements
    LANDING: Dict[str, List[Tuple[str, str]]] = {
        "logo": [
            (By.CSS_SELECTOR, "a.logo img"),
            (By.XPATH, "//img[contains(@src, 'logo')]"),
            (By.CSS_SELECTOR, "header img")
        ],
        "page_title": [
            (By.CSS_SELECTOR, "h1"),
            (By.XPATH, "//h1[contains(text(), 'Bid')]"),
            (By.CSS_SELECTOR, "title")
        ]
    }

    # 2. Search & Filtering Controls
    FILTERS: Dict[str, List[Tuple[str, str]]] = {
        "search_input": [
            (By.ID, "searchBid"),
            (By.CSS_SELECTOR, "input[placeholder*='Search']"),
            (By.XPATH, "//input[@id='searchBid']")
        ],
        "search_submit": [
            (By.CSS_SELECTOR, "button.search-btn"),
            (By.XPATH, "//button[contains(@class, 'search')]"),
            (By.CSS_SELECTOR, "input[type='submit']")
        ],
        "filter_container": [
            (By.ID, "filter_section"),
            (By.CSS_SELECTOR, "div.filter-box"),
            (By.XPATH, "//div[contains(@class, 'filter')]")
        ],
        "status_bid_ra_checkbox": [
            (By.ID, "bidrastatus"),
            (By.CSS_SELECTOR, "input#bidrastatus"),
            (By.XPATH, "//input[@id='bidrastatus']")
        ],
        "outcome_awarded_checkbox": [
            (By.ID, "bid_awarded"),
            (By.CSS_SELECTOR, "input#bid_awarded"),
            (By.XPATH, "//input[@id='bid_awarded']")
        ],
        "ongoing_bids_checkbox": [
            (By.ID, "ongoing_bids"),
            (By.CSS_SELECTOR, "input#ongoing_bids"),
            (By.XPATH, "//input[@id='ongoing_bids']")
        ],
        "spinner_loader": [
            (By.CSS_SELECTOR, "div.loader"),
            (By.CSS_SELECTOR, ".loader"),
            (By.XPATH, "//div[contains(@class, 'loader')]")
        ]
    }

    # 3. Listing Grid/Table Elements
    LISTING_TABLE: Dict[str, List[Tuple[str, str]]] = {
        "bid_blocks": [
            (By.CSS_SELECTOR, "div.card"),
            (By.CSS_SELECTOR, "div.bid_card"),
            (By.XPATH, "//div[contains(@class, 'card')]"),
            (By.CSS_SELECTOR, "div.block_bid")
        ],
        "bid_number": [
            (By.CSS_SELECTOR, "a[href*='showBidDocument']"),
            (By.XPATH, ".//a[contains(@href, 'showBidDocument')]"),
            (By.CSS_SELECTOR, ".bid_no")
        ],
        "items": [
            (By.XPATH, ".//div[span[contains(text(), 'Items')]]/span[2]"),
            (By.CSS_SELECTOR, ".items_list"),
            (By.XPATH, ".//span[contains(@class, 'item-name')]")
        ],
        "quantity": [
            (By.XPATH, ".//div[span[contains(text(), 'Quantity')]]/span[2]"),
            (By.CSS_SELECTOR, ".quantity_span")
        ],
        "start_date": [
            (By.XPATH, ".//span[contains(text(), 'Start Date')]/following-sibling::span"),
            (By.XPATH, ".//*[contains(text(), 'Start Date')]/..")
        ],
        "end_date": [
            (By.XPATH, ".//span[contains(text(), 'End Date')]/following-sibling::span"),
            (By.XPATH, ".//*[contains(text(), 'End Date')]/..")
        ]
    }

    # 4. Pagination Elements
    PAGINATION: Dict[str, List[Tuple[str, str]]] = {
        "next_button": [
            (By.CSS_SELECTOR, "a.page-link.next"),
            (By.CSS_SELECTOR, "a.next"),
            (By.CSS_SELECTOR, "li.next a"),
            (By.XPATH, "//a[contains(text(), 'Next')]"),
            (By.CSS_SELECTOR, "a[rel='next']")
        ],
        "prev_button": [
            (By.CSS_SELECTOR, "a.page-link.prev"),
            (By.CSS_SELECTOR, "li.prev a"),
            (By.XPATH, "//a[contains(text(), 'Prev')]")
        ],
        "active_page": [
            (By.CSS_SELECTOR, "span.current"),
            (By.CSS_SELECTOR, "li.active a"),
            (By.XPATH, "//li[contains(@class, 'active')]/a")
        ]
    }

    # 5. Bid Detail Page Elements
    BID_DETAIL: Dict[str, List[Tuple[str, str]]] = {
        "tender_value": [
            (By.XPATH, "//*[contains(text(), 'Tender Value')]/following-sibling::td"),
            (By.XPATH, "//*[contains(text(), 'Estimated')]/following-sibling::span")
        ],
        "buyer_department": [
            (By.XPATH, "//*[contains(text(), 'Ministry')]/following-sibling::span"),
            (By.CSS_SELECTOR, ".buyer-dept")
        ]
    }

    # 6. Evaluation Details Elements
    EVALUATION_DETAIL: Dict[str, List[Tuple[str, str]]] = {
        "qualified_vendors": [
            (By.CSS_SELECTOR, "table.qualified_table tr"),
            (By.XPATH, "//tr[td[contains(text(), 'Qualified')]]")
        ],
        "disqualified_vendors": [
            (By.CSS_SELECTOR, "table.disqualified_table tr"),
            (By.XPATH, "//tr[td[contains(text(), 'Disqualified')]]")
        ]
    }


def get_selector_fallback(
    category_map: Dict[str, List[Tuple[str, str]]],
    key: str
) -> List[Tuple[str, str]]:
    """
    Safety helper to fetch a list of fallback locators for a specific key.
    """
    if key in category_map:
        return category_map[key]
    return []
