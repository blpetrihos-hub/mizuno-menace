"""Fetch Mizuno EMEA (EU) list prices by article / style id."""

from __future__ import annotations

import re
import time

import requests

from .currency_util import to_usd
from .reference_cache import OFFICIAL_TTL_SECONDS, PriceEntry, ReferenceCache
from .style_extractor import normalize_style_id

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
BASE = "https://emea.mizuno.com"
PRODUCT_URL = BASE + "/eu/en-gb/product/{style_id}.html"
SEARCH_URL = BASE + "/eu/en/show-search/"


class MizunoEuClient:
    """Look up EU article numbers on emea.mizuno.com (SFCC storefront)."""

    def __init__(
        self,
        cache: ReferenceCache | None = None,
        timeout: int = 20,
        delay: float = 0.25,
        max_fetches_per_run: int = 12,
    ):
        self.cache = cache or ReferenceCache()
        self.timeout = timeout
        self.delay = delay
        self.max_fetches_per_run = max_fetches_per_run
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept-Language": "en-GB,en;q=0.9",
            }
        )
        self._fetch_count = 0
        self._last_fetch = 0.0

    @property
    def fetch_budget_exhausted(self) -> bool:
        return self._fetch_count >= self.max_fetches_per_run

    def lookup(
        self,
        style_id: str,
        *,
        title_hint: str = "",
        target_currency: str = "USD",
    ) -> PriceEntry | None:
        style_id = normalize_style_id(style_id)
        if not style_id:
            return None

        cached = self.cache.get_eu(style_id)
        if cached and cached.is_fresh(OFFICIAL_TTL_SECONDS):
            return self._for_currency(cached, target_currency)

        if self.cache.is_eu_miss(style_id):
            return None

        if self.fetch_budget_exhausted:
            return self._for_currency(cached, target_currency) if cached else None

        entry = self._fetch(style_id, title_hint=title_hint)
        if entry:
            self.cache.put_eu(entry)
            return self._for_currency(entry, target_currency)
        self.cache.put_eu_miss(style_id)
        return None

    def _for_currency(self, entry: PriceEntry, target: str) -> PriceEntry:
        if not entry or (target or "USD").upper() == entry.currency.upper():
            return entry
        if target.upper() == "USD" and entry.currency.upper() != "USD":
            converted = to_usd(entry.msrp, entry.currency)
            return PriceEntry(
                style_id=entry.style_id,
                msrp=converted,
                currency="USD",
                source=entry.source,
                label=entry.label,
                url=entry.url,
                title=entry.title,
                updated_at=entry.updated_at,
            )
        return entry

    def _pause(self) -> None:
        elapsed = time.time() - self._last_fetch
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_fetch = time.time()

    def _fetch(self, style_id: str, *, title_hint: str) -> PriceEntry | None:
        self._pause()
        self._fetch_count += 1
        resp = self._session.get(
            PRODUCT_URL.format(style_id=style_id),
            timeout=self.timeout,
            allow_redirects=True,
        )
        if resp.status_code == 200:
            entry = self._parse_product_page(style_id, resp.url, resp.text)
            if entry:
                return entry

        if title_hint:
            return self._fetch_via_search(style_id)
        return None

    def _fetch_via_search(self, style_id: str) -> PriceEntry | None:
        """Search by article number; only accept exact data-pid matches."""
        self._pause()
        self._fetch_count += 1
        resp = self._session.get(
            SEARCH_URL,
            params={"q": style_id},
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            return None

        for pid in dict.fromkeys(re.findall(r'data-pid="([^"]+)"', resp.text)):
            if normalize_style_id(pid) != style_id:
                continue
            self._pause()
            self._fetch_count += 1
            pr = self._session.get(
                PRODUCT_URL.format(style_id=pid),
                timeout=self.timeout,
                allow_redirects=True,
            )
            if pr.status_code == 200:
                return self._parse_product_page(style_id, pr.url, pr.text)
        return None

    def _parse_product_page(
        self, style_id: str, url: str, html: str
    ) -> PriceEntry | None:
        msrp, currency = _extract_list_price(html, style_id)
        if msrp is None:
            return None
        title_m = re.search(r"<title>([^<]+)</title>", html, re.I)
        title = title_m.group(1).split("|")[0].strip() if title_m else style_id
        return PriceEntry(
            style_id=style_id,
            msrp=msrp,
            currency=currency,
            source="mizuno_eu",
            label="Mizuno EU MSRP",
            url=url,
            title=title,
            updated_at=time.time(),
        )


def _extract_list_price(html: str, pid: str) -> tuple[float | None, str]:
    """Parse SFCC analytics / tracking JSON embedded in product pages."""
    patterns = [
        rf'"id"\s*:\s*"{re.escape(pid)}"[\s\S]{{0,500}}?"price"\s*:\s*([0-9]+(?:\.[0-9]{{2}})?)',
        rf'"price"\s*:\s*([0-9]+(?:\.[0-9]{{2}})?)[\s\S]{{0,500}}?"id"\s*:\s*"{re.escape(pid)}"',
        rf"'id'\s*:\s*'{re.escape(pid)}'[\s\S]{{0,300}}?'price'\s*:\s*([0-9]+(?:\.[0-9]{{2}})?)",
    ]
    for pat in patterns:
        m = re.search(pat, html, re.I)
        if m:
            return float(m.group(1)), "EUR"
    return None, ""
