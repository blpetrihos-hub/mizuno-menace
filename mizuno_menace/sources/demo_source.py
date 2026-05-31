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
