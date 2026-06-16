from __future__ import annotations

from abc import ABC, abstractmethod


class BaseCollector(ABC):
    def __init__(self, config: dict | None = None) -> None:
        self.config = config or {}

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
