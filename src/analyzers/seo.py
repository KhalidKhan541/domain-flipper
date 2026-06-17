from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

from src.config import settings
from src.checkers.rdap_checker import RDAPChecker
from src.utils import async_retry, setup_logger

try:
    import whois as whois_lib
except ImportError:
    whois_lib = None  # type: ignore[assignment]

DEFAULT_RESPONSE: dict[str, Any] = {
    "dr": None,
    "referring_domains": None,
    "total_backlinks": None,
    "anchor_diversity_score": None,
    "domain_age": None,
    "traffic_estimate": None,
    "seo_score": 0.0,
    "page_title": None,
    "meta_description": None,
    "status_code": None,
    "content_length": None,
    "links_found": None,
}

WAYBACK_CDX_URL = "https://web.archive.org/cdx/search/cdx"


class SEOAnalyzer:
    def __init__(self) -> None:
        self.logger = setup_logger("SEOAnalyzer")

    async def analyze(
        self,
        domain: str,
        domain_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if settings.offline_mode:
            return self._offline_response()

        result = dict(DEFAULT_RESPONSE)
        data = domain_data or {}

        pre_dr = data.get("dr")
        pre_rd = data.get("referring_domains")
        pre_age = data.get("domain_age")

        tasks = [
            self._get_http_data(domain),
            self._get_domain_age(domain, pre_age),
            self._get_rdap_data(domain),
            self._get_wayback_age(domain),
            self._get_domain_age_from_rdap(domain),
        ]

        http_data, domain_age, rdap_data, wayback_age, rdap_age = (
            await asyncio.gather(*tasks, return_exceptions=True)
        )

        if not isinstance(http_data, Exception) and http_data:
            result["page_title"] = http_data.get("page_title")
            result["meta_description"] = http_data.get("meta_description")
            result["status_code"] = http_data.get("status_code")
            result["content_length"] = http_data.get("content_length")
            result["links_found"] = http_data.get("links_found")
        else:
            self.logger.debug("HTTP check failed for %s: %s", domain, http_data)

        if not isinstance(domain_age, Exception) and domain_age is not None:
            result["domain_age"] = domain_age
        elif not isinstance(wayback_age, Exception) and wayback_age is not None:
            result["domain_age"] = wayback_age

        if pre_age is not None and isinstance(pre_age, (int, float)) and pre_age > 0:
            result["domain_age"] = int(pre_age)

        if not isinstance(rdap_age, Exception) and rdap_age is not None:
            result["domain_age"] = rdap_age

        if not isinstance(rdap_data, Exception) and rdap_data:
            rdap_events = rdap_data.get("events", [])
            for ev in rdap_events:
                if ev.get("eventAction") == "registration":
                    created = ev.get("eventDate", "")
                    if created:
                        try:
                            year = int(created[:4])
                            now = datetime.now(timezone.utc).year
                            result["domain_age"] = max(1, now - year)
                        except (ValueError, TypeError):
                            pass
                    break

        if pre_dr is not None and pre_rd is not None:
            result["dr"] = pre_dr
            result["referring_domains"] = pre_rd

        if result["dr"] is not None and result["referring_domains"] is not None:
            result["total_backlinks"] = self._estimate_total_backlinks(
                result["referring_domains"]
            )
            result["anchor_diversity_score"] = self._estimate_anchor_diversity(
                result["referring_domains"], result["total_backlinks"]
            )

        result["traffic_estimate"] = self._infer_traffic_from_seo(result)
        result["seo_score"] = self._compute_seo_score(result)

        return result

    def _offline_response(self) -> dict[str, Any]:
        return dict(DEFAULT_RESPONSE)

    async def _get_http_data(self, domain: str) -> dict[str, Any]:
        try:
            url = f"https://{domain}"
            async with httpx.AsyncClient(
                timeout=15.0, follow_redirects=True
            ) as client:
                resp = await client.get(url)

                page_title = None
                meta_description = None
                internal_links = 0
                external_links = 0

                content_type = resp.headers.get("content-type", "")
                body = resp.text if "text" in content_type or "html" in content_type else ""

                if body:
                    title_match = re.search(
                        r"<title[^>]*>(.*?)</title>", body, re.IGNORECASE | re.DOTALL
                    )
                    if title_match:
                        page_title = title_match.group(1).strip()

                    desc_match = re.search(
                        r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']',
                        body,
                        re.IGNORECASE | re.DOTALL,
                    )
                    if not desc_match:
                        desc_match = re.search(
                            r'<meta\s+content=["\'](.*?)["\']\s+name=["\']description["\']',
                            body,
                            re.IGNORECASE | re.DOTALL,
                        )
                    if desc_match:
                        meta_description = desc_match.group(1).strip()

                    link_matches = re.findall(
                        r'<a\s+[^>]*href=["\']([^"\'#]+)["\'][^>]*>', body, re.IGNORECASE
                    )
                    for href in link_matches:
                        if href.startswith("http://") or href.startswith("https://"):
                            parsed = urlparse(href)
                            link_domain = parsed.netloc.lower().lstrip("www.")
                            target_domain = domain.lower().lstrip("www.")
                            if link_domain == target_domain or link_domain.endswith(
                                "." + target_domain
                            ):
                                internal_links += 1
                            else:
                                external_links += 1
                        elif href.startswith("/"):
                            internal_links += 1

                return {
                    "page_title": page_title,
                    "meta_description": meta_description,
                    "status_code": resp.status_code,
                    "content_length": len(resp.content),
                    "links_found": internal_links + external_links,
                }
        except Exception:
            self.logger.debug("HTTP check failed for %s", domain, exc_info=True)
            return {}

    async def _get_domain_age(self, domain: str, pre_age: Any) -> int | None:
        if pre_age is not None and isinstance(pre_age, (int, float)) and pre_age > 0:
            return int(pre_age)

        creation = await self._get_creation_from_whois(domain)
        if creation is not None:
            return max(1, creation)
        return None

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

    async def _get_rdap_data(self, domain: str) -> dict[str, Any] | None:
        try:
            checker = RDAPChecker()
            result = await checker.check(domain)
            if result.get("method") == "offline":
                return None
            tld = domain.rsplit(".", 1)[-1] if "." in domain else ""
            base = checker.RDAP_BASE.get(tld)
            if base is None:
                return None
            url = f"{base}{domain}"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, follow_redirects=True)
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            self.logger.debug("RDAP lookup failed for %s", domain, exc_info=True)
        return None

    async def _get_domain_age_from_rdap(self, domain: str) -> int | None:
        try:
            checker = RDAPChecker()
            tld = domain.rsplit(".", 1)[-1] if "." in domain else ""
            base = checker.RDAP_BASE.get(tld)
            if base is None:
                return None
            url = f"{base}{domain}"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, follow_redirects=True)
                if resp.status_code == 200:
                    data = resp.json()
                    events = data.get("events", [])
                    for ev in events:
                        if ev.get("eventAction") == "registration":
                            created = ev.get("eventDate", "")
                            if created:
                                year = int(created[:4])
                                now = datetime.now(timezone.utc).year
                                return max(1, now - year)
                    return None
        except Exception:
            self.logger.debug("RDAP age lookup failed for %s", domain, exc_info=True)
        return None

    async def _get_wayback_age(self, domain: str) -> int | None:
        try:
            params = {
                "url": domain,
                "output": "json",
                "limit": 1,
                "fl": "timestamp",
                "matchType": "exact",
                "collapse": "timestamp:6",
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(WAYBACK_CDX_URL, params=params)
                if resp.status_code == 200:
                    rows = resp.json()
                    if len(rows) > 1:
                        ts = rows[-1][0]
                        year = int(ts[:4])
                        now = datetime.now(timezone.utc).year
                        return max(1, now - year)
        except Exception:
            self.logger.debug("Wayback CDX failed for %s", domain, exc_info=True)
        return None

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

    @staticmethod
    def _infer_traffic_from_seo(result: dict[str, Any]) -> str:
        status = result.get("status_code")
        content_len = result.get("content_length")
        links = result.get("links_found")
        dr = result.get("dr")

        if status and status >= 400:
            return "low"

        score = 0
        if status and status == 200:
            score += 30
        if content_len and content_len > 1000:
            score += 20
        if links and links > 5:
            score += 20
        if dr and dr > 30:
            score += 30

        if score >= 60:
            return "high"
        if score >= 30:
            return "medium"
        return "low"

    @staticmethod
    def _compute_seo_score(result: dict[str, Any]) -> float:
        score = 0.0

        status = result.get("status_code")
        if status:
            if status == 200:
                score += 30.0
            elif 300 <= status < 400:
                score += 15.0

        content_len = result.get("content_length")
        if content_len and content_len > 5000:
            score += 20.0
        elif content_len and content_len > 1000:
            score += 10.0

        title = result.get("page_title")
        if title and len(title) > 10:
            score += 10.0

        meta = result.get("meta_description")
        if meta and len(meta) > 20:
            score += 10.0

        dr = result.get("dr")
        if dr is not None:
            score += min(20.0, dr * 0.2)

        rd = result.get("referring_domains")
        if rd is not None:
            score += min(10.0, rd / 50.0)

        age = result.get("domain_age")
        if age and age > 0:
            score += min(10.0, age * 0.5)

        return round(max(0.0, min(100.0, score)), 2)
