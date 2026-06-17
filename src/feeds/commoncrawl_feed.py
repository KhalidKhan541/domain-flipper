from __future__ import annotations

import json
import random
import re
from typing import Any

import httpx

from src.feeds.base import BaseFeed
from src.utils import setup_logger

DOMAIN_RE = re.compile(r"^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$")


class CommonCrawlFeed(BaseFeed):
    source = "commoncrawl"

    CC_API_BASE = "https://index.commoncrawl.org"
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    def __init__(self) -> None:
        self.logger = setup_logger("CommonCrawlFeed")

    TLD_SEEDS = ["*.com", "*.io", "*.ai", "*.net", "*.org", "*.co", "*.app", "*.dev"]

    async def fetch(self, max_domains: int = 200) -> list[dict]:
        latest = await self._get_latest_index()
        if not latest:
            self.logger.warning("No CC index found — returning empty (no fallback)")
            return []

        found: set[str] = set()
        random.shuffle(self.TLD_SEEDS)
        per_tld = max(10, max_domains // len(self.TLD_SEEDS))

        for tld in self.TLD_SEEDS:
            try:
                urls = await self._search_index(latest, tld, limit=per_tld * 3)
                for u in urls:
                    domain = self._extract_domain(u)
                    if domain and DOMAIN_RE.match(domain):
                        found.add(domain)
            except Exception as exc:
                self.logger.debug("CC search for %s failed: %s", tld, exc)

            if len(found) >= max_domains:
                break

        domains = list(found)[:max_domains]
        self.logger.info("CommonCrawlFeed: %d domains", len(domains))
        return [self._make_dict(d) for d in domains]

    async def _get_latest_index(self) -> str | None:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(f"{self.CC_API_BASE}/collinfo.json")
                resp.raise_for_status()
                indexes = resp.json()
                if isinstance(indexes, list) and indexes:
                    working = [
                        i
                        for i in indexes
                        if "CC-MAIN-201" in i.get("id", "")
                        or "CC-MAIN-202" in i.get("id", "")
                    ]
                    if working:
                        return working[0]["id"]
                    return indexes[0]["id"]
            return None
        except Exception as exc:
            self.logger.debug("Failed to get CC index: %s", exc)
            return None

    async def _search_index(
        self, index: str, url_pattern: str, limit: int = 100
    ) -> list[str]:
        url = f"{self.CC_API_BASE}/{index}-index"
        params = {
            "url": url_pattern,
            "output": "json",
            "fl": "url",
            "limit": str(limit),
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    url, params=params, headers={"User-Agent": self.USER_AGENT}
                )
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
            self.logger.debug("CC search error for '%s': %s", url_pattern, exc)
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
