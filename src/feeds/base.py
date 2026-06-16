from abc import ABC, abstractmethod


class BaseFeed(ABC):
    source: str = "base"

    @abstractmethod
    async def fetch(self, max_domains: int = 200) -> list[dict]:
        pass
