import random

from src.utils import setup_logger
from src.generators.base import BaseDomainGenerator
from src.generators.keyword_generator import (
    NICHE_KEYWORDS,
    PREFIXES,
    SUFFIXES,
    _get_keywords,
    _is_valid_candidate,
)

logger = setup_logger(__name__)

THESAURUS = {
    "ai": ["cognitive", "neural", "intelligent"],
    "finance": ["money", "capital", "wealth", "funding"],
    "health": ["wellness", "vitality", "medical"],
    "fast": ["swift", "quick", "rapid", "turbo", "hyper"],
    "big": ["mega", "macro", "vast", "massive", "giant"],
    "small": ["micro", "nano", "mini", "tiny"],
    "new": ["fresh", "novel", "prime", "pioneer"],
    "smart": ["clever", "sharp", "bright", "genius", "witty"],
    "best": ["top", "prime", "elite", "premium", "ace"],
    "first": ["prime", "alpha", "beta", "pilot", "dawn"],
    "future": ["next", "pro", "ultra", "beyond", "frontier"],
}


def _expand_with_thesaurus(keywords: list[str]) -> list[str]:
    expanded = set(keywords)
    for kw in keywords:
        synonyms = THESAURUS.get(kw, [])
        for syn in synonyms:
            expanded.add(syn)
    return list(expanded)


class ThesaurusGenerator(BaseDomainGenerator):
    def __init__(self) -> None:
        self._prefixes = PREFIXES
        self._suffixes = SUFFIXES

    async def generate(
        self, niche: str = "general", count: int = 100, exclude: set[str] | None = None
    ) -> list[str]:
        exclude = exclude or set()
        base_keywords = _get_keywords(niche)
        if not base_keywords:
            logger.warning("No keywords found for niche: %s", niche)
            return []

        keywords = _expand_with_thesaurus(base_keywords)
        candidates: set[str] = set()

        # a. Direct keywords
        for kw in keywords:
            if _is_valid_candidate(kw):
                candidates.add(kw.lower())

        # b. Compound words
        for kw1 in keywords:
            for kw2 in keywords:
                compound = kw1 + kw2
                if _is_valid_candidate(compound):
                    candidates.add(compound.lower())

        # c. Prefix + keyword
        for prefix in self._prefixes:
            for kw in keywords:
                pk = prefix + kw
                if _is_valid_candidate(pk):
                    candidates.add(pk.lower())

        # d. Keyword + suffix
        for kw in keywords:
            for suffix in self._suffixes:
                ks = kw + suffix
                if _is_valid_candidate(ks):
                    candidates.add(ks.lower())

        # e. Prefix + suffix (brandable)
        for prefix in self._prefixes:
            for suffix in self._suffixes:
                ps = prefix + suffix
                if _is_valid_candidate(ps):
                    candidates.add(ps.lower())

        # f. Truncated compounds
        for kw1 in keywords:
            for kw2 in keywords:
                if kw1 != kw2:
                    trunc = kw1[:4] + kw2[:3]
                    if _is_valid_candidate(trunc):
                        candidates.add(trunc.lower())

        # Deduplicate against excluded set
        candidates -= exclude

        result = sorted(candidates)
        random.shuffle(result)
        result = result[:count]

        logger.info(
            "Generated %d thesaurus-expanded domain candidates for niche='%s'",
            len(result),
            niche,
        )
        return result
