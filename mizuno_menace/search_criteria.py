"""Sizing filters and eBay search text for deal discovery."""

from __future__ import annotations

from typing import Literal

APPAREL_SIZE = "M"
SHOE_SIZE_US = "11"
SHOE_SIZE_EU = "45"

SearchScope = Literal["both", "apparel", "shoes"]
VALID_SEARCH_SCOPES: tuple[str, ...] = ("both", "apparel", "shoes")
DEFAULT_SEARCH_SCOPE: SearchScope = "both"

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


def normalize_search_scope(scope: str) -> str:
    key = (scope or DEFAULT_SEARCH_SCOPE).strip().lower()
    return key if key in VALID_SEARCH_SCOPES else DEFAULT_SEARCH_SCOPE


def normalize_custom_query(query: str) -> str:
    return (query or "").strip()


def ebay_apparel_query(size: str = APPAREL_SIZE) -> str:
    size = normalize_apparel_size(size)
    word = _APPAREL_QUERY_WORD.get(size, size.lower())
    return f"Mizuno {word} mens NWT"


def ebay_shoe_query(shoe_size_us: str = SHOE_SIZE_US) -> str:
    us = normalize_shoe_size_us(shoe_size_us)
    return f"Mens Mizuno size {us} new"


def us_shoe_to_eu(us: str) -> str:
    us = normalize_shoe_size_us(us)
    return _US_TO_EU_SHOE.get(us, SHOE_SIZE_EU)


def plan_scan_searches(
    *,
    apparel_size: str = APPAREL_SIZE,
    shoe_size_us: str = SHOE_SIZE_US,
    search_scope: str = DEFAULT_SEARCH_SCOPE,
    custom_query: str = "",
) -> list[tuple[str, str, str]]:
    """Return (query, kind, size) tuples for each eBay search to run."""
    apparel_size = normalize_apparel_size(apparel_size)
    shoe_size_us = normalize_shoe_size_us(shoe_size_us)
    scope = normalize_search_scope(search_scope)
    custom = normalize_custom_query(custom_query)

    if custom:
        if scope == "apparel":
            return [(custom, "apparel", apparel_size)]
        if scope == "shoes":
            return [(custom, "shoe", shoe_size_us)]
        return [(custom, "", "")]

    plans: list[tuple[str, str, str]] = []
    if scope in ("both", "apparel"):
        plans.append((ebay_apparel_query(apparel_size), "apparel", apparel_size))
    if scope in ("both", "shoes"):
        plans.append((ebay_shoe_query(shoe_size_us), "shoe", shoe_size_us))
    return plans


def scan_description(
    apparel_size: str,
    shoe_size_us: str,
    *,
    search_scope: str = DEFAULT_SEARCH_SCOPE,
    custom_query: str = "",
) -> str:
    """User-facing summary of what the scan will search."""
    apparel = normalize_apparel_size(apparel_size)
    shoe = normalize_shoe_size_us(shoe_size_us)
    scope = normalize_search_scope(search_scope)
    custom = normalize_custom_query(custom_query)
    prefix = (
        "Searches eBay for New With Tags, Buy It Now Mizuno listings — "
    )
    suffix = " — then opens a ranked HTML report."

    if custom:
        return (
            f'{prefix}using your custom search "{custom}" only'
            f"{suffix}"
        )

    if scope == "apparel":
        return (
            f"{prefix}mens size {apparel} apparel only"
            f"{suffix}"
        )
    if scope == "shoes":
        return (
            f"{prefix}mens US size {shoe} shoes only"
            f"{suffix}"
        )
    return (
        f"{prefix}mens size {apparel} apparel and mens US size {shoe} shoes"
        f"{suffix}"
    )


# Backward-compatible defaults
EBAY_APPAREL_QUERY = ebay_apparel_query()
EBAY_SHOE_QUERY = ebay_shoe_query()
