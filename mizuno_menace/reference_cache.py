"""Persistent cache for official and catalog MSRP entries."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .paths import cache_dir, package_dir

OFFICIAL_CACHE_FILE = "mizuno_official.json"
CATALOG_CACHE_FILE = "catalog_msrp.json"
MISS_CACHE_FILE = "mizuno_miss.json"
CACHE_VERSION = 1
OFFICIAL_TTL_SECONDS = 7 * 86_400  # weekly refresh
MISS_TTL_SECONDS = 30 * 86_400     # don't re-fetch misses for 30 days


@dataclass
class PriceEntry:
    style_id: str
    msrp: float
    currency: str = "USD"
    source: str = "catalog"
    label: str = "Catalog MSRP"
    url: str = ""
    title: str = ""
    updated_at: float = 0.0

    @property
    def as_of_date(self) -> str:
        if not self.updated_at:
            return ""
        return time.strftime("%Y-%m-%d", time.localtime(self.updated_at))

    def is_fresh(self, ttl: int = OFFICIAL_TTL_SECONDS) -> bool:
        if not self.updated_at:
            return False
        return (time.time() - self.updated_at) < ttl


class ReferenceCache:
    def __init__(
        self,
        official_path: Path | None = None,
        catalog_path: Path | None = None,
    ):
        base = cache_dir()
        self.official_path = official_path or (base / OFFICIAL_CACHE_FILE)
        self.catalog_path = catalog_path or (base / CATALOG_CACHE_FILE)
        self.miss_path = base / MISS_CACHE_FILE
        self._official: dict[str, PriceEntry] = {}
        self._catalog: dict[str, PriceEntry] = {}
        self._miss: dict[str, float] = {}
        self._load_all()

    def _read_store(self, path: Path) -> dict[str, dict]:
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        if not isinstance(payload, dict):
            return {}
        entries = payload.get("entries", payload)
        return entries if isinstance(entries, dict) else {}

    def _write_store(self, path: Path, entries: dict[str, PriceEntry]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": CACHE_VERSION,
            "updated_at": time.time(),
            "entries": {
                key: asdict(entry) for key, entry in sorted(entries.items())
            },
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _entry_from_dict(self, style_id: str, raw: dict) -> PriceEntry:
        return PriceEntry(
            style_id=style_id,
            msrp=float(raw.get("msrp", 0)),
            currency=str(raw.get("currency", "USD") or "USD"),
            source=str(raw.get("source", "catalog")),
            label=str(raw.get("label", "Catalog MSRP")),
            url=str(raw.get("url", "")),
            title=str(raw.get("title", "")),
            updated_at=float(raw.get("updated_at", 0) or 0),
        )

    def _load_store(self, path: Path) -> dict[str, PriceEntry]:
        entries: dict[str, PriceEntry] = {}
        for key, raw in self._read_store(path).items():
            if not isinstance(raw, dict):
                continue
            style_id = str(raw.get("style_id") or key).upper()
            try:
                entries[style_id] = self._entry_from_dict(style_id, raw)
            except (TypeError, ValueError):
                continue
        return entries

    def _load_seed_catalog(self) -> None:
        seed_path = package_dir() / "data" / "catalog_seed.json"
        if not seed_path.exists():
            return
        try:
            payload = json.loads(seed_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        entries = payload.get("entries", payload)
        if not isinstance(entries, dict):
            return
        for key, raw in entries.items():
            if not isinstance(raw, dict):
                continue
            style_id = str(raw.get("style_id") or key).upper()
            if style_id in self._catalog:
                continue
            try:
                entry = self._entry_from_dict(style_id, raw)
                entry.source = "catalog"
                entry.label = "Catalog MSRP"
                if not entry.updated_at:
                    entry.updated_at = time.time()
                self._catalog[style_id] = entry
            except (TypeError, ValueError):
                continue

    def _load_all(self) -> None:
        self._official = self._load_store(self.official_path)
        self._catalog = self._load_store(self.catalog_path)
        self._miss = self._load_misses()
        self._load_seed_catalog()

    def _load_misses(self) -> dict[str, float]:
        if not self.miss_path.exists():
            return {}
        try:
            payload = json.loads(self.miss_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        entries = payload.get("entries", payload)
        if not isinstance(entries, dict):
            return {}
        out: dict[str, float] = {}
        for key, ts in entries.items():
            try:
                out[str(key).upper()] = float(ts)
            except (TypeError, ValueError):
                continue
        return out

    def _write_misses(self) -> None:
        self.miss_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": CACHE_VERSION,
            "updated_at": time.time(),
            "entries": self._miss,
        }
        self.miss_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def is_miss(self, style_id: str) -> bool:
        ts = self._miss.get(style_id.upper())
        if ts is None:
            return False
        return (time.time() - ts) < MISS_TTL_SECONDS

    def put_miss(self, style_id: str) -> None:
        self._miss[style_id.upper()] = time.time()
        self._write_misses()

    def get_official(self, style_id: str) -> PriceEntry | None:
        return self._official.get(style_id.upper())

    def get_catalog(self, style_id: str) -> PriceEntry | None:
        return self._catalog.get(style_id.upper())

    def put_official(self, entry: PriceEntry) -> None:
        key = entry.style_id.upper()
        entry.source = "mizuno_official"
        entry.label = "Mizuno MSRP"
        self._official[key] = entry
        self._catalog.setdefault(key, entry)
        self._write_store(self.official_path, self._official)
        self._write_store(self.catalog_path, self._catalog)

    def put_catalog(self, entry: PriceEntry) -> None:
        key = entry.style_id.upper()
        entry.source = "catalog"
        entry.label = "Catalog MSRP"
        self._catalog[key] = entry
        self._write_store(self.catalog_path, self._catalog)
