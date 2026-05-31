"""Tiered reference-price waterfall for discount calculations."""

from __future__ import annotations

import statistics
import time
from collections import defaultdict

from .models import Listing
from .msrp_lookup import lookup_estimated_msrp
from .mizuno_usa import MizunoUsaClient
from .reference_cache import PriceEntry, ReferenceCache
from .style_extractor import normalize_style_id, resolve_style_id

MIN_MARKET_SAMPLES = 3

SOURCE_LABELS = {
    "mizuno_official": "Mizuno MSRP",
    "catalog": "Catalog MSRP",
    "market": "Market reference",
    "ebay_list": "vs seller list",
    "estimated": "Estimated MSRP",
}


class ReferenceResolver:
    """Apply the tiered MSRP / reference-price waterfall to listings."""

    def __init__(
        self,
        cache: ReferenceCache | None = None,
        mizuno: MizunoUsaClient | None = None,
    ):
        self.cache = cache or ReferenceCache()
        self.mizuno = mizuno or MizunoUsaClient(cache=self.cache)

    def enrich_listing(self, listing: Listing) -> None:
        """Resolve style id and tiers 1–2, 4 for a single listing."""
        if not listing.style_id:
            listing.style_id = resolve_style_id(
                url=listing.url,
                title=listing.title,
            )

        if listing.reference_source:
            return

        style_id = normalize_style_id(listing.style_id)
        title_hint = listing.product_name or listing.title

        if style_id:
            official = self.mizuno.lookup(style_id, title_hint=title_hint)
            if official:
                self._apply_entry(listing, official, estimated=False)
                return

            catalog = self.cache.get_catalog(style_id)
            if catalog:
                self._apply_entry(listing, catalog, estimated=False)
                return

        if listing.original_price and listing.original_price > listing.total:
            self._apply(
                listing,
                price=listing.original_price,
                source="ebay_list",
                as_of="",
                estimated=False,
            )

    def finalize_listings(self, listings: list[Listing]) -> None:
        """Run market tier, estimated fallback, and leave unknowns unranked."""
        for listing in listings:
            self.enrich_listing(listing)

        self._apply_market_references(listings)

        for listing in listings:
            if listing.reference_source:
                continue
            if listing.original_price and listing.original_price > listing.total:
                self._apply(
                    listing,
                    price=listing.original_price,
                    source="ebay_list",
                    as_of="",
                    estimated=False,
                )
                continue

            estimated = lookup_estimated_msrp(listing.title)
            if estimated:
                self._apply(
                    listing,
                    price=estimated,
                    source="estimated",
                    as_of="",
                    estimated=True,
                )

    def _apply_market_references(self, listings: list[Listing]) -> None:
        anchors: dict[str, list[float]] = defaultdict(list)
        for listing in listings:
            if listing.reference_source:
                continue
            style_id = normalize_style_id(listing.style_id)
            if not style_id:
                continue
            if listing.source == "foot-store":
                anchors[style_id].append(listing.total)
            if listing.original_price and listing.original_price > 0:
                anchors[style_id].append(listing.original_price)

        medians: dict[str, float] = {}
        for style_id, prices in anchors.items():
            if len(prices) < MIN_MARKET_SAMPLES:
                continue
            medians[style_id] = round(statistics.median(prices), 2)

        if not medians:
            return

        today = time.strftime("%Y-%m-%d")
        for listing in listings:
            if listing.reference_source:
                continue
            style_id = normalize_style_id(listing.style_id)
            median = medians.get(style_id)
            if median is None:
                continue
            self._apply(
                listing,
                price=median,
                source="market",
                as_of=today,
                estimated=False,
            )

    def _apply_entry(
        self,
        listing: Listing,
        entry: PriceEntry,
        *,
        estimated: bool,
    ) -> None:
        self._apply(
            listing,
            price=entry.msrp,
            source=entry.source,
            as_of=entry.as_of_date,
            estimated=estimated,
        )

    @staticmethod
    def _apply(
        listing: Listing,
        *,
        price: float,
        source: str,
        as_of: str,
        estimated: bool,
    ) -> None:
        if price <= 0:
            return
        listing.msrp = round(price, 2)
        listing.reference_source = source
        listing.reference_as_of = as_of
        listing.estimated = estimated


def apply_references(listings: list[Listing]) -> None:
    """Convenience helper used by scrape paths."""
    ReferenceResolver().finalize_listings(listings)
