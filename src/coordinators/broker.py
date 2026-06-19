"""Orchestrates the domain brokering pipeline — find, analyze, report."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from src.analyzers.broker import BrokerAnalyzer
from src.analyzers.commercial import CommercialAnalyzer
from src.analyzers.history import HistoryAnalyzer
from src.analyzers.seo import SEOAnalyzer
from src.analyzers.scoring import ScoringEngine
from src.checkers.rdap_checker import RDAPChecker
from src.config import settings

from src.database import Database
from src.feeds.auction_feed import AuctionFeed
from src.feeds.expireddomains_feed import ExpiredDomainsFeed
from src.generators.keyword_generator import KeywordGenerator
from src.generators.thesaurus_generator import ThesaurusGenerator
from src.constants import NICHES
from src.utils import setup_logger


class BrokerCoordinator:
    """Orchestrates domain brokering discovery + analysis pipeline."""

    def __init__(self, db: Optional[Database] = None) -> None:
        self.logger = setup_logger("BrokerCoordinator")
        self.keyword_gen = KeywordGenerator()
        self.thesaurus_gen = ThesaurusGenerator()
        self.checker = RDAPChecker()
        self.feeds = [ExpiredDomainsFeed(), AuctionFeed()]
        self.seo_analyzer = SEOAnalyzer()
        self.commercial_analyzer = CommercialAnalyzer()
        self.history_analyzer = HistoryAnalyzer()
        self.broker_analyzer = BrokerAnalyzer()
        self.scoring_engine = ScoringEngine()
        self.db = db or Database(settings.database_path)

    async def discover(self, max_domains: int = 200) -> list[dict[str, Any]]:
        """Discover broker-ready domains from generators + feeds.

        For brokering we want domains that:
        - Are expired/expiring (from feeds)
        - Have realistic resale value
        - Have potential buyer demand
        """
        candidates_task = self._collect_candidates()
        feeds_task = self._collect_feeds()
        candidates, feed_domains = await asyncio.gather(candidates_task, feeds_task)

        generated = await self._check_available(candidates)

        merged = self._merge_domains(generated, feed_domains)
        final = merged[:max_domains]

        self.logger.info(
            "Broker discovery: %d generated + %d feed = %d total",
            len(generated), len(feed_domains), len(final),
        )
        return final

    async def analyze_all(self, domains: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Run full broker analysis pipeline on collected domains."""
        self.logger.info("Broker-analyzing %d domains…", len(domains))
        semaphore = asyncio.Semaphore(10)

        async def analyze_one(domain: dict[str, Any]) -> Optional[dict[str, Any]]:
            async with semaphore:
                try:
                    name = domain["domain_name"]
                    niche = domain.get("category", "general")

                    history_task = self.history_analyzer.analyze(name)
                    seo_task = self.seo_analyzer.analyze(name)
                    commercial_task = self.commercial_analyzer.analyze(name)
                    broker_task = self.broker_analyzer.analyze(name, niche)

                    history, seo, commercial, broker = await asyncio.gather(
                        history_task, seo_task, commercial_task, broker_task,
                        return_exceptions=True,
                    )

                    if isinstance(history, Exception):
                        self.logger.warning("History failed for %s: %s", name, history)
                        history = {"cleanliness_score": 50, "trust_score": 50}
                    if isinstance(seo, Exception):
                        self.logger.warning("SEO failed for %s: %s", name, seo)
                        seo = {"dr": 0, "referring_domains": 0, "domain_age": 0, "seo_score": 0}
                    if isinstance(commercial, Exception):
                        self.logger.warning("Commercial failed for %s: %s", name, commercial)
                        commercial = {"category": "general", "commercial_score": 50}
                    if isinstance(broker, Exception):
                        self.logger.warning("Broker analysis failed for %s: %s", name, broker)
                        broker = {
                            "marketplace": {"is_listed": False, "listings": [], "min_price": 0, "score": 0},
                            "buyer_leads": {"total_leads": 0, "leads": []},
                            "estimated_value": 0,
                            "commission": {"amount": 0, "rate": 0.15},
                            "broker_score": 0,
                            "broker_grade": "Cold",
                        }

                    domain["dr"] = max(domain.get("dr", 0) or 0, seo.get("dr", 0) or 0)
                    domain["referring_domains"] = max(domain.get("referring_domains", 0) or 0, seo.get("referring_domains", 0) or 0)
                    domain["domain_age"] = max(domain.get("domain_age", 0) or 0, seo.get("domain_age", 0) or 0)
                    domain["seo_score"] = seo.get("seo_score", 0) or 0
                    domain["cleanliness_score"] = history.get("cleanliness_score", 50) or 50
                    domain["trust_score"] = history.get("trust_score", 50) or 50
                    domain["category"] = commercial.get("category", "general") or "general"
                    domain["commercial_score"] = commercial.get("commercial_score", 50) or 50

                    domain["marketplace"] = broker.get("marketplace") or {}
                    domain["buyer_leads"] = broker.get("buyer_leads") or {"total_leads": 0, "leads": []}
                    domain["estimated_value"] = broker.get("estimated_value") or 0
                    domain["commission"] = broker.get("commission") or {"amount": 0, "rate": 0.15}
                    domain["broker_score"] = broker.get("broker_score") or 0
                    domain["broker_grade"] = broker.get("broker_grade") or "Cold"

                    result = self.scoring_engine.calculate(
                        domain=name,
                        price=domain.get("price", 0),
                        seo_score=domain["seo_score"],
                        commercial_score=domain["commercial_score"],
                        trust_score=domain["trust_score"],
                        cleanliness_score=domain["cleanliness_score"],
                    )

                    domain["final_score"] = result["final_score"]
                    domain["opportunity_grade"] = result["opportunity_grade"]
                    domain["reason"] = result.get("reason", "")

                    await self.db.save_domain(domain)
                    return domain

                except Exception as e:
                    self.logger.error("Failed to broker-analyze %s: %s", domain.get("domain_name"), e)
                    return None

        tasks = [analyze_one(d) for d in domains]
        results = await asyncio.gather(*tasks)
        analyzed: list[dict[str, Any]] = [r for r in results if r is not None]
        analyzed.sort(key=lambda x: x.get("broker_score") or 0, reverse=True)

        self.logger.info("Broker-analyzed %d domains successfully", len(analyzed))
        return analyzed

    async def _collect_candidates(self) -> list[str]:
        all_candidates: set[str] = set()
        for niche in NICHES:
            try:
                keywords = await self.keyword_gen.generate(niche, max_domains=50)
                all_candidates.update(keywords)
            except Exception as e:
                self.logger.warning("KeywordGenerator failed for niche '%s': %s", niche, e)
            try:
                thesaurus = await self.thesaurus_gen.generate(niche, max_domains=50)
                all_candidates.update(thesaurus)
            except Exception as e:
                self.logger.warning("ThesaurusGenerator failed for niche '%s': %s", niche, e)

        candidates = list(all_candidates)
        if len(candidates) > 500:
            candidates = candidates[:500]
        self.logger.info("Collected %d unique domain candidates", len(candidates))
        return candidates

    async def _collect_feeds(self) -> list[dict]:
        tasks = [feed.fetch() for feed in self.feeds]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_domains: list[dict] = []
        for feed, result in zip(self.feeds, results):
            if isinstance(result, Exception):
                self.logger.error("Feed %s failed: %s", feed.source, result)
            else:
                self.logger.info("Feed %s returned %d domains", feed.source, len(result))
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
        self.logger.info("%d / %d generated candidates are available", len(available), len(candidates))
        return available

    def _merge_domains(self, generated: list[dict], feed_domains: list[dict]) -> list[dict]:
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
        return merged
