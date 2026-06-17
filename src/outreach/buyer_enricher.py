from __future__ import annotations

import re
from typing import Any

import httpx

from src.config import settings
from src.utils import setup_logger

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


class BuyerEnricher:
    def __init__(self) -> None:
        self.logger = setup_logger("BuyerEnricher")

    async def enrich(self, leads: list[dict[str, Any]], domain: str, niche: str) -> list[dict[str, Any]]:
        enriched: list[dict[str, Any]] = []

        for lead in leads:
            try:
                company = lead.get("company", "")
                result: dict[str, Any] = {
                    **lead,
                    "contact_name": None,
                    "contact_title": None,
                    "contact_email": None,
                    "contact_linkedin": None,
                    "confidence": "none",
                }

                if not settings.offline_mode:
                    await self._search_contact(company, domain, result)

                if result["contact_name"] is None:
                    result.pop("confidence", None)
                    result["contact_name"] = lead.get("contact_name")
                    result["contact_title"] = lead.get("contact_title")
                    result["contact_email"] = lead.get("contact_email")
                    result["contact_linkedin"] = lead.get("contact_linkedin")
                    result["confidence"] = lead.get("confidence", "none")

                enriched.append(result)

            except Exception as exc:
                self.logger.warning("Failed to enrich lead %s: %s", lead.get("company"), exc)
                enriched.append({
                    **lead,
                    "contact_name": None,
                    "contact_title": None,
                    "contact_email": None,
                    "contact_linkedin": None,
                    "confidence": "error",
                })

        return enriched

    async def _search_contact(self, company: str, domain: str, result: dict[str, Any]) -> None:
        slug = company.lower().replace(" ", "").replace(",", "").replace(".", "")
        company_domain = domain
        if "." in domain:
            _, tld = domain.rsplit(".", 1)
            company_domain = f"{slug}.{tld}"

        linkedin_found = await self._search_linkedin(company)
        email_found = await self._search_email(company, company_domain)

        if linkedin_found:
            result["contact_name"] = linkedin_found.get("name")
            result["contact_title"] = linkedin_found.get("title")
            result["contact_linkedin"] = linkedin_found.get("url")

        if email_found:
            result["contact_email"] = email_found

        if linkedin_found or email_found:
            result["confidence"] = "found"
        else:
            if not result["contact_email"] and company_domain:
                result["contact_email"] = f"info@{company_domain}"
            if result["contact_name"] or result["contact_email"]:
                result["confidence"] = "generated"
            else:
                result["confidence"] = "none"

    async def _search_linkedin(self, company: str) -> dict[str, str] | None:
        query = f"site:linkedin.com/in \"{company}\""
        search_url = f"https://www.google.com/search?q={self._urlencode(query)}"
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(10.0),
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
            ) as client:
                resp = await client.get(search_url)
                if resp.status_code != 200:
                    self.logger.debug("LinkedIn search returned %d for %s", resp.status_code, company)
                    return None

                text = resp.text
                name = self._extract_name_from_snippet(text, company)
                title = self._extract_title_from_snippet(text)
                url = self._extract_linkedin_url(text)

                if name or url:
                    return {"name": name, "title": title, "url": url}
                return None

        except httpx.TimeoutException:
            self.logger.debug("LinkedIn search timeout for %s", company)
            return None
        except httpx.HTTPError as exc:
            self.logger.debug("LinkedIn search HTTP error for %s: %s", company, exc)
            return None
        except OSError as exc:
            self.logger.debug("LinkedIn search connection error for %s: %s", company, exc)
            return None

    async def _search_email(self, company: str, company_domain: str) -> str | None:
        query = f"\"@{company_domain}\""
        search_url = f"https://www.google.com/search?q={self._urlencode(query)}"
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(10.0),
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
            ) as client:
                resp = await client.get(search_url)
                if resp.status_code != 200:
                    return None

                emails = re.findall(rf"[a-zA-Z0-9._%+-]+@{re.escape(company_domain)}", resp.text)
                if emails:
                    return emails[0]
                return None

        except httpx.TimeoutException:
            self.logger.debug("Email search timeout for %s", company)
            return None
        except httpx.HTTPError as exc:
            self.logger.debug("Email search HTTP error for %s: %s", company, exc)
            return None
        except OSError as exc:
            self.logger.debug("Email search connection error for %s: %s", company, exc)
            return None

    def _extract_name_from_snippet(self, html: str, company: str) -> str | None:
        match = re.search(rf'<h3[^>]*>([^<]*)</h3>', html, re.IGNORECASE)
        if match:
            text = match.group(1)
            text = re.sub(r'<[^>]+>', '', text)
            text = text.strip()
            if text and len(text) < 200:
                return text
        match = re.search(r'((?:<span[^>]*>)*?([A-Z][a-z]+ [A-Z][a-z]+)(?:</span>)*?)', html)
        if match:
            return match.group(2)
        return None

    def _extract_title_from_snippet(self, html: str) -> str | None:
        for role in ("CEO", "CTO", "CFO", "COO", "Founder", "Co-Founder", "President", "Director", "VP", "Head of", "Lead", "Manager"):
            pattern = re.escape(role)
            if re.search(pattern, html, re.IGNORECASE):
                match = re.search(r'([A-Za-z\s&/,-]{2,60}(?:CEO|CTO|CFO|COO|Founder|Co-Founder|President|Director|VP|Head\s+of|Lead|Manager))', html)
                if match:
                    return match.group(1).strip()
                return role
        return None

    def _extract_linkedin_url(self, html: str) -> str | None:
        match = re.search(r'(https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9_-]+)', html)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _urlencode(query: str) -> str:
        return query.replace(" ", "+").replace("\"", "%22")
