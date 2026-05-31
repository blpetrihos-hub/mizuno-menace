"""foot-store.com price source.

foot-store has no public API and its on-site search is rendered client-side, so
we discover product URLs from the store's XML sitemaps (filtered to Mizuno),
match them against the query, then read each product page's JSON-LD
(schema.org/Product) for the name and price.

This is intentionally polite: the (large) Mizuno URL list is cached on disk, we
only fetch a handful of product pages per query, and we pause between requests.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import requests

from ..msrp_lookup import normalize_product_name
from ..style_extractor import resolve_style_id
from ..models import Listing
from ..paths import cache_dir
from ..search_criteria import APPAREL_SIZE, SHOE_SIZE_EU, SHOE_SIZE_US
from .base import PriceSource

SITEMAP_INDEX = "https://foot-store.com/sitemap.xml"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
# Tokens that don't help match a product slug (brand/gender/size words).
STOPWORDS = {
    "mizuno", "mens", "men", "man", "womens", "women", "unisex", "the", "and",
    "with", "for", "size", "medium", "med", "small", "large", "xl", "xxl",
    "xs", "nwt", "new", "tags", "tag",
}
# Slug fragments that indicate the wrong gender / product line.
WOMENS_MARKERS = ("women-s", "womens-", "-women-", "woman-s")
KIDS_MARKERS = ("children-s", "children-", "kids-", "youth-", "junior-")
# Known two-word colors at the end of foot-store slugs (longest first).
SLUG_COLOR_PHRASES = (
    "navy-blue", "royal-blue", "maui-blue", "blue-granite", "royal-white",
    "black-white", "grey-white", "navy blue", "royal blue", "maui blue",
)
APPAREL_SLUG_MARKERS = (
    "jacket", "hoodie", "hooded-sweatshirt", "sweatshirt", "tights", "legging",
    "leggings", "trouser", "trousers", "jogger", "joggers", "shirt", "tee",
    "jersey", "pants", "coat", "shorts", "vest", "gilet", "half-zip",
    "windbreaker", "sweater", "pullover", "top",
)
SHOE_SLUG_MARKERS = (
    "running-shoes-mizuno", "shoes-mizuno-wave", "trainers-mizuno",
    "running-shoes-mizuno", "shoes-mizuno",
)
WOMENS_TITLE_MARKERS = (
    "women", "woman", "womens", "wos", "girl", "girls", "junior", "youth", "kid",
    "children", "child ",
)
# Slug ends with a single-letter size code (not a color word).
_SIZE_SUFFIX = re.compile(r"-(?:xs|xxl|xl|l|m|s)$")


class FootStoreSource(PriceSource):
    name = "foot-store"

    def __init__(
        self,
        max_products: int = 6,
        max_candidates: int = 40,
        timeout: int = 20,
        cache_path: Path | None = None,
        cache_ttl: int = 86_400,  # 24h
        delay: float = 0.3,
    ):
        self.max_products = max_products
        self.max_candidates = max_candidates
        self.timeout = timeout
        self.cache_path = cache_path or (cache_dir() / "footstore_mizuno_urls.txt")
        self.cache_ttl = cache_ttl
        self.delay = delay
        self._urls: list[str] | None = None
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": USER_AGENT})

    # -- URL discovery -----------------------------------------------------

    def _load_urls(self) -> list[str]:
        if self._urls is not None:
            return self._urls

        if self.cache_path.exists() and (time.time() - self.cache_path.stat().st_mtime) < self.cache_ttl:
            self._urls = self.cache_path.read_text(encoding="utf-8").splitlines()
            return self._urls

        urls = self._download_mizuno_urls()
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text("\n".join(urls), encoding="utf-8")
        self._urls = urls
        return urls

    def _download_mizuno_urls(self) -> list[str]:
        index = self._session.get(SITEMAP_INDEX, timeout=self.timeout)
        index.raise_for_status()
        product_maps = [
            loc for loc in re.findall(r"<loc>([^<]+)</loc>", index.text)
            if "product" in loc.lower()
        ]
        urls: list[str] = []
        for sm in product_maps:
            try:
                resp = self._session.get(sm, timeout=self.timeout)
                resp.raise_for_status()
            except requests.RequestException:
                continue
            urls.extend(
                loc for loc in re.findall(r"<loc>([^<]+)</loc>", resp.text)
                if "mizuno" in loc.lower()
            )
        return urls

    @staticmethod
    def _slug_size_suffix(slug: str) -> str | None:
        m = _SIZE_SUFFIX.search(slug)
        return m.group(0).lstrip("-") if m else None

    @classmethod
    def _url_kind(cls, slug: str) -> str | None:
        if cls._is_womens(slug) or cls._is_kids(slug):
            return None
        if any(m in slug for m in APPAREL_SLUG_MARKERS):
            return "apparel"
        if any(m in slug for m in SHOE_SLUG_MARKERS):
            return "shoe"
        return None

    @classmethod
    def _apparel_matches_size(cls, slug: str, size: str = APPAREL_SIZE) -> bool:
        suffix = cls._slug_size_suffix(slug)
        if suffix is None:
            return True  # multi-size color page
        return suffix == size.lower()

    @classmethod
    def _shoe_matches_size(cls, slug: str, us: str = SHOE_SIZE_US, eu: str = SHOE_SIZE_EU) -> bool:
        # Explicit EU size segment in slug (foot-store convention).
        if re.search(rf"(?:^|-){re.escape(eu)}(?:-|$)", slug):
            return True
        if re.search(rf"(?:^|-){re.escape(us)}(?:-|$)", slug):
            return True
        # Model pages without size in slug (multi-size JSON-LD).
        if "running-shoes-mizuno" in slug or "shoes-mizuno-wave" in slug:
            return True
        if "trainers-mizuno" in slug and "-wave-" in slug:
            return True
        return False

    @staticmethod
    def _title_is_mens(title: str, description: str = "") -> bool:
        text = f"{title} {description}".lower()
        if re.search(r"\b(child|children|kids|kid|youth|junior|women|womens|wos|girl)\b", text):
            return False
        if "gender: male" in text or " men's " in f" {text} " or text.startswith("men "):
            return True
        if " male " in f" {text} ":
            return True
        return True

    def _filter_scan_urls(self, urls: list[str], apparel_size: str, shoe_us: str, shoe_eu: str) -> list[str]:
        kept: list[str] = []
        for url in urls:
            slug = self._slug(url)
            kind = self._url_kind(slug)
            if kind == "apparel" and self._apparel_matches_size(slug, apparel_size):
                kept.append(url)
            elif kind == "shoe" and self._shoe_matches_size(slug, shoe_us, shoe_eu):
                kept.append(url)
        return kept

    # -- matching ----------------------------------------------------------

    @staticmethod
    def _tokenize(query: str) -> list[str]:
        toks = re.findall(r"[a-z0-9]+", query.lower())
        return [t for t in toks if t not in STOPWORDS and len(t) > 1]

    @staticmethod
    def _slug(url: str) -> str:
        return url.rstrip("/").rsplit("/", 1)[-1].lower()

    @staticmethod
    def _is_womens(slug: str) -> bool:
        return any(m in slug for m in WOMENS_MARKERS) or slug.startswith("women-")

    @staticmethod
    def _is_kids(slug: str) -> bool:
        return any(m in slug for m in KIDS_MARKERS)

    @staticmethod
    def _shoe_model(slug: str) -> int | None:
        m = re.search(r"wave-(?:rider|inspire)-(\d+)", slug)
        return int(m.group(1)) if m else None

    @staticmethod
    def _size_in_slug(size: str, slug: str) -> bool:
        if not size.isdigit():
            return size in slug
        return bool(re.search(rf"(?:^|-){re.escape(size)}(?:-|$)", slug))

    @staticmethod
    def _token_matches_slug(token: str, slug: str) -> bool:
        if token.isdigit():
            return FootStoreSource._size_in_slug(token, slug)
        if token in slug:
            return True
        if token == "hoodie" and "hooded" in slug:
            return True
        if token == "tights" and ("tight" in slug or "legging" in slug):
            return True
        return False

    def _score_match(self, slug: str, toks: list[str]) -> int:
        score = sum(1 for t in toks if self._token_matches_slug(t, slug))
        if not score:
            return 0
        if self._is_womens(slug):
            score -= 4
        if self._is_kids(slug):
            score -= 5
        if "rider" in toks and "inspire" in slug and "rider" not in slug:
            score -= 6
        if "inspire" in toks and "rider" in slug and "inspire" not in slug:
            score -= 6
        # Prefer exact product-line tokens (athletics vs generic team gear).
        if "athletics" in toks:
            if "athletics" in slug:
                score += 2
            elif "team" in slug:
                score -= 2
        if "team" in toks and "team" in slug:
            score += 1
        if "sapporo" in toks and "sapporo" in slug:
            score += 1
        if "sendai" in toks and "sendai" in slug:
            score += 1
        if "wave" in toks and "wave" in slug:
            score += 1
        if "rider" in toks and "rider" in slug:
            score += 1
        if "inspire" in toks and "inspire" in slug:
            score += 1
        if "merino" in toks and "merino" in slug:
            score += 2
        if "tights" in toks and ("tight" in slug or "legging" in slug):
            score += 2
        if "hoodie" in toks and "hoodie" in slug:
            score += 1
        if "hoodie" in toks and "graphic" in slug and "graphic" not in toks:
            score -= 2
        if "rider" in toks or "inspire" in toks:
            model = self._shoe_model(slug)
            if model is not None:
                score += min(model // 5, 4)
            if "running-shoes" in slug:
                score += 1
            if "trainers" in slug:
                score -= 1
        return score

    def _match(self, query: str, urls: list[str]) -> list[str]:
        toks = self._tokenize(query)
        if not toks:
            return []
        scored: list[tuple[int, int, str]] = []
        for url in urls:
            slug = self._slug(url)
            score = self._score_match(slug, toks)
            if score > 0:
                scored.append((score, len(slug), url))
        if not scored:
            return []
        best = max(s[0] for s in scored)
        threshold = max(1, round(len(toks) * 0.6))
        # Allow near-matches (e.g. hooded sweatshirt when query says hoodie).
        keep = [s for s in scored if s[0] >= max(threshold, best - 2)]
        keep.sort(key=lambda s: (-s[0], s[1]))
        return [url for _, _, url in keep]

    @staticmethod
    def _listing_matches_query(title: str, toks: list[str]) -> bool:
        """Drop obvious mismatches after fetching the product page."""
        title_l = title.lower()
        if any(w in title_l for w in ("children", "kids", "kid's", "youth", "junior")):
            return False
        if "athletics" in toks and "athletics" not in title_l:
            if "team" in title_l and "team" not in toks:
                return False
        if "sendai" in toks and "sendai" not in title_l:
            return False
        if "sapporo" in toks and "sapporo" not in title_l:
            return False
        if "rider" in toks and "rider" not in title_l:
            return False
        if "inspire" in toks and "inspire" not in title_l:
            return False
        if "rider" in toks and "inspire" in title_l and "rider" not in title_l:
            return False
        if "merino" in toks and "merino" not in title_l:
            return False
        if "tights" in toks and "tight" not in title_l and "legging" not in title_l:
            return False
        if "jersey" in title_l and "jersey" not in toks:
            return False
        if "hoodie" in toks and "hoodie" not in title_l and "hooded" not in title_l:
            return False
        return True

    # -- product parsing ---------------------------------------------------

    def _parse_product(self, url: str) -> tuple[Listing | None, bool, str]:
        try:
            resp = self._session.get(url, timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException:
            return None, False, ""

        for block in re.findall(
            r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
            resp.text,
            re.DOTALL,
        ):
            try:
                data = json.loads(block.strip())
            except json.JSONDecodeError:
                continue
            listing, oos, desc = self._listing_from_ld(data, url)
            if listing or oos:
                return listing, oos, desc
        return None, False, ""

    def _listing_from_ld(self, data, url: str) -> tuple[Listing | None, bool, str]:
        candidates = data if isinstance(data, list) else [data]
        for node in candidates:
            if not isinstance(node, dict) or node.get("@type") != "Product":
                continue
            offers = node.get("offers")
            price, currency = _min_offer(offers)
            description = str(node.get("description", "") or "")
            if price is None:
                return None, True, description
            condition = "New" if "New" in str(node.get("itemCondition", "")) else ""
            color = _normalize_color(str(node.get("color", "") or "").strip())
            if not color:
                color = _color_from_slug(url)
            title = str(node.get("name", "")).strip()
            style_id = resolve_style_id(
                url=url,
                footstore_offers=offers,
                title=title,
            )
            return Listing(
                title=title,
                price=price,
                currency=currency or "USD",
                source=self.name,
                url=url,
                condition=condition,
                buying_option="FIXED_PRICE",
                color=color,
                style_id=style_id,
            ), False, description
        return None, False, ""

    # -- API ---------------------------------------------------------------

    def scan_deals(
        self,
        *,
        apparel_size: str = APPAREL_SIZE,
        shoe_size_us: str = SHOE_SIZE_US,
        shoe_size_eu: str = SHOE_SIZE_EU,
        max_pages: int = 350,
        **kwargs,
    ) -> list[Listing]:
        """Scrape in-stock Mizuno deals from foot-store (no watchlist queries)."""
        urls = self._filter_scan_urls(
            self._load_urls(), apparel_size, shoe_size_us, shoe_size_eu
        )
        listings: list[Listing] = []
        seen_urls: set[str] = set()
        for i, url in enumerate(urls):
            if i >= max_pages:
                break
            if url in seen_urls:
                continue
            seen_urls.add(url)
            if i:
                time.sleep(self.delay)
            listing, _, desc = self._parse_product(url)
            if not listing:
                continue
            slug = self._slug(url)
            if not self._title_is_mens(listing.title, desc):
                continue
            listing.product_name = normalize_product_name(listing.title)
            listings.append(listing)
        self._last_oos_count = 0
        return listings

    def search(self, query: str, limit: int = 10, **kwargs) -> list[Listing]:
        toks = self._tokenize(query)
        urls = self._load_urls()
        matches = self._match(query, urls)
        listings: list[Listing] = []
        oos = 0
        for i, url in enumerate(matches):
            if len(listings) >= limit:
                break
            if i >= self.max_candidates:
                break
            if i:
                time.sleep(self.delay)
            listing, out_of_stock, _desc = self._parse_product(url)
            if out_of_stock:
                oos += 1
            if listing and self._listing_matches_query(listing.title, toks):
                listings.append(listing)
        self._last_oos_count = oos
        listings.sort(key=lambda lst: lst.total)
        return listings[:limit]

    @property
    def last_oos_count(self) -> int:
        return getattr(self, "_last_oos_count", 0)


def _normalize_color(color: str) -> str:
    if not color:
        return ""
    parts = [p.strip() for p in re.split(r"[/\\]", color) if p.strip()]
    if not parts:
        return ""
    # Drop duplicate segments (e.g. "blacksand/blacksand/metallicgray").
    unique: list[str] = []
    for part in parts:
        if part.lower() not in {u.lower() for u in unique}:
            unique.append(part)
    if len(unique) == 1:
        return " ".join(w.capitalize() for w in unique[0].split())
    # Keep at most two segments for readable link labels.
    return " / ".join(" ".join(w.capitalize() for w in p.split()) for p in unique[:2])


def _color_from_slug(url: str) -> str:
    """Best-effort color from the product URL slug (e.g. ...-navy-blue)."""
    slug = url.rstrip("/").rsplit("/", 1)[-1].lower()
    for phrase in SLUG_COLOR_PHRASES:
        hyphen = phrase.replace(" ", "-")
        if slug.endswith(hyphen):
            return _normalize_color(phrase)
    parts = slug.split("-")
    if len(parts) >= 2:
        return _normalize_color(parts[-1])
    return ""


def _min_offer(offers) -> tuple[float | None, str | None]:
    """Return the cheapest in-stock offer price + currency from JSON-LD."""
    if offers is None:
        return None, None
    if isinstance(offers, dict):
        offers = [offers]
    best_price: float | None = None
    currency: str | None = None
    for off in offers:
        if not isinstance(off, dict):
            continue
        availability = str(off.get("availability", ""))
        if availability and "InStock" not in availability:
            continue
        value = off.get("price")
        if value is None:
            continue
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue
        if best_price is None or value < best_price:
            best_price = value
            currency = off.get("priceCurrency", currency)
    return best_price, currency
