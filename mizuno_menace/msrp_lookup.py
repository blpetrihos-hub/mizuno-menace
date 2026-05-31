"""Mizuno USA retail reference prices by product line (not a search watchlist).

Used when scraping foot-store to compute discount % vs Mizuno MSRP. Longest
keyword tuple wins. Extend as new product lines appear in scan results.
"""

from __future__ import annotations

import re

from .models import Listing

# (keyword fragments, MSRP USD) — order: longest / most specific first.
_MSRP_RULES: list[tuple[tuple[str, ...], float]] = [
    (("sapporo", "hybrid", "glt"), 160.0),
    (("sapporo", "hybrid"), 150.0),
    (("sapporo", "bench"), 140.0),
    (("sendai", "high", "neck"), 80.0),
    (("high", "neck", "sweatshirt"), 80.0),
    (("sendai", "trad", "jacket"), 120.0),
    (("sendai", "trad"), 110.0),
    (("team", "sendai", "jacket"), 120.0),
    (("team", "sendai", "sweatshirt"), 75.0),
    (("sendai", "sweatshirt"), 75.0),
    (("sendai", "training"), 70.0),
    (("sendai", "jogger"), 65.0),
    (("team", "sendai"), 75.0),
    (("athletics", "graphic", "hoodie"), 75.0),
    (("athletics", "hoodie"), 70.0),
    (("athletics", "hooded"), 70.0),
    (("athletic", "hooded"), 65.0),
    (("bt", "pr", "merino", "tight"), 120.0),
    (("bt", "pr", "merino"), 100.0),
    (("merino", "tight"), 120.0),
    (("merino", "legging"), 85.0),
    (("merino", "jersey"), 90.0),
    (("breath", "thermo", "merino"), 85.0),
    (("tech", "light"), 80.0),
    (("wave", "rider"), 140.0),
    (("wave", "inspire"), 145.0),
    (("wave", "ultima"), 120.0),
    (("wave", "rebellion"), 160.0),
    (("wave", "sky"), 150.0),
    (("wave", "horizon"), 130.0),
    (("neo", "vista"), 170.0),
    (("wave", "prophecy"), 200.0),
    (("team", "fz", "hooded"), 65.0),
    (("team", "fz"), 65.0),
    (("fz", "hooded"), 65.0),
    (("hooded", "sweatshirt"), 70.0),
    (("sweatshirt", "high", "neck"), 80.0),
    (("sweatshirt"), 70.0),
    (("jogging", "trouser"), 65.0),
    (("training", "jogger"), 65.0),
    (("trad", "jacket"), 120.0),
    (("trad", "trouser"), 55.0),
    (("padded", "jacket"), 150.0),
    (("hybrid", "jacket"), 150.0),
    (("jacket"), 120.0),
    (("half", "zip"), 90.0),
    (("t shirt"), 50.0),
    (("tank", "top"), 35.0),
    (("tee"), 35.0),
    (("shirt"), 50.0),
    (("shorts"), 45.0),
    (("legging"), 85.0),
    (("tights"), 100.0),
    (("tight"), 100.0),
    (("running", "shoes"), 130.0),
    (("trainers"), 130.0),
    (("wave", "knit"), 130.0),
    (("wave", "serene"), 120.0),
    (("wave", "mujin"), 150.0),
]

_COLOR_WORDS = {
    "black", "white", "red", "blue", "navy", "royal", "green", "grey", "gray",
    "yellow", "orange", "pink", "purple", "burgundy", "mercury", "baritone",
    "granite", "aquifer", "fluorescent", "snow", "odyssey", "blacksand",
    "metallicgray", "metallic", "sand", "gold", "silver", "elm", "wind",
    "surf", "harbor", "mist", "dress", "blues", "capri", "breeze", "tangelo",
}


def _title_key(title: str) -> str:
    text = title.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    tokens = [t for t in text.split() if t and t not in _COLOR_WORDS and t != "mizuno"]
    return " ".join(tokens)


def normalize_product_name(title: str) -> str:
    """Strip color/size noise so variants group under one product."""
    key = _title_key(title)
    return " ".join(w.capitalize() for w in key.split()) or title.strip()


def lookup_msrp(title: str) -> float | None:
    text = _title_key(title)
    if not text:
        return None
    best: tuple[int, float] | None = None
    for keywords, msrp in _MSRP_RULES:
        if all(k in text for k in keywords):
            score = len(keywords)
            if best is None or score > best[0]:
                best = (score, msrp)
    return best[1] if best else None


def apply_msrp(listing: Listing) -> None:
    msrp = lookup_msrp(listing.title)
    if msrp:
        listing.msrp = msrp
