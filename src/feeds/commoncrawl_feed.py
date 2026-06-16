from __future__ import annotations

import json
import random
import re
from typing import Any

import httpx

from src.config import settings
from src.feeds.base import BaseFeed
from src.utils import setup_logger

NICHE_KEYWORDS = {
    "ai": ["ai", "intelligence", "machine", "deep", "neural", "gpt", "llm", "chatbot", "copilot", "genai"],
    "saas": ["saas", "cloud", "platform", "app", "dashboard", "analytics", "portal", "automation", "workflow", "software"],
    "finance": ["finance", "invest", "bank", "capital", "wealth", "stock", "crypto", "pay", "fund", "trade"],
    "health": ["health", "wellness", "fitness", "med", "care", "clinic", "therapy", "nutrition", "vitamin", "recovery"],
    "ecommerce": ["shop", "store", "buy", "cart", "product", "retail", "mall", "deal", "price", "offer"],
    "education": ["learn", "course", "academy", "school", "study", "train", "class", "tutor", "edu", "skill"],
    "cybersecurity": ["cyber", "security", "secure", "protect", "privacy", "vpn", "firewall", "encrypt", "defense", "shield"],
    "realestate": ["realty", "estate", "home", "house", "property", "rent", "apartment", "mortgage", "listing", "agent"],
    "productivity": ["productivity", "focus", "track", "manage", "plan", "organize", "task", "time", "habit", "goal"],
    "legal": ["legal", "law", "attorney", "lawyer", "justice", "rights", "contract", "patent", "trademark", "notary"],
}

DOMAIN_RE = re.compile(r"^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$")


class CommonCrawlFeed(BaseFeed):
    source = "commoncrawl"

    CC_API_BASE = "https://index.commoncrawl.org"
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    def __init__(self) -> None:
        self.logger = setup_logger("CommonCrawlFeed")

    async def fetch(self, max_domains: int = 200) -> list[dict]:
        if settings.offline_mode:
            self.logger.info("Offline mode, using fallback domain pool")
            domains = self._fallback_list()
            selected = random.sample(domains, min(max_domains, len(domains)))
            return [self._make_dict(d) for d in selected]

        latest = await self._get_latest_index()
        if not latest:
            self.logger.warning("No CC index found, using fallback")
            domains = self._fallback_list()[:max_domains]
            return [self._make_dict(d) for d in domains]

        found: set[str] = set()
        keywords = list(NICHE_KEYWORDS.keys())
        random.shuffle(keywords)
        per_niche = max(1, max_domains // len(keywords) * 2)

        for niche in keywords:
            kw = random.choice(NICHE_KEYWORDS[niche])
            try:
                urls = await self._search_index(latest, kw, limit=per_niche)
                for u in urls:
                    domain = self._extract_domain(u)
                    if domain and DOMAIN_RE.match(domain):
                        found.add(domain)
            except Exception as exc:
                self.logger.debug("CC search failed for '%s': %s", kw, exc)

            if len(found) >= max_domains * 2:
                break

        if not found:
            self.logger.warning("CC returned no domains, using fallback")
            domains = self._fallback_list()[:max_domains]
        else:
            domains = random.sample(list(found), min(max_domains, len(found)))

        self.logger.info("CommonCrawlFeed: %d domains from CC + fallback", len(domains))
        return [self._make_dict(d) for d in domains]

    async def _get_latest_index(self) -> str | None:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(self.CC_API_BASE)
                resp.raise_for_status()
                indexes = resp.json()
                if isinstance(indexes, list) and indexes:
                    latest = indexes[-1].get("id", "")
                    if latest:
                        return latest
            return None
        except Exception as exc:
            self.logger.debug("Failed to get CC index: %s", exc)
            return None

    async def _search_index(self, index: str, keyword: str, limit: int = 100) -> list[str]:
        url = f"{self.CC_API_BASE}/{index}-index"
        params = {
            "url": f"*{keyword}*.com*",
            "output": "json",
            "fl": "url",
            "limit": str(limit),
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url, params=params, headers={"User-Agent": self.USER_AGENT})
                resp.raise_for_status()
                urls: list[str] = []
                for line in resp.text.strip().split("\n"):
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            u = data.get("url", "")
                            if u:
                                urls.append(u)
                        except json.JSONDecodeError:
                            continue
                return urls
        except Exception as exc:
            self.logger.debug("CC search error for '%s': %s", keyword, exc)
            return []

    @staticmethod
    def _extract_domain(url: str) -> str | None:
        url = url.strip().lower()
        url = re.sub(r"^https?://", "", url)
        url = url.split("/")[0]
        url = url.split("?")[0]
        url = url.split("#")[0]
        if DOMAIN_RE.match(url) and url.count(".") >= 1:
            return url
        return None

    def _fallback_list(self) -> list[str]:
        return [
            "openassistant.ai", "vectorsearch.ai", "langflow.io", "diffusionlab.io", "llmrouter.io",
            "fintechx.io", "blockchainpay.co", "insurtechpro.io", "wealthsimple.co", "quanttrade.io",
            "medtechhub.io", "biogenix.io", "symptomcheck.pro", "healthdata.io", "genomicslab.io",
            "edtechx.io", "learnpath.io", "classroomio.io", "quizmaster.io", "gradetracker.io",
            "devsecops.io", "zero-day.io", "malwarewatch.io", "authshield.io", "cloudguard.io",
            "smartproperty.io", "rentalfinder.io", "propertyx.io", "homescout.io", "zoningcheck.io",
            "goalminder.io", "taskflow.io", "routine.io", "focusbits.io", "kanbantool.io",
            "legalops.io", "contractflow.io", "paralegalhub.io", "legalanalytics.io", "clausemanager.io",
            "payflow.io", "bankless.io", "walletguard.io", "swapzone.io", "liquiditypool.io",
            "fitplan.io", "mealplanner.io", "workoutgen.io", "sleepcycle.io", "calmtrack.io",
        ]

    def _make_dict(self, domain_name: str) -> dict[str, Any]:
        tld = domain_name.split(".")[-1] if "." in domain_name else ""
        return {
            "domain_name": domain_name,
            "price": 0.0,
            "source": self.source,
            "tld": tld,
            "dr": 0,
            "referring_domains": 0,
            "domain_age": 0,
        }
