"""Drop listings that should never appear in deal results."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .models import Listing

_SOCK_WORD = re.compile(r"\bsocks?\b", re.IGNORECASE)

_WOMENS_WORD = re.compile(
    r"\b("
    r"womens?|women'?s?|ladies?|lady'?s?|female|"
    r"for\s+women|wmns?|girls?|girl'?s?"
    r")\b",
    re.IGNORECASE,
)

_UNISEX_WORD = re.compile(r"\bunisex\b", re.IGNORECASE)

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

_GOLF_WORD = re.compile(
    r"\b("
    r"golf(?:ing)?|"
    r"golf\s+shoes?|"
    r"golf\s+shirt|"
    r"golf\s+polo"
    r")\b",
    re.IGNORECASE,
)

_FIELD_SPORT = re.compile(
    r"\b("
    r"futsal|"
    r"soccer\s+shoes?|"
    r"monarcida|"
    r"neo\s+sala|"
    r"baseball\s+shoes?|"
    r"softball\s+shoes?|"
    r"wave\s+lightrevo|"
    r"lightrevo|"
    r"turf\s+shoes?|"
    r"baseball\s+jersey|"
    r"softball\s+jersey"
    r")\b",
    re.IGNORECASE,
)

_JUNK_MERCH = re.compile(
    r"\b("
    r"funny|"
    r"reprint|"
    r"anime|"
    r"kimetsu|"
    r"demon\s+slayer|"
    r"cosplay|"
    r"parody|"
    r"meme|"
    r"safety\s+vest|"
    r"saftey\s+vest|"
    r"promo\s+saftey"
    r")\b",
    re.IGNORECASE,
)

EXCLUSION_LABELS: dict[str, str] = {
    "socks": "sock",
    "womens": "women's",
    "cleats": "cleat",
    "unisex": "unisex",
    "golf": "golf",
    "field_sport": "field sport",
    "junk": "junk/merch",
}


def _listing_text(lst: Listing) -> str:
    parts = [lst.title or ""]
    if lst.product_name:
        parts.append(lst.product_name)
    return " ".join(parts)


def is_socks_listing(text: str) -> bool:
    return bool(_SOCK_WORD.search(text or ""))


def is_womens_listing(text: str) -> bool:
    return bool(_WOMENS_WORD.search(text or ""))


def is_unisex_listing(text: str) -> bool:
    return bool(_UNISEX_WORD.search(text or ""))


def is_cleats_listing(text: str) -> bool:
    text = text or ""
    return bool(
        _CLEAT_WORD.search(text)
        or _CLEAT_SPIKE.search(text)
        or _CLEAT_MODEL.search(text)
    )


def is_golf_listing(text: str) -> bool:
    return bool(_GOLF_WORD.search(text or ""))


def is_field_sport_listing(text: str) -> bool:
    return bool(_FIELD_SPORT.search(text or ""))


def is_junk_merch_listing(text: str) -> bool:
    return bool(_JUNK_MERCH.search(text or ""))


@dataclass
class ExclusionStats:
    counts: dict[str, int] = field(default_factory=dict)

    def record(self, reason: str) -> None:
        self.counts[reason] = self.counts.get(reason, 0) + 1

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    def get(self, reason: str) -> int:
        return self.counts.get(reason, 0)


def exclusion_reason(lst: Listing) -> str | None:
    text = _listing_text(lst)
    if is_socks_listing(text):
        return "socks"
    if is_womens_listing(text):
        return "womens"
    if is_cleats_listing(text):
        return "cleats"
    if is_unisex_listing(text):
        return "unisex"
    if is_golf_listing(text):
        return "golf"
    if is_field_sport_listing(text):
        return "field_sport"
    if is_junk_merch_listing(text):
        return "junk"
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
        if reason:
            stats.record(reason)
            continue
        kept.append(lst)
    return kept, stats
