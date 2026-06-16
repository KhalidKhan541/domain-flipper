import pytest
from unittest.mock import patch, MagicMock
from src.analyzers.history import HistoryAnalyzer

@pytest.mark.asyncio
class TestHistoryAnalyzer:
    async def test_clean_domain(self):
        analyzer = HistoryAnalyzer()
        result = await analyzer.analyze("example.com")
        assert "cleanliness_score" in result
        assert "trust_score" in result
        assert 0 <= result["cleanliness_score"] <= 100
        assert 0 <= result["trust_score"] <= 100
