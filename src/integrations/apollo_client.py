from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

import aiohttp

logger = logging.getLogger(__name__)

BASE_URL = "https://api.apollo.io/v1"


class ApolloClient:
    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key
        self._headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        if api_key:
            self._headers["X-Api-Key"] = api_key
        self._request_times: list[float] = []
        self._rate_limit = 3
        self._rate_window = 1.0

    def _has_key(self) -> bool:
        if self.api_key:
            return True
        logger.warning("Apollo API key not configured — returning empty results")
        return False

    async def _rate_limit_wait(self) -> None:
        now = time.monotonic()
        self._request_times = [t for t in self._request_times if now - t < self._rate_window]
        if len(self._request_times) >= self._rate_limit:
            sleep_time = self._rate_window - (now - self._request_times[0])
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
        self._request_times.append(time.monotonic())

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{BASE_URL}{path}"
        await self._rate_limit_wait()
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=self._headers, json=payload) as resp:
                resp.raise_for_status()
                return await resp.json()

    async def _get(self, path: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        url = f"{BASE_URL}{path}"
        await self._rate_limit_wait()
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self._headers, params=params) as resp:
                resp.raise_for_status()
                return await resp.json()

    async def search_companies(
        self,
        industry: str,
        min_employees: int,
        max_employees: int,
        keywords: list[str],
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        if not self._has_key():
            return []

        try:
            payload: dict[str, Any] = {
                "q_organization_keyword_tags": keywords,
                "organization_num_employees_ranges": [f"{min_employees},{max_employees}"],
                "page": 1,
                "per_page": limit,
            }
            if industry:
                payload["organization_industry_tag_ids"] = [industry]

            data = await self._post("/mixed_companies/search", payload)
            organizations = data.get("accounts", data.get("organizations", []))
            results: list[dict[str, Any]] = []

            for org in organizations:
                results.append({
                    "name": org.get("name", ""),
                    "domain": org.get("primary_domain", ""),
                    "industry": org.get("industry", ""),
                    "employee_count": org.get("estimated_num_employees", 0),
                    "founded_year": org.get("founded_year"),
                    "technologies": org.get("technologies", []),
                })

            return results

        except Exception as exc:
            logger.error("Apollo search_companies failed: %s", exc)
            return []

    async def search_contacts(
        self,
        company_domain: str,
        titles: list[str],
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        if not self._has_key():
            return []

        try:
            payload = {
                "person_titles": titles,
                "organization_domains": [company_domain],
                "page": 1,
                "per_page": limit,
            }

            data = await self._post("/mixed_people/search", payload)
            people = data.get("people", [])
            results: list[dict[str, Any]] = []

            for person in people:
                email_data = person.get("email", {}) or {}
                results.append({
                    "name": f"{person.get('first_name', '')} {person.get('last_name', '')}".strip(),
                    "title": person.get("title", ""),
                    "email": email_data.get("address") or email_data.get("email", ""),
                    "linkedin_url": person.get("linkedin_url", ""),
                })

            return results

        except Exception as exc:
            logger.error("Apollo search_contacts failed for %s: %s", company_domain, exc)
            return []

    async def enrich_organization(self, domain: str) -> dict[str, Any]:
        if not self._has_key():
            return {}

        try:
            data = await self._get(f"/organizations/{domain}")
            org = data.get("organization", data)

            social_links: list[dict[str, str]] = []
            for link in org.get("social_links", []):
                social_links.append({
                    "platform": link.get("platform", ""),
                    "url": link.get("url", ""),
                })

            return {
                "revenue": org.get("annual_revenue_printed", org.get("annual_revenue", "")),
                "technologies": org.get("technologies", []),
                "keywords": org.get("keywords", []),
                "social_links": social_links,
            }

        except Exception as exc:
            logger.error("Apollo enrich_organization failed for %s: %s", domain, exc)
            return {}
