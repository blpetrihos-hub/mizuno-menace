"""Sizing filters and eBay search text for deal discovery."""

from __future__ import annotations

APPAREL_SIZE = "M"
SHOE_SIZE_US = "11"
SHOE_SIZE_EU = "45"

APPAREL_SIZE_OPTIONS: tuple[str, ...] = ("XS", "S", "M", "L", "XL", "XXL")
SHOE_SIZE_US_OPTIONS: tuple[str, ...] = (
    "7",
    "7.5",
    "8",
    "8.5",
    "9",
    "9.5",
    "10",
    "10.5",
    "11",
    "11.5",
    "12",
    "12.5",
    "13",
    "14",
    "15",
)

_APPAREL_QUERY_WORD = {
    "XS": "xsmall",
    "S": "small",
    "M": "medium",
    "L": "large",
    "XL": "xlarge",
    "XXL": "xxlarge",
}

# Approximate US mens → EU for optional foot-store filtering.
_US_TO_EU_SHOE: dict[str, str] = {
    "7": "40",
    "7.5": "40.5",
    "8": "41",
    "8.5": "42",
    "9": "42.5",
    "9.5": "43",
    "10": "44",
    "10.5": "44.5",
    "11": "45",
    "11.5": "45.5",
    "12": "46",
    "12.5": "47",
    "13": "47.5",
    "14": "48.5",
    "15": "49",
}


def normalize_apparel_size(size: str) -> str:
    key = (size or APPAREL_SIZE).strip().upper()
    return key if key in APPAREL_SIZE_OPTIONS else APPAREL_SIZE


def normalize_shoe_size_us(size: str) -> str:
    key = (size or SHOE_SIZE_US).strip()
    return key if key in SHOE_SIZE_US_OPTIONS else SHOE_SIZE_US


def us_shoe_to_eu(us: str) -> str:
    us = normalize_shoe_size_us(us)
    return _US_TO_EU_SHOE.get(us, SHOE_SIZE_EU)


def ebay_apparel_query(size: str = APPAREL_SIZE) -> str:
    size = normalize_apparel_size(size)
    word = _APPAREL_QUERY_WORD.get(size, size.lower())
    return f"Mizuno {word} mens NWT"


def ebay_shoe_query(shoe_size_us: str = SHOE_SIZE_US) -> str:
    us = normalize_shoe_size_us(shoe_size_us)
    return f"Mens Mizuno size {us} new"


def scan_description(apparel_size: str, shoe_size_us: str) -> str:
    """User-facing summary of what the scan will search."""
    apparel = normalize_apparel_size(apparel_size)
    shoe = normalize_shoe_size_us(shoe_size_us)
    return (
        f"Searches eBay for New With Tags, Buy It Now Mizuno listings — "
        f"mens size {apparel} apparel and mens US size {shoe} shoes — "
        f"then opens a ranked HTML report."
    )


# Backward-compatible defaults
EBAY_APPAREL_QUERY = ebay_apparel_query()
EBAY_SHOE_QUERY = ebay_shoe_query()
