"""Configuration loaded from environment / .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .paths import find_config

try:
    from dotenv import load_dotenv

    _env = find_config(".env")
    load_dotenv(_env) if _env else load_dotenv()
except Exception:  # dotenv is optional at runtime
    pass


@dataclass
class EbayConfig:
    client_id: str | None
    client_secret: str | None
    env: str
    marketplace_id: str

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    @property
    def oauth_url(self) -> str:
        if self.env == "sandbox":
            return "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
        return "https://api.ebay.com/identity/v1/oauth2/token"

    @property
    def browse_url(self) -> str:
        if self.env == "sandbox":
            return "https://api.sandbox.ebay.com/buy/browse/v1/item_summary/search"
        return "https://api.ebay.com/buy/browse/v1/item_summary/search"


def load_ebay_config() -> EbayConfig:
    return EbayConfig(
        client_id=os.getenv("EBAY_CLIENT_ID"),
        client_secret=os.getenv("EBAY_CLIENT_SECRET"),
        env=os.getenv("EBAY_ENV", "production").strip().lower(),
        marketplace_id=os.getenv("EBAY_MARKETPLACE_ID", "EBAY_US").strip(),
    )
