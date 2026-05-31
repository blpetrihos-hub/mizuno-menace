"""Drop listings that should never appear in deal results."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Listing

_SOCK_WORD = re.compile(r"\bsocks?\b", re.IGNORECASE)

_WOMENS_WORD = re.compile(
    r"\b("
    r"womens?|women'?s?|ladies?|lady'?s?|female|"
    r"for\s+women|wmns?|girls?|girl'?s?"
    r")\b",
    re.IGNORECASE,
)

_CLEAT_WORD = re.compile(r"\bcleats?\b|\bcleated\b", re.IGNORECASE)

_CLEAT_SPIKE = re.compile(
    r"\b("
    r"(?:baseball|softball|football|soccer|lacrosse|rugby|fastpitch|track)"
    r"\s+(?:cleats?|spikes?|cleated)|"
    r"(?:cleats?|spikes?)\s+(?:baseball|softball|football|soccer|lacrosse)|"
    r"metal\s+(?:cleats?|spikes?)|"
    r"molded\s+cleats?|"
    r"(?:baseball|softball|football)\s+spikes?"
    r")\b",
    re.IGNORECASE,
)

# Mizuno field/cleat lines that often omit the word "cleat" in eBay titles.
_CLEAT_MODEL = re.compile(
    r"\b("
    r"ambition\s+\d+|"
    r"dominant\s+(?:ic|mc|metal|tpu)?|"
    r"9[\s-]?spike|"
    r"lightning\s+(?:star|fastpitch)|"
    r"fastpitch\s+metal|"
    r"pro\s+direct\s+medial"
    r")\b",
    re.IGNORECASE,
)


def _listing_text(lst: Listing) -> str:
    parts = [lst.title or ""]
    if lst.product_name:
        parts.append(lst.product_name)
    return " ".join(parts)


def is_socks_listing(text: str) -> bool:
    """True when title/name indicates socks (word-boundary match avoids 'soccer')."""
    return bool(_SOCK_WORD.search(text or ""))


def is_womens_listing(text: str) -> bool:
    """Exclude women's / girls listings."""
    return bool(_WOMENS_WORD.search(text or ""))


def is_cleats_listing(text: str) -> bool:
    """Exclude baseball/football/soccer cleats and spiked field shoes."""
    text = text or ""
    return bool(
        _CLEAT_WORD.search(text)
        or _CLEAT_SPIKE.search(text)
        or _CLEAT_MODEL.search(text)
    )


@dataclass
class ExclusionStats:
    socks: int = 0
    womens: int = 0
    cleats: int = 0

    @property
    def total(self) -> int:
        return self.socks + self.womens + self.cleats


def exclusion_reason(lst: Listing) -> str | None:
    text = _listing_text(lst)
    if is_socks_listing(text):
        return "socks"
    if is_womens_listing(text):
        return "womens"
    if is_cleats_listing(text):
        return "cleats"
    return None


def listing_is_excluded(lst: Listing) -> bool:
    return exclusion_reason(lst) is not None


def drop_excluded_listings(
    listings: list[Listing],
) -> tuple[list[Listing], ExclusionStats]:
    kept: list[Listing] = []
    stats = ExclusionStats()
    for lst in listings:
        reason = exclusion_reason(lst)
        if reason == "socks":
            stats.socks += 1
            continue
        if reason == "womens":
            stats.womens += 1
            continue
        if reason == "cleats":
            stats.cleats += 1
            continue
        kept.append(lst)
    return kept, stats
