from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseCollector(ABC):
    source: str = "base"

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._offline_mode: bool = getattr(config, "offline_mode", False) if config else False

    @abstractmethod
    async def collect(self) -> list[dict]:
        """Collect domains from this source.

        Each domain dict must have:
        - domain_name: str
        - price: float (0 if unknown/auction)
        - auction_end_date: str (ISO format or empty)
        - registrar: str
        - tld: str
        - source: str (constant identifying this marketplace)
        - dr: int (default 0, will be enriched)
        - referring_domains: int (default 0)
        - domain_age: int (default 0)
        """

    async def _collect_offline(self) -> list[dict]:
        """Return mock data when in offline mode. Override in subclasses."""
        import asyncio
        await asyncio.sleep(0.01)
        return []
