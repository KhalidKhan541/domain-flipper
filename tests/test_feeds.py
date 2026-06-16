import pytest
from src.feeds.expireddomains_feed import ExpiredDomainsFeed
from src.feeds.auction_feed import AuctionFeed

@pytest.mark.asyncio
class TestExpiredDomainsFeed:
    async def test_fallback_returns_domains(self):
        feed = ExpiredDomainsFeed()
        # Force fallback by not making real HTTP calls  
        result = feed._fallback_list()
        assert len(result) >= 50
        assert all("." in d for d in result)

@pytest.mark.asyncio
class TestAuctionFeed:
    async def test_fallback_returns_domains(self):
        feed = AuctionFeed()
        result = feed._fallback_list()
        assert len(result) >= 50
        assert all("." in d for d in result)
