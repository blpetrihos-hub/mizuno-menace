"""Fetch Mizuno USA MSRP by style id (official tier-1 source)."""

from __future__ import annotations

import json
import re
import time
from html import unescape

import requests

from .fetch_budget import MIZUNO_FETCH_DELAY, MAX_MIZUNO_FETCHES_PER_RUN
from .reference_cache import OFFICIAL_TTL_SECONDS, PriceEntry, ReferenceCache
from .style_extractor import (
    mizuno_product_url_from_search_href,
    normalize_style_id,
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
SEARCH_URL = "https://usa.mizuno.com/search.php"
PRODUCT_CARD = re.compile(
    r'class="card-figure[^"]*"[\s\S]*?href="([^"]+)"',
    re.I,
)
NON_SALE_PRICE = re.compile(
    r'non_sale_price_without_tax"\s*:\s*\{\s*"formatted"\s*:\s*"[^"]*"\s*,\s*"value"\s*:\s*([0-9]+(?:\.[0-9]+)?)',
    re.I,
)
PAGE_MPN = re.compile(r'Style\s*#\s*([A-Z0-9-]+)', re.I)


class MizunoUsaClient:
    def __init__(
        self,
        cache: ReferenceCache | None = None,
        timeout: int = 20,
        delay: float = MIZUNO_FETCH_DELAY,
        max_fetches_per_run: int = MAX_MIZUNO_FETCHES_PER_RUN,
    ):
        self.cache = cache or ReferenceCache()
        self.timeout = timeout
        self.delay = delay
        self.max_fetches_per_run = max_fetches_per_run
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": USER_AGENT})
        self._fetch_count = 0
        self._last_fetch = 0.0
        self.last_lookup_attempted = False

    @property
    def fetch_budget_exhausted(self) -> bool:
        return self._fetch_count >= self.max_fetches_per_run

    def lookup(
        self,
        style_id: str,
        *,
        title_hint: str = "",
    ) -> PriceEntry | None:
        style_id = normalize_style_id(style_id)
        if not style_id:
            return None

        if self.cache.is_miss(style_id):
            return None

        cached = self.cache.get_official(style_id)
        if cached and cached.is_fresh(OFFICIAL_TTL_SECONDS):
            return cached

        if self.fetch_budget_exhausted:
            return cached

        self.last_lookup_attempted = True
        entry = self._fetch(style_id, title_hint=title_hint)
        if entry:
            self.cache.put_official(entry)
            return entry
        self.cache.put_miss(style_id)
        return cached

    def _pause(self) -> None:
        elapsed = time.time() - self._last_fetch
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_fetch = time.time()

    def _fetch(self, style_id: str, *, title_hint: str) -> PriceEntry | None:
        for query in (style_id, title_hint.strip()):
            if not query:
                continue
            product_url = self._search_product_url(query)
            if not product_url:
                continue
            entry = self._fetch_product_page(style_id, product_url)
            if entry:
                return entry
        return None

    def _search_product_url(self, query: str) -> str:
        self._pause()
        self._fetch_count += 1
        resp = self._session.get(
            SEARCH_URL,
            params={"search_query": query},
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            return ""
        for match in PRODUCT_CARD.finditer(resp.text):
            href = unescape(match.group(1))
            url = mizuno_product_url_from_search_href(href)
            if "/search" in url or url.rstrip("/") == "https://usa.mizuno.com":
                continue
            return url
        return ""

    def _fetch_product_page(self, style_id: str, url: str) -> PriceEntry | None:
        self._pause()
        self._fetch_count += 1
        resp = self._session.get(url, timeout=self.timeout)
        if resp.status_code != 200:
            return None

        page_style = self._page_style_id(resp.text)
        if page_style and page_style != style_id and not self._styles_related(style_id, page_style):
            return None

        msrp = self._page_msrp(resp.text)
        title = self._page_title(resp.text) or style_id
        if msrp is None:
            return None

        return PriceEntry(
            style_id=style_id,
            msrp=msrp,
            currency="USD",
            source="mizuno_official",
            label="Mizuno MSRP",
            url=url,
            title=title,
            updated_at=time.time(),
        )

    @staticmethod
    def _styles_related(requested: str, found: str) -> bool:
        """Allow parent-style matches (e.g. base shoe vs color variant)."""
        return requested.startswith(found[:6]) or found.startswith(requested[:6])

    def _page_style_id(self, html_text: str) -> str:
        for block in re.findall(
            r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
            html_text,
            re.DOTALL,
        ):
            try:
                data = json.loads(block.strip())
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and data.get("@type") == "Product":
                return normalize_style_id(str(data.get("sku", "")))
        match = PAGE_MPN.search(html_text)
        return normalize_style_id(match.group(1)) if match else ""

    def _page_title(self, html_text: str) -> str:
        for block in re.findall(
            r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
            html_text,
            re.DOTALL,
        ):
            try:
                data = json.loads(block.strip())
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and data.get("@type") == "Product":
                return str(data.get("name", "")).strip()
        return ""

    def _page_msrp(self, html_text: str) -> float | None:
        match = NON_SALE_PRICE.search(html_text)
        if match:
            return float(match.group(1))

        for block in re.findall(
            r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
            html_text,
            re.DOTALL,
        ):
            try:
                data = json.loads(block.strip())
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict) or data.get("@type") != "Product":
                continue
            offers = data.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            value = offers.get("price") if isinstance(offers, dict) else None
            if value is not None:
                return float(value)
        return None
