"""Base class for price sources."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Listing


class PriceSource(ABC):
    """A pluggable provider that returns priced listings for a search term.

    Add a new website by subclassing this and implementing `search`.
    """

    #: Short, human-readable name shown in output (e.g. "eBay").
    name: str = "source"

    @property
    def available(self) -> bool:
        """Whether this source is usable right now (e.g. has credentials)."""
        return True

    @abstractmethod
    def search(self, query: str, limit: int = 10, **kwargs) -> list[Listing]:
        """Return up to `limit` listings for `query`.

        Optional kwargs (used by sources that support them, ignored otherwise):
          * category_id: str | None  - eBay category for aspect filtering
          * aspects: dict[str, str]  - eBay aspect filters, e.g. {"Size": "M"}
        """
        raise NotImplementedError
