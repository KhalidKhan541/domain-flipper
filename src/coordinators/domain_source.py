"""Orchestrates domain generation, availability checking, and feed collection."""

from src.utils import setup_logger
from src.config import settings
from src.generators.keyword_generator import KeywordGenerator
from src.generators.thesaurus_generator import ThesaurusGenerator
from src.checkers.rdap_checker import RDAPChecker
from src.feeds.expireddomains_feed import ExpiredDomainsFeed
from src.feeds.auction_feed import AuctionFeed
from src.database import Database
import asyncio
from typing import Optional


NICHES = [
    "ai", "saas", "finance", "health", "ecommerce",
    "education", "cybersecurity", "realestate", "productivity", "legal",
]


class DomainSourceCoordinator:
    """Coordinates domain discovery from all free sources."""

    def __init__(self, db: Optional[Database] = None):
        self.logger = setup_logger("DomainSourceCoordinator")
        self.keyword_gen = KeywordGenerator()
        self.thesaurus_gen = ThesaurusGenerator()
        self.checker = RDAPChecker()
        self.feeds = [ExpiredDomainsFeed(), AuctionFeed()]
        self.db = db or Database(settings.database_path)

    async def discover(self, max_domains: int = 200) -> list[dict]:
        """Run all discovery methods and return unique, available domains.

        Pipeline:
        1. Generate domain name candidates from keywords
        2. Collect expired domains from feeds
        3. Check availability via RDAP
        4. Return unified list of domain dicts
        """
        candidates_task = self._collect_candidates()
        feeds_task = self._collect_feeds()

        candidates, feed_domains = await asyncio.gather(candidates_task, feeds_task)

        generated = await self._check_available(candidates)

        merged = self._merge_domains(generated, feed_domains)

        final = merged[:max_domains]

        self.logger.info(
            "Discovery complete: %d generated available, %d feed domains, %d total",
            len(generated), len(feed_domains), len(final),
        )

        return final

    async def _collect_candidates(self) -> list[str]:
        """Collect domain name candidates from all generators."""
        all_candidates: set[str] = set()

        for niche in NICHES:
            try:
                keywords = await self.keyword_gen.generate(niche, max_domains=50)
                all_candidates.update(keywords)
            except Exception as e:
                self.logger.warning(
                    "KeywordGenerator failed for niche '%s': %s", niche, e
                )

            try:
                thesaurus = await self.thesaurus_gen.generate(niche, max_domains=50)
                all_candidates.update(thesaurus)
            except Exception as e:
                self.logger.warning(
                    "ThesaurusGenerator failed for niche '%s': %s", niche, e
                )

        candidates = list(all_candidates)
        if len(candidates) > 500:
            candidates = candidates[:500]

        self.logger.info("Collected %d unique domain candidates", len(candidates))
        return candidates

    async def _collect_feeds(self) -> list[dict]:
        """Collect domains from all feed sources."""
        tasks = [feed.fetch() for feed in self.feeds]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_domains: list[dict] = []
        for feed, result in zip(self.feeds, results):
            if isinstance(result, Exception):
                self.logger.error("Feed %s failed: %s", feed.source, result)
            else:
                self.logger.info(
                    "Feed %s returned %d domains", feed.source, len(result)
                )
                all_domains.extend(result)

        seen: set[str] = set()
        unique: list[dict] = []
        for d in all_domains:
            name = d.get("domain_name", "")
            if name and name not in seen:
                seen.add(name)
                unique.append(d)

        self.logger.info("Collected %d unique feed domains", len(unique))
        return unique

    async def _check_available(self, candidates: list[str]) -> list[dict]:
        """Check which generated names are available and return as domain dicts."""
        domains_to_check = [f"{candidate}.com" for candidate in candidates]

        try:
            results = await self.checker.check_batch(domains_to_check)
        except Exception as e:
            self.logger.error("RDAP batch check failed: %s", e)
            return []

        available: list[dict] = []
        for candidate, result in zip(candidates, results):
            if result.get("available", False):
                available.append({
                    "domain_name": f"{candidate}.com",
                    "price": 12.0,
                    "auction_end_date": "",
                    "registrar": "",
                    "tld": "com",
                    "source": "keyword_generator",
                    "dr": 0,
                    "referring_domains": 0,
                    "domain_age": 0,
                })

        self.logger.info(
            "%d / %d generated candidates are available",
            len(available), len(candidates),
        )
        return available

    def _merge_domains(
        self, generated: list[dict], feed_domains: list[dict]
    ) -> list[dict]:
        """Merge generated and feed domains, deduplicating by domain_name."""
        seen: set[str] = set()
        merged: list[dict] = []

        for d in feed_domains:
            name = d.get("domain_name", "")
            if name and name not in seen:
                seen.add(name)
                merged.append(d)

        for d in generated:
            name = d.get("domain_name", "")
            if name and name not in seen:
                seen.add(name)
                merged.append(d)

        self.logger.info(
            "Merged %d feed + %d generated = %d unique domains",
            len(feed_domains), len(generated), len(merged),
        )
        return merged
