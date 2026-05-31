"""Drop listings that should never appear in deal results."""

from __future__ import annotations

import re

from .models import Listing

_SOCK_WORD = re.compile(r"\bsocks?\b", re.IGNORECASE)


def is_socks_listing(text: str) -> bool:
    """True when title/name indicates socks (word-boundary match avoids 'soccer')."""
    return bool(_SOCK_WORD.search(text or ""))


def listing_is_excluded(lst: Listing) -> bool:
    if is_socks_listing(lst.title):
        return True
    if lst.product_name and is_socks_listing(lst.product_name):
        return True
    return False


def drop_excluded_listings(listings: list[Listing]) -> tuple[list[Listing], int]:
    kept: list[Listing] = []
    excluded = 0
    for lst in listings:
        if listing_is_excluded(lst):
            excluded += 1
            continue
        kept.append(lst)
    return kept, excluded
