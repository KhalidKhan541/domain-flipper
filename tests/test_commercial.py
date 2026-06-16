import pytest
from src.analyzers.commercial import CommercialAnalyzer

@pytest.mark.asyncio
class TestCommercialAnalyzer:
    async def test_ai_category(self):
        analyzer = CommercialAnalyzer()
        result = await analyzer.analyze("aichatbot.com")
        assert result["category"] == "ai"

    async def test_finance_category(self):
        analyzer = CommercialAnalyzer()
        result = await analyzer.analyze("stockinvest.com")
        assert result["category"] == "finance"

    async def test_general_category(self):
        analyzer = CommercialAnalyzer()
        result = await analyzer.analyze("randomnamexyz.com")
        assert result["category"] == "general"

    async def test_brandability_short(self):
        analyzer = CommercialAnalyzer()
        result = await analyzer.analyze("go.com")
        assert result["brandability"] >= 60

    async def test_brandability_long_hyphenated(self):
        analyzer = CommercialAnalyzer()
        result = await analyzer.analyze("the-best-online-store-123.com")
        assert result["brandability"] < 60
