"""Offline demo source mimicking eBay listings for development without API keys."""

from __future__ import annotations

import hashlib

from ..models import Listing
from ..msrp_lookup import normalize_product_name
from .base import PriceSource

COLORS = ["Black", "Navy Blue", "Royal Blue", "Grey", "White", "Red"]


class DemoSource(PriceSource):
    name = "eBay"

    def __init__(self, currency: str = "USD"):
        self.currency = currency

    @property
    def available(self) -> bool:
        return True

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
            original = round((price + shipping) * markup, 2)
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
                    kind="apparel",
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
        from ..search_criteria import normalize_search_scope

        scope = normalize_search_scope(kwargs.get("search_scope", "both"))
        custom = (kwargs.get("custom_query") or "").strip()
        allowed_kinds: set[str] | None = None
        if not custom:
            if scope == "apparel":
                allowed_kinds = {"apparel"}
            elif scope == "shoes":
                allowed_kinds = {"shoe"}

        catalog = [
            ("Jacket Mizuno Sapporo Hybrid GLT", "apparel", "32FE9A0609"),
            ("Mizuno Team Sendai High Neck Sweatshirt", "apparel", ""),
            ("Hooded Sweatshirt Mizuno Athletics Blue Granite", "apparel", ""),
            ("Legging Mizuno BT PR Merino Black", "apparel", ""),
            ("Running shoes Mizuno Wave Rider 29", "shoe", "411495"),
            ("Sweatshirt Mizuno Team Sendai", "apparel", ""),
            ("Jacket Mizuno Sendai Trad", "apparel", ""),
            ("Running shoes Mizuno Wave Ultima 17", "shoe", "411501"),
            ("Running shoes Mizuno Wave Inspire 21", "shoe", "411502"),
            ("Running shoes Mizuno Neo Vista", "shoe", "411503"),
        ]
        listings: list[Listing] = []
        for i, (title, kind, style_id) in enumerate(catalog):
            if allowed_kinds is not None and kind not in allowed_kinds:
                continue
            seed = int(hashlib.sha256(title.encode()).hexdigest(), 16)
            base = 60 + (seed % 90)
            for variant in range(3):
                vseed = seed + variant * 997
                spread = (vseed % 40) - 15
                price = round(max(20.0, base + spread + variant * 4), 2)
                shipping = round((vseed % 12), 2)
                markup = 1.12 + ((vseed % 30) / 100.0)
                original = round((price + shipping) * markup, 2)
                color = COLORS[(i + variant) % len(COLORS)]
                lst = Listing(
                    title=f"{title} {color}",
                    price=price,
                    currency=self.currency,
                    source=self.name,
                    url=f"https://example.com/demo/{i}-{variant}",
                    condition="New with tags",
                    condition_id="1000",
                    shipping=shipping,
                    buying_option="FIXED_PRICE",
                    original_price=original if variant == 0 else None,
                    color=color,
                    style_id=style_id,
                    kind=kind,
                )
                lst.product_name = normalize_product_name(title)
                listings.append(lst)

        # Noise listings (filtered out before ranking; exercises custom + default scans).
        noise = [
            ("Mizuno Baseball Elite Jersey Mens M NWT", "apparel", ""),
            ("Mizuno Batting Jacket Mens Medium New With Tags", "apparel", ""),
            ("Mizuno Wave Lightrevo Baseball Softball Turf Shoes", "shoe", ""),
            ("Mizuno Womens Running Shirt Medium NWT", "apparel", ""),
            ("Mizuno Running Socks 3-Pack Mens", "apparel", ""),
            ("Mizuno Youth Running Jacket Medium", "apparel", ""),
            ("Mizuno Soccer Training Jacket Mens M", "apparel", ""),
        ]
        for i, (title, kind, style_id) in enumerate(noise):
            if allowed_kinds is not None and kind not in allowed_kinds:
                continue
            listings.append(
                Listing(
                    title=title,
                    price=29.99 + i,
                    currency=self.currency,
                    source=self.name,
                    url=f"https://example.com/demo/noise-{i}",
                    condition="New with tags",
                    condition_id="1000",
                    shipping=0.0,
                    buying_option="FIXED_PRICE",
                    kind=kind,
                    style_id=style_id,
                )
            )
        return listings
