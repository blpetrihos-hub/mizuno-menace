"""User scan preferences (deal count, sizes) from the settings page."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from .paths import user_data_dir
from .search_criteria import (
    APPAREL_SIZE,
    DEFAULT_SEARCH_SCOPE,
    SHOE_SIZE_US,
    normalize_apparel_size,
    normalize_custom_query,
    normalize_search_scope,
    normalize_shoe_size_us,
)

VALID_TOP = (10, 20, 30, 40, 50)
DEFAULT_TOP = 30

SETTINGS_FILE = "settings.json"


@dataclass
class ScanSettings:
    top: int = DEFAULT_TOP
    apparel_size: str = APPAREL_SIZE
    shoe_size_us: str = SHOE_SIZE_US
    search_scope: str = DEFAULT_SEARCH_SCOPE
    custom_query: str = ""

    def normalized(self) -> ScanSettings:
        top = self.top if self.top in VALID_TOP else DEFAULT_TOP
        return ScanSettings(
            top=top,
            apparel_size=normalize_apparel_size(self.apparel_size),
            shoe_size_us=normalize_shoe_size_us(self.shoe_size_us),
            search_scope=normalize_search_scope(self.search_scope),
            custom_query=normalize_custom_query(self.custom_query),
        )


def _settings_path():
    return user_data_dir() / SETTINGS_FILE


def load_scan_settings(default: ScanSettings | None = None) -> ScanSettings:
    base = (default or ScanSettings()).normalized()
    path = _settings_path()
    if not path.exists():
        return base
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return base
    if not isinstance(raw, dict):
        return base
    return ScanSettings(
        top=int(raw.get("top", base.top)),
        apparel_size=str(raw.get("apparel_size", base.apparel_size)),
        shoe_size_us=str(raw.get("shoe_size_us", base.shoe_size_us)),
        search_scope=str(raw.get("search_scope", base.search_scope)),
        custom_query=str(raw.get("custom_query", base.custom_query)),
    ).normalized()


def save_scan_settings(settings: ScanSettings) -> None:
    settings = settings.normalized()
    _settings_path().write_text(
        json.dumps(asdict(settings), indent=2),
        encoding="utf-8",
    )


def load_last_top(default: int = DEFAULT_TOP) -> int:
    return load_scan_settings(ScanSettings(top=default)).top


def save_last_top(top: int) -> None:
    current = load_scan_settings()
    current.top = top
    save_scan_settings(current)
