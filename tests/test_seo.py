import pytest
from src.analyzers.seo import SEOAnalyzer

@pytest.mark.asyncio
class TestSEOAnalyzer:
    async def test_basic_analysis(self):
        analyzer = SEOAnalyzer()
        result = await analyzer.analyze("example.com")
        assert "seo_score" in result
        assert "dr" in result
        assert "referring_domains" in result
        assert "domain_age" in result
