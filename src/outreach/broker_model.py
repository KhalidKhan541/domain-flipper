from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from src.integrations.social_search import SocialSearcher
from src.config import settings

logger = logging.getLogger(__name__)

BROKER_DATA_FILE = Path("data/broker_leads.json")


class BrokerModel:
    """
    Zero-cost domain brokering model.
    
    Flow:
    1. Find buyers looking for domains in specific niches (Reddit, Twitter, HN)
    2. Find registered domains that match those niches (parked/for-sale)
    3. Connect buyer with domain owner
    4. Take 15% commission on the deal
    """

    def __init__(self) -> None:
        self.social = SocialSearcher(
            twitter_bearer_token=getattr(settings, "twitter_bearer_token", None),
        )
        self._leads = self._load_leads()

    def _load_leads(self) -> dict[str, Any]:
        if BROKER_DATA_FILE.exists():
            try:
                return json.loads(BROKER_DATA_FILE.read_text())
            except (json.JSONDecodeError, KeyError):
                return {"buyers": [], "sellers": [], "deals": []}
        return {"buyers": [], "sellers": [], "deals": []}

    def _save_leads(self) -> None:
        BROKER_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        BROKER_DATA_FILE.write_text(json.dumps(self._leads, indent=2))

    async def find_buyers(self, niche: str) -> list[dict[str, Any]]:
        """
        Find people actively looking to buy domains in a niche.
        These are warm leads — they already want what you can broker.
        """
        logger.info("Finding buyers for niche: %s", niche)

        buyers: list[dict[str, Any]] = []

        # Search Reddit for domain-buying intent
        try:
            reddit_buyers = await self._search_reddit_buyers(niche)
            buyers.extend(reddit_buyers)
            logger.info("Found %d Reddit buyers for %s", len(reddit_buyers), niche)
        except Exception as exc:
            logger.error("Reddit buyer search failed: %s", exc)

        # Search Twitter for domain-buying intent
        try:
            twitter_buyers = await self._search_twitter_buyers(niche)
            buyers.extend(twitter_buyers)
            logger.info("Found %d Twitter buyers for %s", len(twitter_buyers), niche)
        except Exception as exc:
            logger.error("Twitter buyer search failed: %s", exc)

        # Search HN for domain-buying intent
        try:
            hn_buyers = await self._search_hn_buyers(niche)
            buyers.extend(hn_buyers)
            logger.info("Found %d HN buyers for %s", len(hn_buyers), niche)
        except Exception as exc:
            logger.error("HN buyer search failed: %s", exc)

        # Deduplicate by email/username
        seen: set[str] = set()
        unique_buyers: list[dict[str, Any]] = []
        for buyer in buyers:
            key = buyer.get("email") or buyer.get("username", "")
            if key and key not in seen:
                seen.add(key)
                unique_buyers.append(buyer)

        logger.info("Total unique buyers for %s: %d", niche, len(unique_buyers))
        return unique_buyers

    async def find_sellers(self, niche: str) -> list[dict[str, Any]]:
        """
        Find domains that are registered but might be for sale.
        Look for parked domains, 'for sale' pages, etc.
        """
        logger.info("Finding potential sellers for niche: %s", niche)

        sellers: list[dict[str, Any]] = []

        # Search for domains with "for sale" pages
        try:
            sale_domains = await self._find_for_sale_domains(niche)
            sellers.extend(sale_domains)
            logger.info("Found %d domains with 'for sale' pages", len(sale_domains))
        except Exception as exc:
            logger.error("For-sale domain search failed: %s", exc)

        # Search expired domains that might have been re-registered
        try:
            reregistered = await self._find_reregistered_domains(niche)
            sellers.extend(reregistered)
            logger.info("Found %d re-registered domains", len(reregistered))
        except Exception as exc:
            logger.error("Re-registered domain search failed: %s", exc)

        logger.info("Total potential sellers for %s: %d", niche, len(sellers))
        return sellers

    async def match_buyers_sellers(
        self, buyers: list[dict], sellers: list[dict]
    ) -> list[dict[str, Any]]:
        """
        Match buyers with potential domains.
        Returns deal opportunities with estimated commission.
        """
        deals: list[dict[str, Any]] = []

        for seller in sellers:
            domain = seller.get("domain", "")
            asking_price = seller.get("asking_price", 0)
            owner_email = seller.get("owner_email", "")

            for buyer in buyers:
                niche_match = buyer.get("niche", "").lower() in domain.lower()
                if niche_match and owner_email:
                    commission = int(asking_price * 0.15)
                    deals.append({
                        "domain": domain,
                        "buyer_username": buyer.get("username", ""),
                        "buyer_email": buyer.get("email", ""),
                        "buyer_source": buyer.get("source", ""),
                        "seller_email": owner_email,
                        "asking_price": asking_price,
                        "estimated_commission": commission,
                        "status": "matched",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    })

        logger.info("Matched %d deal opportunities", len(deals))
        return deals

    async def _search_reddit_buyers(self, niche: str) -> list[dict[str, Any]]:
        """Search Reddit for people looking to buy domains."""
        buyers: list[dict[str, Any]] = []

        search_queries = [
            f"looking to buy {niche} domain",
            f"want to purchase {niche} domain",
            f"need {niche} domain for sale",
            f"buying {niche} domain",
        ]

        async with httpx.AsyncClient(timeout=15.0) as client:
            for query in search_queries:
                try:
                    headers = {"User-Agent": "DomainBroker/1.0"}
                    resp = await client.get(
                        "https://www.reddit.com/search.json",
                        params={"q": query, "limit": 10, "sort": "new"},
                        headers=headers,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        for child in data.get("data", {}).get("children", []):
                            post = child.get("data", {})
                            author = post.get("author", "")
                            title = post.get("title", "")
                            selftext = post.get("selftext", "")
                            url = post.get("url", "")

                            if author and author != "[deleted]":
                                buyers.append({
                                    "username": author,
                                    "email": "",
                                    "source": "reddit",
                                    "niche": niche,
                                    "post_title": title,
                                    "post_url": f"https://reddit.com{url}",
                                    "intent_score": self._score_intent(title + " " + selftext),
                                })
                except Exception as exc:
                    logger.debug("Reddit query failed: %s: %s", query, exc)

        return buyers

    async def _search_twitter_buyers(self, niche: str) -> list[dict[str, Any]]:
        """Search Twitter for people looking to buy domains."""
        buyers: list[dict[str, Any]] = []

        bearer_token = getattr(settings, "twitter_bearer_token", None)
        if not bearer_token:
            return buyers

        search_queries = [
            f"looking to buy {niche} domain",
            f"want {niche} domain",
            f"buying {niche} domain",
        ]

        async with httpx.AsyncClient(timeout=15.0) as client:
            for query in search_queries:
                try:
                    resp = await client.get(
                        "https://api.twitter.com/2/tweets/search/recent",
                        params={
                            "query": query,
                            "max_results": 10,
                            "tweet.fields": "author_id,text",
                        },
                        headers={"Authorization": f"Bearer {bearer_token}"},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        for tweet in data.get("data", []):
                            author_id = tweet.get("author_id", "")
                            text = tweet.get("text", "")
                            buyers.append({
                                "username": f"twitter:{author_id}",
                                "email": "",
                                "source": "twitter",
                                "niche": niche,
                                "post_title": text[:100],
                                "post_url": f"https://twitter.com/i/status/{tweet.get('id', '')}",
                                "intent_score": self._score_intent(text),
                            })
                except Exception as exc:
                    logger.debug("Twitter query failed: %s: %s", query, exc)

        return buyers

    async def _search_hn_buyers(self, niche: str) -> list[dict[str, Any]]:
        """Search Hacker News for people looking to buy domains."""
        buyers: list[dict[str, Any]] = []

        search_queries = [
            f"looking to buy {niche} domain",
            f"want {niche} domain",
            f"buying {niche} domain",
        ]

        async with httpx.AsyncClient(timeout=15.0) as client:
            for query in search_queries:
                try:
                    resp = await client.get(
                        "https://hn.algolia.com/api/v1/search_by_date",
                        params={"query": query, "tags": "story", "hitsPerPage": 10},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        for hit in data.get("hits", []):
                            author = hit.get("author", "")
                            title = hit.get("title", "")
                            url = hit.get("url", "")
                            points = hit.get("points", 0)

                            if author:
                                buyers.append({
                                    "username": author,
                                    "email": "",
                                    "source": "hackernews",
                                    "niche": niche,
                                    "post_title": title,
                                    "post_url": url or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}",
                                    "intent_score": self._score_intent(title) + min(points, 20),
                                })
                except Exception as exc:
                    logger.debug("HN query failed: %s: %s", query, exc)

        return buyers

    async def _find_for_sale_domains(self, niche: str) -> list[dict[str, Any]]:
        """Find domains with 'for sale' landing pages."""
        sellers: list[dict[str, Any]] = []

        # Common domain patterns for a niche
        keywords = self._extract_keywords(niche)
        tlds = ["com", "io", "ai", "co", "net"]

        potential_domains = []
        for kw in keywords:
            for tld in tlds:
                potential_domains.append(f"{kw}.{tld}")
                potential_domains.append(f"{kw}-{niche}.{tld}")

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            for domain in potential_domains[:30]:  # Limit to avoid rate limits
                try:
                    resp = await client.get(f"http://{domain}", follow_redirects=True)
                    text = resp.text.lower()

                    # Check for "for sale" indicators
                    for_sale_indicators = [
                        "for sale", "buy now", "make offer", "price",
                        "contact us", "inquire", "purchase", "domain for sale",
                    ]
                    if any(indicator in text for indicator in for_sale_indicators):
                        # Extract price if mentioned
                        price = self._extract_price(text)
                        sellers.append({
                            "domain": domain,
                            "asking_price": price,
                            "owner_email": self._extract_contact_email(text),
                            "source": "for-sale-page",
                            "niche": niche,
                        })
                        logger.info("Found for-sale domain: %s ($%d)", domain, price)

                except Exception:
                    continue  # Domain doesn't resolve or error

        return sellers

    async def _find_reregistered_domains(self, niche: str) -> list[dict[str, Any]]:
        """Find domains that were recently re-registered (potential flips)."""
        # This is a placeholder — in production you'd use WHOIS history APIs
        return []

    def _extract_keywords(self, niche: str) -> list[str]:
        """Extract keywords from niche for domain guessing."""
        base_keywords = {
            "ai": ["aitools", "aiapp", "aitech", "myai", "useai", "getai", "aipro"],
            "saas": ["saasapp", "mysaas", "saastool", "cloudapp", "myapp", "webapp"],
            "finance": ["fintech", "mymoney", "payapp", "wallet", "invest", "trading"],
            "health": ["healthapp", "medtech", "wellness", "fitness", "myhealth"],
            "ecommerce": ["shopapp", "mystore", "buyapp", "myshop", "ecom"],
            "education": ["learnapp", "edtech", "mycourse", "study", "teach"],
            "security": ["cyber", "protect", "safe", "secure", "privacy"],
        }
        return base_keywords.get(niche, [niche, f"{niche}app", f"my{niche}"])

    def _score_intent(self, text: str) -> int:
        """Score buying intent from text."""
        score = 0
        text_lower = text.lower()

        high_intent = ["looking to buy", "want to buy", "need a domain", "buying domain"]
        medium_intent = ["interested in", "anyone know", "recommendations for"]
        low_intent = ["domain", "website", "online"]

        for phrase in high_intent:
            if phrase in text_lower:
                score += 30
        for phrase in medium_intent:
            if phrase in text_lower:
                score += 15
        for phrase in low_intent:
            if phrase in text_lower:
                score += 5

        return min(score, 100)

    def _extract_price(self, text: str) -> int:
        """Extract price from page text."""
        patterns = [
            r"\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)",
            r"price[:\s]*\$?(\d{1,3}(?:,\d{3})*)",
            r"(\d{1,3}(?:,\d{3})*)\s*(?:usd|dollars?)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                price_str = match.group(1).replace(",", "")
                try:
                    return int(float(price_str))
                except ValueError:
                    continue
        return 0

    def _extract_contact_email(self, text: str) -> str:
        """Extract contact email from page text."""
        email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        matches = re.findall(email_pattern, text)
        # Filter out common non-contact emails
        filtered = [e for e in matches if not any(x in e.lower() for x in ["example", "test", "noreply", "no-reply"])]
        return filtered[0] if filtered else ""

    async def run_broker_pipeline(self, niche: str) -> dict[str, Any]:
        """
        Run the full broker pipeline for a niche.
        Returns matched deals ready for outreach.
        """
        logger.info("Running broker pipeline for niche: %s", niche)

        # Find buyers and sellers in parallel
        buyers, sellers = await asyncio.gather(
            self.find_buyers(niche),
            self.find_sellers(niche),
        )

        # Match them
        deals = await self.match_buyers_sellers(buyers, sellers)

        # Save results
        self._leads["buyers"].extend(buyers)
        self._leads["sellers"].extend(sellers)
        self._leads["deals"].extend(deals)
        self._save_leads()

        result = {
            "niche": niche,
            "buyers_found": len(buyers),
            "sellers_found": len(sellers),
            "deals_matched": len(deals),
            "deals": deals,
            "top_buyers": sorted(buyers, key=lambda x: x.get("intent_score", 0), reverse=True)[:5],
            "top_sellers": sellers[:5],
        }

        logger.info(
            "Broker pipeline complete for %s: %d buyers, %d sellers, %d deals",
            niche, len(buyers), len(sellers), len(deals),
        )

        return result
