"""Run all configured sources for each product and collect results."""

from __future__ import annotations

from .models import ItemResult, Listing, Product
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
            listings.extend(found)

        # Lowest total (price + shipping) first.
        listings.sort(key=lambda lst: lst.total)
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
