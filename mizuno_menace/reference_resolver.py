"""Reference prices for deal scoring — official MSRP and eBay seller list only."""

from __future__ import annotations

from collections import defaultdict

from .fetch_budget import MAX_MIZUNO_EU_FETCHES_PER_RUN, MAX_MIZUNO_FETCHES_PER_RUN
from .models import Listing
from .msrp_lookup import lookup_estimated_msrp
from .mizuno_eu import MizunoEuClient
from .mizuno_usa import MizunoUsaClient
from .reference_cache import PriceEntry, ReferenceCache
from .style_extractor import (
    likely_mizuno_eu_style,
    likely_mizuno_usa_style,
    normalize_style_id,
    resolve_style_id,
)

SOURCE_LABELS = {
    "mizuno_official": "Mizuno MSRP",
    "mizuno_eu": "Mizuno EU MSRP",
    "catalog": "Catalog MSRP",
    "ebay_list": "vs seller list",
    "peer_style": "Peer median (style)",
    "peer_product": "Peer median (product)",
    "peer_category": "Category median",
    "estimated": "Estimated MSRP",
}


class ReferenceResolver:
    """Apply official MSRP + per-listing eBay list prices (no keyword guesses)."""

    def __init__(
        self,
        cache: ReferenceCache | None = None,
        mizuno: MizunoUsaClient | None = None,
        *,
        allow_estimated: bool = False,
    ):
        self.cache = cache or ReferenceCache()
        self.mizuno_usa = mizuno or MizunoUsaClient(
            cache=self.cache,
            max_fetches_per_run=MAX_MIZUNO_FETCHES_PER_RUN,
        )
        self.mizuno_eu = MizunoEuClient(
            cache=self.cache,
            max_fetches_per_run=MAX_MIZUNO_EU_FETCHES_PER_RUN,
        )
        self.allow_estimated = allow_estimated
        self._official_by_style: dict[str, PriceEntry] = {}
        self._eu_by_style: dict[str, PriceEntry] = {}
        self._catalog_by_style: dict[str, PriceEntry] = {}

    def finalize_listings(self, listings: list[Listing]) -> None:
        self._ensure_style_ids(listings)
        self._prefetch_references(listings)
        self._apply_cached_tiers(listings)
        self._apply_ebay_list_prices(listings)
        if self.allow_estimated:
            self._apply_estimated(listings)

    def _ensure_style_ids(self, listings: list[Listing]) -> None:
        for listing in listings:
            if not listing.style_id:
                listing.style_id = resolve_style_id(
                    url=listing.url,
                    title=listing.title,
                )

    def _prefetch_references(self, listings: list[Listing]) -> None:
        hints: dict[str, str] = {}
        currencies: dict[str, str] = {}
        for listing in listings:
            style_id = normalize_style_id(listing.style_id)
            if not style_id:
                continue
            hint = listing.product_name or listing.title
            hints.setdefault(style_id, hint)
            currencies.setdefault(style_id, listing.currency or "USD")

        for style_id, hint in sorted(hints.items()):
            target = currencies.get(style_id, "USD")

            eu_cached = self.cache.get_eu(style_id)
            if eu_cached:
                self._eu_by_style[style_id] = self.mizuno_eu._for_currency(
                    eu_cached, target
                )

            us_cached = self.cache.get_official(style_id)
            if us_cached:
                self._official_by_style[style_id] = us_cached

            catalog = self.cache.get_catalog(style_id)
            if catalog:
                self._catalog_by_style[style_id] = catalog

            if likely_mizuno_usa_style(style_id) and not self._official_by_style.get(style_id):
                if not self.cache.is_miss(style_id):
                    entry = self.mizuno_usa.lookup(style_id, title_hint=hint)
                    if entry:
                        self._official_by_style[style_id] = entry

            if likely_mizuno_eu_style(style_id) and not self._eu_by_style.get(style_id):
                if not self.cache.is_eu_miss(style_id):
                    entry = self.mizuno_eu.lookup(
                        style_id,
                        title_hint=hint,
                        target_currency=target,
                    )
                    if entry:
                        self._eu_by_style[style_id] = entry

    def _apply_cached_tiers(self, listings: list[Listing]) -> None:
        for listing in listings:
            if listing.reference_source:
                continue
            style_id = normalize_style_id(listing.style_id)

            official = self._official_by_style.get(style_id)
            if official:
                self._apply_entry(listing, official, estimated=False)
                continue

            eu = self._eu_by_style.get(style_id)
            if eu:
                self._apply_entry(listing, eu, estimated=False)
                continue

            catalog = self._catalog_by_style.get(style_id) or self.cache.get_catalog(style_id)
            if catalog:
                self._apply_entry(
                    listing,
                    self._entry_for_currency(catalog, listing.currency or "USD"),
                    estimated=False,
                )

    def _apply_ebay_list_prices(self, listings: list[Listing]) -> None:
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

    def _apply_estimated(self, listings: list[Listing]) -> None:
        for listing in listings:
            if listing.reference_source:
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

    def _entry_for_currency(self, entry: PriceEntry, target: str) -> PriceEntry:
        from .currency_util import to_usd

        target = (target or "USD").upper()
        if entry.currency.upper() == target:
            return entry
        if target == "USD" and entry.currency.upper() != "USD":
            return PriceEntry(
                style_id=entry.style_id,
                msrp=to_usd(entry.msrp, entry.currency),
                currency="USD",
                source=entry.source,
                label=entry.label,
                url=entry.url,
                title=entry.title,
                updated_at=entry.updated_at,
            )
        return entry

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


def apply_references(listings: list[Listing], *, allow_estimated: bool = False) -> None:
    """Official MSRP + eBay list prices; peer scoring runs separately."""
    ReferenceResolver(allow_estimated=allow_estimated).finalize_listings(listings)


def reference_source_counts(listings: list[Listing]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for listing in listings:
        key = listing.reference_source or "none"
        counts[key] += 1
    return dict(counts)
