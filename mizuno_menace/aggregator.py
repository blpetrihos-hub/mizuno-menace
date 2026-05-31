"""Run all configured sources for each product and collect results."""

from __future__ import annotations

from collections import defaultdict

from .models import ItemResult, Listing, Product
from .reference_resolver import apply_references
from .search_criteria import APPAREL_SIZE, SHOE_SIZE_EU, SHOE_SIZE_US
from .sources.base import PriceSource


class Aggregator:
    def __init__(self, sources: list[PriceSource], limit: int = 10, use_aspects: bool = True):
        self.sources = [s for s in sources if s.available]
        self.limit = limit
        self.use_aspects = use_aspects

    def search_product(self, product: Product) -> ItemResult:
        listings: list[Listing] = []
        errors: list[str] = []
        category_id, aspects = product.ebay_aspects() if self.use_aspects else (None, {})
        for source in self.sources:
            try:
                found = source.search(
                    product.query,
                    limit=self.limit,
                    category_id=category_id,
                    aspects=aspects,
                )
            except Exception as exc:  # one bad source shouldn't kill the run
                errors.append(f"{source.name}: {exc}")
                continue
            for lst in found:
                lst.product_name = product.name
                if product.msrp:
                    lst.msrp = product.msrp
                    lst.reference_source = "watchlist"
            listings.extend(found)

        listings.sort(key=lambda lst: lst.total)
        apply_references(listings)
        result = ItemResult(query=product.query, product_name=product.name, listings=listings)
        if errors and not listings:
            result.error = "; ".join(errors)
        elif not listings:
            for source in self.sources:
                oos = getattr(source, "last_oos_count", 0)
                if oos:
                    result.note = (
                        f"{oos} matching listing(s) on {source.name} are out of stock."
                    )
                    break
        return result

    def search_all(self, products: list[Product]) -> list[ItemResult]:
        return [self.search_product(p) for p in products]

    def scan_deals(
        self,
        *,
        apparel_size: str = APPAREL_SIZE,
        shoe_size_us: str = SHOE_SIZE_US,
        shoe_size_eu: str = SHOE_SIZE_EU,
        max_pages: int = 350,
    ) -> list[ItemResult]:
        """Discover deals by scraping sources; group color variants under one product."""
        raw: list[Listing] = []
        for source in self.sources:
            scan = getattr(source, "scan_deals", None)
            if not scan:
                continue
            try:
                found = scan(
                    apparel_size=apparel_size,
                    shoe_size_us=shoe_size_us,
                    shoe_size_eu=shoe_size_eu,
                    max_pages=max_pages,
                )
            except Exception:
                continue
            raw.extend(found)

        apply_references(raw)

        by_product: dict[str, list[Listing]] = defaultdict(list)
        for lst in raw:
            if (lst.discount_pct or 0) <= 0:
                continue
            key = lst.product_name or lst.title
            by_product[key].append(lst)

        results: list[ItemResult] = []
        for name, listings in by_product.items():
            listings.sort(key=lambda lst: lst.total)
            results.append(
                ItemResult(query=name, product_name=name, listings=listings)
            )
        return results
