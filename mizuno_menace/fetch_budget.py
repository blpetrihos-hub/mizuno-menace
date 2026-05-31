"""Adaptive fetch limits balancing scan depth vs runtime."""

from __future__ import annotations

# Foot-store product pages
DEFAULT_MAX_PAGES = 0          # 0 = auto from --top
MIN_FOOTSTORE_PAGES = 50
MAX_FOOTSTORE_PAGES = 280
PAGES_PER_TOP_DEAL = 7         # top 30 → ~210 pages auto

# Mizuno USA official price lookups (network)
MAX_MIZUNO_FETCHES_PER_RUN = 12
MAX_MIZUNO_EU_FETCHES_PER_RUN = 12
MIZUNO_FETCH_DELAY = 0.25

# eBay Browse API (per query in scrape mode)
MIN_EBAY_RESULTS = 20
MAX_EBAY_RESULTS = 50
EBAY_RESULTS_PER_TOP = 2       # top 30 → 60 → capped at 50

# Early stop once enough distinct products are collected
MIN_PAGES_BEFORE_EARLY_STOP = 40
TARGET_PRODUCTS_MULTIPLIER = 3.0  # collect ~3× top N deal products before early stop


def effective_max_pages(requested: int, top: int) -> int:
    """Scale foot-store page budget from deal count; honour explicit overrides."""
    if requested > 0:
        return min(requested, MAX_FOOTSTORE_PAGES)
    auto = max(MIN_FOOTSTORE_PAGES, min(MAX_FOOTSTORE_PAGES, top * PAGES_PER_TOP_DEAL))
    return auto


def target_product_count(top: int) -> int:
    """Stop foot-store early after this many distinct product names."""
    return max(20, int(top * TARGET_PRODUCTS_MULTIPLIER))


def ebay_scan_limit(top: int, max_pages: int) -> int:
    """eBay results per apparel/shoe query."""
    _ = max_pages
    return min(MAX_EBAY_RESULTS, max(MIN_EBAY_RESULTS, top * EBAY_RESULTS_PER_TOP))
