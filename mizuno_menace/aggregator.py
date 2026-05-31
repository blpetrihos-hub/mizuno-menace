"""Run all configured sources for each product and collect results."""

from __future__ import annotations

from collections import defaultdict

from .fetch_budget import (
    effective_max_pages,
    ebay_scan_limit,
    target_product_count,
)
from .models import ItemResult, Listing, Product
from .reference_resolver import apply_references, reference_source_counts
from .search_criteria import APPAREL_SIZE, SHOE_SIZE_EU, SHOE_SIZE_US
from .sources.base import PriceSource


class Aggregator:
    def __init__(self, sources: list[PriceSource], limit: int = 10, use_aspects: bool = True):
        self.sources = [s for s in sources if s.available]
        self.limit = limit
        self.use_aspects = use_aspects
        self.last_scan_stats: dict = {}

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
        max_pages: int = 0,
        top: int = 30,
    ) -> list[ItemResult]:
        """Discover deals by scraping sources; group color variants under one product."""
        page_budget = effective_max_pages(max_pages, top)
        product_target = target_product_count(top)
        ebay_limit = ebay_scan_limit(top, page_budget)

        raw: list[Listing] = []
        scan_errors: list[str] = []
        for source in self.sources:
            scan = getattr(source, "scan_deals", None)
            if not scan:
                continue
            try:
                kwargs: dict = {
                    "apparel_size": apparel_size,
                    "shoe_size_us": shoe_size_us,
                    "shoe_size_eu": shoe_size_eu,
                    "max_pages": page_budget,
                }
                if source.name == "foot-store":
                    kwargs["target_products"] = product_target
                if source.name == "eBay":
                    kwargs["ebay_limit"] = ebay_limit
                found = scan(**kwargs)
            except Exception as exc:
                scan_errors.append(f"{source.name}: {exc}")
                continue
            raw.extend(found)

        apply_references(raw)
        self.last_scan_stats = {
            "listings": len(raw),
            "page_budget": page_budget,
            "ebay_limit": ebay_limit,
            "references": reference_source_counts(raw),
            "errors": scan_errors,
        }
        for source in self.sources:
            pages = getattr(source, "last_pages_scanned", 0)
            if pages:
                self.last_scan_stats["footstore_pages"] = pages

        by_product: dict[str, list[Listing]] = defaultdict(list)
        skipped = 0
        for lst in raw:
            if (lst.discount_pct or 0) <= 0:
                skipped += 1
                continue
            key = lst.product_name or lst.title
            by_product[key].append(lst)

        self.last_scan_stats["products_ranked"] = len(by_product)
        self.last_scan_stats["skipped_no_discount"] = skipped

        results: list[ItemResult] = []
        for name, listings in by_product.items():
            listings.sort(key=lambda lst: lst.total)
            results.append(
                ItemResult(query=name, product_name=name, listings=listings)
            )
        results.sort(
            key=lambda r: (r.best_discount.discount_pct if r.best_discount else 0),
            reverse=True,
        )
        return results
