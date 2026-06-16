from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Any

import httpx
from bs4 import BeautifulSoup

from src.config import settings
from src.utils import async_retry, setup_logger

try:
    import whois as whois_lib
except ImportError:
    whois_lib = None  # type: ignore[assignment]

WHOIS_DOMAINTOOLS_URL = "https://whois.domaintools.com/{domain}"
SIMILARWEB_URL = "https://www.similarweb.com/website/{domain}/"

DEFAULT_RESPONSE: dict[str, Any] = {
    "dr": 0,
    "referring_domains": 0,
    "total_backlinks": 0,
    "anchor_diversity_score": 0.0,
    "domain_age": 0,
    "traffic_estimate": "",
    "seo_score": 0.0,
}

TLD_BACKLINK_BOOST = {
    ".com": 1.5,
    ".org": 1.3,
    ".net": 1.2,
    ".io": 1.1,
    ".co": 1.1,
}


class SEOAnalyzer:
    def __init__(self) -> None:
        self.logger = setup_logger("SEOAnalyzer")

    async def analyze(
        self,
        domain: str,
        domain_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = dict(DEFAULT_RESPONSE)
        data = domain_data or {}

        pre_dr = data.get("dr")
        pre_rd = data.get("referring_domains")

        domain_age = await self._get_domain_age(domain, data)

        if pre_dr is not None and pre_rd is not None:
            estimated_dr, estimated_rd = await self._estimate_backlinks(domain, domain_age)
            result["dr"] = max(pre_dr, estimated_dr)
            result["referring_domains"] = max(pre_rd, estimated_rd)
        else:
            result["dr"], result["referring_domains"] = await self._estimate_backlinks(
                domain, domain_age
            )

        result["domain_age"] = domain_age
        result["total_backlinks"] = self._estimate_total_backlinks(
            result["referring_domains"]
        )
        result["anchor_diversity_score"] = self._estimate_anchor_diversity(
            result["referring_domains"], result["total_backlinks"]
        )
        result["traffic_estimate"] = await self._estimate_traffic(
            domain, result["dr"], domain_age, result["total_backlinks"]
        )
        result["seo_score"] = self._compute_seo_score(
            result["dr"],
            result["referring_domains"],
            domain_age,
            result["anchor_diversity_score"],
        )

        return result

    async def _get_domain_age(
        self, domain: str, data: dict[str, Any]
    ) -> int:
        pre_age = data.get("domain_age")
        if pre_age is not None and isinstance(pre_age, (int, float)) and pre_age > 0:
            return int(pre_age)

        creation = await self._get_creation_from_whois(domain)
        if creation is not None:
            return max(0, int(creation))

        try:
            creation = await self._get_creation_from_domaintools(domain)
            if creation is not None:
                return max(0, int(creation))
        except Exception:
            self.logger.debug("domaintools scrape failed for %s", domain, exc_info=True)

        first_seen = data.get("first_seen")
        if first_seen:
            try:
                year = int(str(first_seen)[:4])
                now = datetime.now(timezone.utc).year
                return max(1, now - year)
            except (ValueError, TypeError):
                pass

        self.logger.warning("Could not determine age for %s, defaulting to 1", domain)
        return 1

    async def _get_creation_from_whois(self, domain: str) -> int | None:
        if whois_lib is None:
            return None
        try:
            w = await asyncio.to_thread(whois_lib.whois, domain)
            cd = w.creation_date
            if cd is None:
                return None
            if isinstance(cd, list):
                cd = cd[0]
            if isinstance(cd, str):
                cd = datetime.fromisoformat(cd.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            if cd.tzinfo is None:
                cd = cd.replace(tzinfo=timezone.utc)
            delta = now - cd
            return max(1, int(delta.days / 365.25))
        except Exception:
            self.logger.debug("WHOIS lookup failed for %s", domain, exc_info=True)
            return None

    @async_retry(max_attempts=2, delay=1.0)
    async def _get_creation_from_domaintools(self, domain: str) -> int | None:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(WHOIS_DOMAINTOOLS_URL.format(domain=domain))
            if resp.status_code != 200:
                return None
            soup = BeautifulSoup(resp.text, "html.parser")
            text = soup.get_text(separator="\n", strip=True)
            patterns = [
                re.compile(r"Creation\s*Date[:\s]+(\d{4})", re.IGNORECASE),
                re.compile(r"Created\s*On[:\s]+(\d{4})", re.IGNORECASE),
                re.compile(r"(\d{4})[-/]\d{2}[-/]\d{2}", re.IGNORECASE),
            ]
            for pattern in patterns:
                match = pattern.search(text)
                if match:
                    year = int(match.group(1))
                    now = datetime.now(timezone.utc).year
                    return max(1, now - year)
            return None

    async def _estimate_backlinks(
        self, domain: str, domain_age: int
    ) -> tuple[int, int]:
        dr, rd = await self._try_ahrefs_api(domain)
        if dr > 0 and rd > 0:
            return dr, rd
        dr, rd = await self._try_moz_api(domain)
        if dr > 0 and rd > 0:
            return dr, rd
        return self._estimate_backlinks_fallback(domain, domain_age)

    async def _try_ahrefs_api(self, domain: str) -> tuple[int, int]:
        api_key = getattr(settings, "ahrefs_api_key", None)
        if not api_key:
            return 0, 0
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://apiv2.ahrefs.com",
                    params={
                        "token": api_key,
                        "from": "domainrating",
                        "target": domain,
                        "mode": "exact",
                        "output": "json",
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    dr_val = int(data.get("domain_rating", 0))
                    resp2 = await client.get(
                        "https://apiv2.ahrefs.com",
                        params={
                            "token": api_key,
                            "from": "backlinks",
                            "target": domain,
                            "mode": "domain",
                            "limit": 1,
                            "output": "json",
                        },
                    )
                    rd_val = 0
                    if resp2.status_code == 200:
                        d2 = resp2.json()
                        rd_val = int(d2.get("refdomains", 0) or d2.get("pages", 0) or 0)
                    return dr_val, rd_val
        except Exception:
            self.logger.debug("Ahrefs API failed for %s", domain, exc_info=True)
        return 0, 0

    async def _try_moz_api(self, domain: str) -> tuple[int, int]:
        api_key = getattr(settings, "moz_api_key", None)
        if not api_key:
            return 0, 0
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "https://lsapi.seomoz.com/v2/url_metrics",
                    json={"target": domain},
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    dr_val = int(data.get("domain_authority", 0) or 0)
                    rd_val = int(data.get("referring_domains", 0) or 0)
                    return dr_val, rd_val
        except Exception:
            self.logger.debug("Moz API failed for %s", domain, exc_info=True)
        return 0, 0

    @staticmethod
    def _estimate_backlinks_fallback(domain: str, domain_age: int) -> tuple[int, int]:
        parts = domain.rsplit(".", 1)
        tld = f".{parts[-1]}" if len(parts) > 1 else ".com"
        boost = TLD_BACKLINK_BOOST.get(tld, 1.0)
        base_dr = min(50, int(domain_age * 5 * boost))
        base_rd = min(200, int(domain_age * 20 * boost))
        return base_dr, base_rd

    @staticmethod
    def _estimate_total_backlinks(referring_domains: int) -> int:
        if referring_domains <= 1:
            return referring_domains
        ratio = 3.0 + (referring_domains / 100.0) * 2.0
        return int(referring_domains * ratio)

    @staticmethod
    def _estimate_anchor_diversity(referring_domains: int, total_backlinks: int) -> float:
        if total_backlinks == 0:
            return 0.0
        ratio = referring_domains / total_backlinks
        score = ratio * 100.0
        return round(max(0.0, min(100.0, score)), 2)

    async def _estimate_traffic(
        self, domain: str, dr: int, age: int, total_backlinks: int
    ) -> str:
        try:
            traffic = await self._try_similarweb(domain)
            if traffic:
                return traffic
        except Exception:
            self.logger.debug("SimilarWeb scrape failed for %s", domain, exc_info=True)
        return self._estimate_traffic_fallback(dr, age, total_backlinks)

    @async_retry(max_attempts=2, delay=1.0)
    async def _try_similarweb(self, domain: str) -> str | None:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(
                SIMILARWEB_URL.format(domain=domain),
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                },
            )
            if resp.status_code != 200:
                return None
            soup = BeautifulSoup(resp.text, "html.parser")
            text = soup.get_text(separator=" ", strip=True).lower()
            for kw, label in [("very high", "high"), ("high", "high"),
                              ("medium", "medium"), ("low", "low")]:
                if f"traffic {kw}" in text or kw in text:
                    return label
            return None

    @staticmethod
    def _estimate_traffic_fallback(dr: int, age: int, total_backlinks: int) -> str:
        score = dr * 0.4 + min(100, total_backlinks / 5) * 0.3 + min(100, age * 10) * 0.3
        if score >= 60:
            return "high"
        if score >= 25:
            return "medium"
        return "low"

    @staticmethod
    def _compute_seo_score(
        dr: int, referring_domains: int, domain_age: int, anchor_diversity: float
    ) -> float:
        dr_component = min(100.0, dr * 1.0) * 0.40
        rd_component = min(100.0, referring_domains / 5.0) * 0.25
        age_component = min(100.0, domain_age * 10.0) * 0.20
        diversity_component = anchor_diversity * 0.15
        score = dr_component + rd_component + age_component + diversity_component
        return round(max(0.0, min(100.0, score)), 2)
