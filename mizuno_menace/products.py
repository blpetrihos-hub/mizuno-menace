"""Loading the product list (with optional Mizuno MSRP references)."""

from __future__ import annotations

import json
from pathlib import Path

from .default_products import DEFAULT_PRODUCTS
from .models import Product


def _from_entries(data: list[dict]) -> list[Product]:
    products: list[Product] = []
    for entry in data:
        msrp = entry.get("msrp")
        products.append(
            Product(
                name=entry.get("name") or entry.get("query", "?"),
                query=entry["query"],
                msrp=float(msrp) if msrp not in (None, "") else None,
                currency=entry.get("currency", "USD"),
                size=str(entry.get("size", "")),
                kind=entry.get("kind", ""),
                category_id=entry.get("category_id"),
                aspects=entry.get("aspects") or {},
            )
        )
    return products


def load_products(path: Path) -> list[Product]:
    """Load products from a JSON file.

    Accepts either a top-level list, or an object with a "products" key
    (so the file can also carry a "_comment").
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("products", [])
    return _from_entries(data)


def default_products() -> list[Product]:
    """The embedded product list (used when no products.json is found)."""
    return _from_entries(DEFAULT_PRODUCTS)


def products_from_queries(queries: list[str]) -> list[Product]:
    """Build products from bare search terms (no MSRP reference)."""
    return [Product(name=q, query=q) for q in queries]
