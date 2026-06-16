from abc import ABC, abstractmethod
from typing import Any

class BaseDomainGenerator(ABC):
    """Generates domain name candidates for a given niche."""
    
    @abstractmethod
    async def generate(self, niche: str = "general", count: int = 100) -> list[str]:
        """Return a list of domain name candidates (SLD only, no TLD)."""
        pass
