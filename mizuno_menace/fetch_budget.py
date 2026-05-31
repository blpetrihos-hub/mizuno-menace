"""Adaptive fetch limits balancing scan depth vs runtime."""

from __future__ import annotations

# Global depth multiplier — bump to scan more pages/results per run.
FETCH_DEPTH_MULTIPLIER = 1.5

# Foot-store product pages
DEFAULT_MAX_PAGES = 0          # 0 = auto from --top
MIN_FOOTSTORE_PAGES = round(50 * FETCH_DEPTH_MULTIPLIER)          # 75
MAX_FOOTSTORE_PAGES = round(280 * FETCH_DEPTH_MULTIPLIER)         # 420
PAGES_PER_TOP_DEAL = round(7 * FETCH_DEPTH_MULTIPLIER)            # 11

# Per-query foot-store search (watchlist mode)
MAX_FOOTSTORE_PRODUCTS = round(6 * FETCH_DEPTH_MULTIPLIER)        # 9
MAX_FOOTSTORE_CANDIDATES = round(40 * FETCH_DEPTH_MULTIPLIER)     # 60

# Mizuno official price lookups (network)
MAX_MIZUNO_FETCHES_PER_RUN = round(12 * FETCH_DEPTH_MULTIPLIER)   # 18
MAX_MIZUNO_EU_FETCHES_PER_RUN = round(12 * FETCH_DEPTH_MULTIPLIER)  # 18
MIZUNO_FETCH_DELAY = 0.25

# eBay Browse API (per query in scrape mode)
MIN_EBAY_RESULTS = round(20 * FETCH_DEPTH_MULTIPLIER)             # 30
MAX_EBAY_RESULTS = round(50 * FETCH_DEPTH_MULTIPLIER)             # 75
EBAY_RESULTS_PER_TOP = round(2 * FETCH_DEPTH_MULTIPLIER)        # 3

# Early stop once enough distinct products are collected
MIN_PAGES_BEFORE_EARLY_STOP = round(40 * FETCH_DEPTH_MULTIPLIER)  # 60
TARGET_PRODUCTS_MULTIPLIER = 3.0 * FETCH_DEPTH_MULTIPLIER       # 4.5

# Watchlist / per-product source limit
DEFAULT_SOURCE_LIMIT = round(25 * FETCH_DEPTH_MULTIPLIER)         # 38


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
