"""Extract Mizuno style / MPN identifiers from listing metadata."""

from __future__ import annotations

import re
from urllib.parse import unquote, urlparse

_STYLE_FROM_URL = re.compile(
    r"^https?://(?:www\.)?foot-store\.com/([a-z0-9]+)-",
    re.I,
)
_STYLE_TOKEN = re.compile(r"^[A-Z0-9]{6,16}$")
_MPN_IN_TITLE = re.compile(
    r"\b([A-Z]{1,2}\d[A-Z0-9]{5,12}|\d{5,6}[A-Z0-9-]*)\b",
    re.I,
)

_EBAY_STYLE_ASPECTS = (
    "mpn",
    "manufacturer part number",
    "style code",
    "style number",
    "style #",
    "model",
    "model number",
)


def normalize_style_id(value: str | None) -> str:
    """Canonical style key: uppercase alphanumeric only."""
    if not value:
        return ""
    cleaned = re.sub(r"[^A-Za-z0-9]", "", value.strip())
    return cleaned.upper()


def style_from_footstore_url(url: str) -> str:
    match = _STYLE_FROM_URL.match(url.strip())
    if not match:
        return ""
    return normalize_style_id(match.group(1))


def style_from_footstore_offers(offers) -> str:
    """Read MPN from foot-store JSON-LD offers."""
    if offers is None:
        return ""
    if isinstance(offers, dict):
        offers = [offers]
    for off in offers:
        if not isinstance(off, dict):
            continue
        for key in ("mpn", "MPN", "sku", "SKU"):
            value = off.get(key)
            if value:
                normalized = normalize_style_id(str(value))
                if normalized and not normalized.startswith("MAG"):
                    return normalized
    return ""


def style_from_ebay_aspects(aspects: list[dict] | None) -> str:
    if not aspects:
        return ""
    for aspect in aspects:
        name = str(aspect.get("name", "")).strip().lower()
        if name not in _EBAY_STYLE_ASPECTS:
            continue
        value = normalize_style_id(str(aspect.get("value", "")))
        if value:
            return value
    return ""


def style_from_title(title: str) -> str:
    """Best-effort MPN token from a listing title."""
    for match in _MPN_IN_TITLE.finditer(title.upper()):
        token = normalize_style_id(match.group(1))
        if _STYLE_TOKEN.match(token):
            return token
    return ""


def resolve_style_id(
    *,
    url: str = "",
    footstore_offers=None,
    ebay_aspects: list[dict] | None = None,
    title: str = "",
) -> str:
    """Resolve a style id from the strongest available signal."""
    for candidate in (
        style_from_footstore_offers(footstore_offers),
        style_from_footstore_url(url),
        style_from_ebay_aspects(ebay_aspects),
        style_from_title(title),
    ):
        if candidate:
            return candidate
    return ""


def mizuno_product_url_from_search_href(href: str) -> str:
    """Normalize a Mizuno USA search-result product href."""
    href = unquote(href.replace("&#x3D;", "=").replace("&amp;", "&"))
    if href.startswith("/"):
        href = f"https://usa.mizuno.com{href}"
    parsed = urlparse(href)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def likely_mizuno_usa_style(style_id: str) -> bool:
    """True when a style id might exist on usa.mizuno.com (skip futile lookups)."""
    style_id = normalize_style_id(style_id)
    if not style_id:
        return False
    # US site SKUs are usually 5–7 digit numeric style numbers.
    if style_id.isdigit() and 5 <= len(style_id) <= 7:
        return True
    return False


def likely_mizuno_eu_style(style_id: str) -> bool:
    """True for foot-store / EMEA article numbers (e.g. 32FE9A0609, J2GBB00308)."""
    style_id = normalize_style_id(style_id)
    if not style_id or likely_mizuno_usa_style(style_id):
        return False
    if re.match(r"^[A-Z]{1,2}\d[A-Z0-9]{4,}$", style_id):
        return True
    if re.match(r"^\d{2}[A-Z]{2}[A-Z0-9]{4,}$", style_id):
        return True
    return len(style_id) >= 8 and style_id[0].isalpha()
