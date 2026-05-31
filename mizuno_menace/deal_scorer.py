"""Indexable deal scores from eBay peer prices — no keyword MSRP guesses."""

from __future__ import annotations

import statistics
import time
from collections import defaultdict

from .models import Listing
from .msrp_lookup import normalize_product_name
from .style_extractor import normalize_style_id

MIN_PEER_STYLE_SAMPLES = 2
MIN_PEER_PRODUCT_SAMPLES = 3
MIN_PEER_CATEGORY_SAMPLES = 5


def score_deals(listings: list[Listing]) -> None:
    """Fill reference + deal_index for listings using eBay peer comparables."""
    ebay = [lst for lst in listings if lst.source == "eBay"]
    if ebay:
        style_totals: dict[str, list[float]] = defaultdict(list)
        product_totals: dict[str, list[float]] = defaultdict(list)
        category_totals: dict[str, list[float]] = defaultdict(list)

        for lst in ebay:
            style_id = normalize_style_id(lst.style_id)
            if style_id:
                style_totals[style_id].append(lst.total)
            name = lst.product_name or normalize_product_name(lst.title)
            if name:
                product_totals[name].append(lst.total)
            kind = lst.kind or "all"
            category_totals[kind].append(lst.total)

        style_median = _medians(style_totals, MIN_PEER_STYLE_SAMPLES)
        product_median = _medians(product_totals, MIN_PEER_PRODUCT_SAMPLES)
        category_median = _medians(category_totals, MIN_PEER_CATEGORY_SAMPLES)
        today = time.strftime("%Y-%m-%d")

        for lst in listings:
            if lst.reference_source in (
                "mizuno_official",
                "mizuno_eu",
                "catalog",
                "watchlist",
                "ebay_list",
            ):
                continue

            style_id = normalize_style_id(lst.style_id)
            name = lst.product_name or normalize_product_name(lst.title)
            kind = lst.kind or "all"

            ref: float | None = None
            source = ""

            if style_id and style_id in style_median:
                ref = style_median[style_id]
                source = "peer_style"
            elif name and name in product_median:
                ref = product_median[name]
                source = "peer_product"
            elif kind in category_median:
                ref = category_median[kind]
                source = "peer_category"

            if ref is None or ref <= lst.total:
                continue

            lst.msrp = round(ref, 2)
            lst.reference_source = source
            lst.reference_as_of = today
            lst.estimated = False

    for lst in listings:
        if lst.deal_index is None and lst.reference_source:
            _sync_deal_index(lst)


def _medians(pools: dict[str, list[float]], min_samples: int) -> dict[str, float]:
    out: dict[str, float] = {}
    for key, prices in pools.items():
        if len(prices) >= min_samples:
            out[key] = round(statistics.median(prices), 2)
    return out


def _sync_deal_index(listing: Listing) -> None:
    ref = listing.reference_price
    if ref is None or ref <= 0:
        listing.deal_index = None
        return
    listing.deal_index = round((ref - listing.total) / ref * 100, 1)
