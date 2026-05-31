"""eBay price source using the official Browse API.

Docs: https://developer.ebay.com/api-docs/buy/browse/resources/item_summary/methods/search
Auth: OAuth2 client-credentials grant (application token).

Default filters match the requested workflow:
  * Condition  -> New with tags (conditionId 1000)
  * Buying     -> Buy It Now only / FIXED_PRICE (no auctions)
  * Sort       -> price (eBay sorts ascending by price + shipping)
"""

from __future__ import annotations

import base64
import time

import requests

from ..config import EbayConfig, load_ebay_config
from ..models import Listing
from ..style_extractor import resolve_style_id
from .base import PriceSource

OAUTH_SCOPE = "https://api.ebay.com/oauth/api_scope"

# eBay condition id 1000 renders as "New with tags" for apparel/shoes.
CONDITION_NEW_WITH_TAGS = "1000"


class EbayAuthError(RuntimeError):
    pass


class EbaySource(PriceSource):
    name = "eBay"

    def __init__(
        self,
        config: EbayConfig | None = None,
        timeout: int = 20,
        *,
        condition_ids: tuple[str, ...] = (CONDITION_NEW_WITH_TAGS,),
        buying_options: tuple[str, ...] = ("FIXED_PRICE",),
        sort: str = "price",
        strict_nwt: bool = True,
    ):
        self.config = config or load_ebay_config()
        self.timeout = timeout
        self.condition_ids = condition_ids
        self.buying_options = buying_options
        self.sort = sort
        self.strict_nwt = strict_nwt
        self._token: str | None = None
        self._token_expiry: float = 0.0
        self._session = requests.Session()

    @property
    def available(self) -> bool:
        return self.config.is_configured

    def _get_token(self) -> str:
        if self._token and time.time() < self._token_expiry - 60:
            return self._token

        if not self.config.is_configured:
            raise EbayAuthError("Missing EBAY_CLIENT_ID / EBAY_CLIENT_SECRET")

        creds = f"{self.config.client_id}:{self.config.client_secret}".encode()
        basic = base64.b64encode(creds).decode()
        resp = self._session.post(
            self.config.oauth_url,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {basic}",
            },
            data={"grant_type": "client_credentials", "scope": OAUTH_SCOPE},
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            raise EbayAuthError(f"OAuth failed ({resp.status_code}): {resp.text[:300]}")
        payload = resp.json()
        self._token = payload["access_token"]
        self._token_expiry = time.time() + int(payload.get("expires_in", 7200))
        return self._token

    def _build_filter(self) -> str:
        parts: list[str] = []
        if self.condition_ids:
            parts.append("conditionIds:{" + "|".join(self.condition_ids) + "}")
        if self.buying_options:
            parts.append("buyingOptions:{" + "|".join(self.buying_options) + "}")
        return ",".join(parts)

    @staticmethod
    def _build_aspect_filter(category_id: str | None, aspects: dict[str, str]) -> str | None:
        if not category_id or not aspects:
            return None
        body = ",".join(f"{name}:{{{value}}}" for name, value in aspects.items())
        return f"categoryId:{category_id},{body}"

    def _request(self, params: dict, token: str):
        return self._session.get(
            self.config.browse_url,
            headers={
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": self.config.marketplace_id,
                # Ask eBay to compute shipping for a US location so the
                # price + shipping sort is accurate.
                "X-EBAY-C-ENDUSERCTX": "contextualLocation=country%3DUS",
            },
            params=params,
            timeout=self.timeout,
        )

    def search(self, query: str, limit: int = 10, **kwargs) -> list[Listing]:
        category_id = kwargs.get("category_id")
        aspects = kwargs.get("aspects") or {}

        token = self._get_token()
        params: dict[str, str | int] = {"q": query, "limit": min(limit, 50)}
        flt = self._build_filter()
        if flt:
            params["filter"] = flt
        if self.sort:
            params["sort"] = self.sort

        aspect_filter = self._build_aspect_filter(category_id, aspects)
        if aspect_filter:
            params["category_ids"] = category_id
            params["aspect_filter"] = aspect_filter

        resp = self._request(params, token)

        # If eBay rejects the aspect/category (e.g. wrong aspect name for the
        # category), retry once without it rather than returning nothing.
        if resp.status_code == 400 and aspect_filter:
            params.pop("aspect_filter", None)
            params.pop("category_ids", None)
            resp = self._request(params, token)

        if resp.status_code != 200:
            raise RuntimeError(f"Browse API {resp.status_code}: {resp.text[:300]}")

        listings: list[Listing] = []
        for item in resp.json().get("itemSummaries", []):
            price = item.get("price") or {}
            value = price.get("value")
            if value is None:
                continue

            condition_id = str(item.get("conditionId", ""))
            if self.strict_nwt and self.condition_ids and condition_id not in self.condition_ids:
                continue

            listings.append(
                Listing(
                    title=item.get("title", "").strip(),
                    price=float(value),
                    currency=price.get("currency", ""),
                    source=self.name,
                    url=item.get("itemWebUrl", ""),
                    condition=item.get("condition", ""),
                    condition_id=condition_id,
                    shipping=_first_shipping_cost(item),
                    buying_option=_buying_option(item),
                    original_price=_original_price(item),
                    color=_aspect_color(item),
                    style_id=resolve_style_id(
                        ebay_aspects=item.get("localizedAspects") or [],
                        title=item.get("title", "").strip(),
                    ),
                )
            )
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
        from ..models import Product
        from ..msrp_lookup import normalize_product_name
        from ..search_criteria import (
            APPAREL_SIZE,
            EBAY_APPAREL_QUERY,
            EBAY_SHOE_QUERY,
            SHOE_SIZE_US,
        )

        apparel_size = apparel_size or APPAREL_SIZE
        shoe_size_us = shoe_size_us or SHOE_SIZE_US
        per_query = min(max(max_pages // 4, 25), 50)
        listings: list[Listing] = []
        seen_urls: set[str] = set()

        searches = (
            (EBAY_APPAREL_QUERY, "apparel", apparel_size),
            (EBAY_SHOE_QUERY, "shoe", shoe_size_us),
        )
        for query, kind, size in searches:
            product = Product(name=query, query=query, kind=kind, size=size)
            category_id, aspects = product.ebay_aspects()
            found = self.search(
                query,
                limit=per_query,
                category_id=category_id,
                aspects=aspects,
            )
            for lst in found:
                if lst.url and lst.url in seen_urls:
                    continue
                if lst.url:
                    seen_urls.add(lst.url)
                lst.product_name = normalize_product_name(lst.title)
                listings.append(lst)
        return listings


def _first_shipping_cost(item: dict) -> float | None:
    for opt in item.get("shippingOptions") or []:
        cost = opt.get("shippingCost") or {}
        value = cost.get("value")
        if value is not None:
            return float(value)
    return None


def _original_price(item: dict) -> float | None:
    """eBay's strikethrough / 'was' price, when the seller provides one."""
    mp = item.get("marketingPrice") or {}
    orig = mp.get("originalPrice") or {}
    value = orig.get("value")
    return float(value) if value is not None else None


def _buying_option(item: dict) -> str:
    opts = item.get("buyingOptions") or []
    return ", ".join(opts)


def _aspect_color(item: dict) -> str:
    """Extract Color from eBay localizedAspects when present."""
    for aspect in item.get("localizedAspects") or []:
        name = str(aspect.get("name", "")).lower()
        if name in ("color", "colour", "main color", "primary color"):
            return str(aspect.get("value", "")).strip()
    return ""
