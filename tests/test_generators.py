import pytest
from src.generators.keyword_generator import KeywordGenerator
from src.generators.thesaurus_generator import ThesaurusGenerator

@pytest.mark.asyncio
class TestKeywordGenerator:
    async def test_generate_returns_strings(self):
        gen = KeywordGenerator()
        result = await gen.generate("ai", 50)
        assert len(result) > 0
        assert all(isinstance(d, str) for d in result)
        assert all(len(d) >= 3 for d in result)
    
    async def test_generate_general(self):
        gen = KeywordGenerator()
        result = await gen.generate("general", 100)
        assert len(result) <= 100
        assert len(result) >= 10
    
    async def test_generate_ai_niche(self):
        gen = KeywordGenerator()
        result = await gen.generate("ai", 50)
        # Should contain AI-related terms
        has_ai_term = any("ai" in d or "intelligence" in d or "neural" in d for d in result)
        assert has_ai_term, f"No AI terms found in: {result[:10]}"
    
    async def test_generate_no_hyphens(self):
        gen = KeywordGenerator()
        result = await gen.generate("general", 50)
        assert all("-" not in d for d in result)

@pytest.mark.asyncio
class TestThesaurusGenerator:
    async def test_generate_with_exclude(self):
        gen = ThesaurusGenerator()
        exclude = {"aifinance", "healthtech"}
        result = await gen.generate("ai", 30, exclude=exclude)
        assert len(result) > 0
        for d in result:
            assert d not in exclude
    
    async def test_generate_variety(self):
        gen = ThesaurusGenerator()
        result = await gen.generate("finance", 50)
        # Should have variety from thesaurus expansion
        assert len(set(result)) >= 5
