import pytest
from src.coordinators.domain_source import DomainSourceCoordinator

@pytest.mark.asyncio
class TestDomainSourceCoordinator:
    async def test_merge_dedup(self):
        coordinator = DomainSourceCoordinator()
        generated = [
            {"domain_name": "test.com", "source": "keyword_generator"},
            {"domain_name": "unique.com", "source": "keyword_generator"},
        ]
        feeds = [
            {"domain_name": "test.com", "source": "expireddomains", "dr": 25},
            {"domain_name": "feed.com", "source": "auctionfeed"},
        ]
        merged = coordinator._merge_domains(generated, feeds)
        assert len(merged) == 3  # 3 unique
        test_entry = [d for d in merged if d["domain_name"] == "test.com"][0]
        assert test_entry["source"] == "expireddomains"  # feed version wins
