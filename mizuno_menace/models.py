"""Shared data structures."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Optional


# Default eBay category id + aspect name used for size filtering, keyed by kind.
# (eBay's size aspect is "Size" for clothing and "US Shoe Size" for shoes.)
_KIND_DEFAULTS = {
    "apparel": ("1059", "Size"),       # Men's Clothing
    "shoe": ("93427", "US Shoe Size"),  # Men's Shoes
}


@dataclass
class Product:
    """A Mizuno product we want to price-check.

    `msrp` is Mizuno's retail price used as the discount reference. When it is
    None, the tool falls back to each eBay listing's own list/strikethrough
    price as the reference instead.

    `category_id` and `aspects` drive eBay aspect-based size filtering. If not
    set explicitly, they are derived from `kind` + `size`.
    """

    name: str
    query: str
    msrp: Optional[float] = None
    currency: str = "USD"
    size: str = ""
    kind: str = ""  # "apparel" or "shoe"
    category_id: Optional[str] = None
    aspects: dict[str, str] = field(default_factory=dict)

    def ebay_aspects(self) -> tuple[Optional[str], dict[str, str]]:
        """Return (category_id, aspects) for eBay aspect filtering.

        Explicit fields win; otherwise derive a size aspect from kind + size.
        """
        if self.aspects:
            return self.category_id, dict(self.aspects)
        default = _KIND_DEFAULTS.get(self.kind.lower())
        if default and self.size:
            cat, aspect_name = default
            return self.category_id or cat, {aspect_name: self.size}
        return self.category_id, {}


@dataclass
class Listing:
    """A single priced result from some source (one eBay listing, etc.)."""

    title: str
    price: float
    currency: str
    source: str
    url: str = ""
    condition: str = ""
    condition_id: str = ""
    shipping: Optional[float] = None
    buying_option: str = ""
    color: str = ""
    style_id: str = ""
    kind: str = ""  # apparel | shoe — set by eBay scan
    # Reference prices for discount math:
    msrp: Optional[float] = None
    original_price: Optional[float] = None  # eBay seller's list/strikethrough
    reference_source: str = ""
    reference_as_of: str = ""
    estimated: bool = False
    deal_index: Optional[float] = None  # indexable % below reference (primary rank key)
    product_name: str = ""

    @property
    def total(self) -> float:
        """Item price plus shipping (when shipping is known)."""
        return round(self.price + (self.shipping or 0.0), 2)

    @property
    def reference_price(self) -> Optional[float]:
        """The price we compare against: Mizuno MSRP if known, else the eBay
        listing's own strikethrough/list price."""
        if self.msrp and self.msrp > 0:
            return self.msrp
        if self.original_price and self.original_price > 0:
            return self.original_price
        return None

    @property
    def reference_label(self) -> str:
        labels = {
            "mizuno_official": "Mizuno MSRP",
            "mizuno_eu": "Mizuno EU MSRP",
            "catalog": "Catalog MSRP",
            "ebay_list": "vs seller list",
            "peer_style": "Peer median (style)",
            "peer_product": "Peer median (product)",
            "peer_category": "Category median",
            "estimated": "Estimated MSRP",
            "watchlist": "Watchlist MSRP",
        }
        label = labels.get(self.reference_source, "")
        if not label:
            if self.msrp and self.msrp > 0:
                return "Mizuno MSRP"
            if self.original_price and self.original_price > 0:
                return "eBay list"
            return ""
        if self.reference_as_of:
            return f"{label} ({self.reference_as_of})"
        return label

    @property
    def savings(self) -> Optional[float]:
        ref = self.reference_price
        if ref is None:
            return None
        return round(ref - self.total, 2)

    @property
    def discount_pct(self) -> Optional[float]:
        if self.deal_index is not None:
            return self.deal_index
        ref = self.reference_price
        if ref is None or ref <= 0:
            return None
        return round((ref - self.total) / ref * 100, 1)


@dataclass
class ItemResult:
    """All listings found for one search term, plus computed stats."""

    query: str
    product_name: str = ""
    listings: list[Listing] = field(default_factory=list)
    error: Optional[str] = None
    note: str = ""

    @property
    def count(self) -> int:
        return len(self.listings)

    @property
    def currency(self) -> str:
        return self.listings[0].currency if self.listings else ""

    def _prices(self) -> list[float]:
        return [lst.total for lst in self.listings]

    @property
    def min_price(self) -> Optional[float]:
        prices = self._prices()
        return min(prices) if prices else None

    @property
    def max_price(self) -> Optional[float]:
        prices = self._prices()
        return max(prices) if prices else None

    @property
    def avg_price(self) -> Optional[float]:
        prices = self._prices()
        return round(statistics.fmean(prices), 2) if prices else None

    @property
    def median_price(self) -> Optional[float]:
        prices = self._prices()
        return round(statistics.median(prices), 2) if prices else None

    @property
    def cheapest(self) -> Optional[Listing]:
        if not self.listings:
            return None
        return min(self.listings, key=lambda lst: lst.total)

    @property
    def best_deal(self) -> Optional[Listing]:
        """Listing with the highest deal index in this group."""
        scored = [lst for lst in self.listings if lst.deal_index is not None]
        if not scored:
            scored = [lst for lst in self.listings if lst.discount_pct is not None]
        if not scored:
            return None
        return max(scored, key=lambda lst: lst.deal_index or lst.discount_pct or 0)

    @property
    def best_discount(self) -> Optional[Listing]:
        """Backward-compatible alias for best_deal."""
        return self.best_deal
