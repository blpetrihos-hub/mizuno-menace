"""Tiered reference-price waterfall for discount calculations."""

from __future__ import annotations

import statistics
import time
from collections import defaultdict

from .fetch_budget import MAX_MIZUNO_FETCHES_PER_RUN
from .models import Listing
from .msrp_lookup import lookup_estimated_msrp
from .mizuno_usa import MizunoUsaClient
from .reference_cache import PriceEntry, ReferenceCache
from .style_extractor import likely_mizuno_usa_style, normalize_style_id, resolve_style_id

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
        self.mizuno = mizuno or MizunoUsaClient(
            cache=self.cache,
            max_fetches_per_run=MAX_MIZUNO_FETCHES_PER_RUN,
        )
        self._official_by_style: dict[str, PriceEntry] = {}
        self._catalog_by_style: dict[str, PriceEntry] = {}

    def finalize_listings(self, listings: list[Listing]) -> None:
        """Run all tiers once; dedupe Mizuno fetches by style id."""
        self._ensure_style_ids(listings)
        self._prefetch_references(listings)
        self._apply_cached_tiers(listings)
        self._apply_market_references(listings)
        self._apply_late_tiers(listings)

    def _ensure_style_ids(self, listings: list[Listing]) -> None:
        for listing in listings:
            if not listing.style_id:
                listing.style_id = resolve_style_id(
                    url=listing.url,
                    title=listing.title,
                )

    def _prefetch_references(self, listings: list[Listing]) -> None:
        hints: dict[str, str] = {}
        for listing in listings:
            style_id = normalize_style_id(listing.style_id)
            if not style_id:
                continue
            hint = listing.product_name or listing.title
            hints.setdefault(style_id, hint)

        for style_id, hint in sorted(hints.items()):
            cached = self.cache.get_official(style_id)
            if cached:
                self._official_by_style[style_id] = cached
                continue

            catalog = self.cache.get_catalog(style_id)
            if catalog:
                self._catalog_by_style[style_id] = catalog

            if not likely_mizuno_usa_style(style_id):
                continue
            if self.cache.is_miss(style_id):
                continue

            entry = self.mizuno.lookup(style_id, title_hint=hint)
            if entry:
                self._official_by_style[style_id] = entry

    def _apply_cached_tiers(self, listings: list[Listing]) -> None:
        for listing in listings:
            if listing.reference_source:
                continue
            style_id = normalize_style_id(listing.style_id)

            official = self._official_by_style.get(style_id)
            if official:
                self._apply_entry(listing, official, estimated=False)
                continue

            catalog = self._catalog_by_style.get(style_id) or self.cache.get_catalog(style_id)
            if catalog:
                self._apply_entry(listing, catalog, estimated=False)
                continue

            if listing.original_price and listing.original_price > listing.total:
                self._apply(
                    listing,
                    price=listing.original_price,
                    source="ebay_list",
                    as_of="",
                    estimated=False,
                )

    def _apply_late_tiers(self, listings: list[Listing]) -> None:
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


def reference_source_counts(listings: list[Listing]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for listing in listings:
        key = listing.reference_source or "none"
        counts[key] += 1
    return dict(counts)
