"""Offline demo source for development and testing without API keys."""

from __future__ import annotations

import hashlib

from ..models import Listing
from .base import PriceSource

COLORS = ["Black", "Navy Blue", "Royal Blue", "Grey", "White", "Red"]


class DemoSource(PriceSource):
    name = "demo"

    def __init__(self, currency: str = "USD"):
        self.currency = currency

    def search(self, query: str, limit: int = 10, **kwargs) -> list[Listing]:
        seed = int(hashlib.sha256(query.encode()).hexdigest(), 16)
        n = 3 + (seed % 4)
        base = 25 + (seed % 120)
        listings: list[Listing] = []
        for i in range(min(n, limit)):
            jitter = ((seed >> (i * 5)) % 60) - 20
            price = round(max(8.0, base + jitter + i * 3.5), 2)
            shipping = round(((seed >> (i * 3)) % 15), 2)
            markup = 1.15 + (((seed >> (i * 7)) % 50) / 100.0)
            original = round(price * markup, 2)
            listings.append(
                Listing(
                    title=f"{query} ({i + 1})",
                    price=price,
                    currency=self.currency,
                    source=self.name,
                    url="https://example.com/demo",
                    condition="New with tags",
                    condition_id="1000",
                    shipping=shipping,
                    buying_option="FIXED_PRICE",
                    original_price=original,
                    color=COLORS[(seed >> i) % len(COLORS)],
                )
            )
        listings.sort(key=lambda lst: lst.total)
        return listings

    def scan_deals(
        self,
        *,
        apparel_size: str = "M",
        shoe_size_us: str = "11",
        shoe_size_eu: str = "45",
        max_pages: int = 350,
        **kwargs,
    ) -> list[Listing]:
        from ..msrp_lookup import apply_msrp, normalize_product_name

        samples = [
            "Jacket Mizuno Sapporo Hybrid GLT",
            "Mizuno Team Sendai High Neck Sweatshirt",
            "Hooded Sweatshirt Mizuno Athletics Blue Granite",
            "Legging Mizuno BT PR Merino Black",
            "Running shoes Mizuno Wave Rider 29",
            "Sweatshirt Mizuno Team Sendai",
            "Jacket Mizuno Sendai Trad",
            "Hooded Sweatshirt Mizuno Team FZ",
            "Jersey Mizuno Merino Black",
            "Jogging Trousers Mizuno Sendai Training",
            "Running shoes Mizuno Wave Ultima 17",
            "Running shoes Mizuno Wave Inspire 21",
            "Hooded Sweatshirt Mizuno Athletics Princess Blue",
            "Trousers Mizuno Team Sendai Trad",
            "Running shoes Mizuno Neo Vista",
            "Sweatshirt High Neck Mizuno Team Sendai",
            "Coat Mizuno Sapporo Bench",
            "Running shoes Mizuno Wave Rebellion",
        ]
        listings: list[Listing] = []
        for i, title in enumerate(samples):
            seed = int(hashlib.sha256(title.encode()).hexdigest(), 16)
            msrp = 70 + (seed % 100)
            discount = 10 + (seed % 45)
            price = round(msrp * (1 - discount / 100), 2)
            color = COLORS[i % len(COLORS)]
            lst = Listing(
                title=title,
                price=price,
                currency=self.currency,
                source=self.name,
                url=f"https://example.com/demo/{i}",
                condition="New",
                buying_option="FIXED_PRICE",
                color=color,
                msrp=float(msrp),
            )
            lst.product_name = normalize_product_name(title)
            listings.append(lst)
        return listings
