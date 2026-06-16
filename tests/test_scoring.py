import pytest
from src.analyzers.scoring import ScoringEngine

@pytest.fixture
def engine():
    return ScoringEngine()

@pytest.mark.asyncio
class TestScoringEngine:
    async def test_perfect_scores(self, engine):
        result = engine.calculate("perfect.com", 10, 100, 100, 100, 100)
        assert result["final_score"] == 100.0
        assert result["opportunity_grade"] == "A+"

    async def test_low_scores(self, engine):
        result = engine.calculate("bad-domain-123456.info", 200, 5, 10, 5, 10)
        assert result["opportunity_grade"] == "Avoid"
        assert result["final_score"] < 30

    async def test_price_efficiency_cheap(self, engine):
        result = engine.calculate("cheap.com", 10, 50, 50, 50, 50)
        assert result["price_efficiency"] == 100.0

    async def test_price_efficiency_expensive(self, engine):
        result = engine.calculate("pricey.com", 200, 50, 50, 50, 50)
        assert result["price_efficiency"] <= 10

    async def test_a_grade(self, engine):
        result = engine.calculate("good.com", 50, 80, 75, 70, 80)
        assert result["opportunity_grade"] in ("A+", "A")

    async def test_rejection_unclean(self, engine):
        result = engine.calculate("bad.com", 50, 50, 50, 50, 10)
        assert result["opportunity_grade"] == "Avoid"
