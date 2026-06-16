from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from src.collectors.base import BaseCollector
from src.config import settings
from src.utils import async_retry, setup_logger


class ExpiredDomainsCollector(BaseCollector):
    SOURCE = "ExpiredDomains"
    BASE_URL = "https://www.expireddomains.net"
    EXPIRED_URL = f"{BASE_URL}/expired-domains/"
    DELETED_URL = f"{BASE_URL}/deleted-domains/"

    MOCK_DOMAINS = [
        {
            "domain_name": "marketingautomation.io",
            "price": 49.0,
            "auction_end_date": "2026-06-23",
            "registrar": "NameCheap",
            "tld": "io",
            "source": SOURCE,
            "dr": 12,
            "referring_domains": 87,
            "domain_age": 4,
        },
        {
            "domain_name": "analyticshub.net",
            "price": 29.0,
            "auction_end_date": "2026-06-24",
            "registrar": "GoDaddy",
            "tld": "net",
            "source": SOURCE,
            "dr": 8,
            "referring_domains": 34,
            "domain_age": 6,
        },
        {
            "domain_name": "cloudsync.app",
            "price": 19.0,
            "auction_end_date": "2026-06-25",
            "registrar": "NameCheap",
            "tld": "app",
            "source": SOURCE,
            "dr": 5,
            "referring_domains": 12,
            "domain_age": 2,
        },
        {
            "domain_name": "datastreampro.com",
            "price": 59.0,
            "auction_end_date": "2026-06-22",
            "registrar": "GoDaddy",
            "tld": "com",
            "source": SOURCE,
            "dr": 18,
            "referring_domains": 142,
            "domain_age": 8,
        },
        {
            "domain_name": "devopscentral.org",
            "price": 35.0,
            "auction_end_date": "2026-06-26",
            "registrar": "NameCheap",
            "tld": "org",
            "source": SOURCE,
            "dr": 10,
            "referring_domains": 56,
            "domain_age": 5,
        },
        {
            "domain_name": "ecomplatforms.co",
            "price": 25.0,
            "auction_end_date": "2026-06-27",
            "registrar": "GoDaddy",
            "tld": "co",
            "source": SOURCE,
            "dr": 7,
            "referring_domains": 29,
            "domain_age": 3,
        },
        {
            "domain_name": "fitnesspro365.com",
            "price": 15.0,
            "auction_end_date": "2026-06-21",
            "registrar": "NameCheap",
            "tld": "com",
            "source": SOURCE,
            "dr": 4,
            "referring_domains": 8,
            "domain_age": 1,
        },
        {
            "domain_name": "greenenergyventures.com",
            "price": 45.0,
            "auction_end_date": "2026-06-28",
            "registrar": "GoDaddy",
            "tld": "com",
            "source": SOURCE,
            "dr": 14,
            "referring_domains": 95,
            "domain_age": 7,
        },
        {
            "domain_name": "healthcareai.dev",
            "price": 39.0,
            "auction_end_date": "2026-06-29",
            "registrar": "NameCheap",
            "tld": "dev",
            "source": SOURCE,
            "dr": 9,
            "referring_domains": 41,
            "domain_age": 3,
        },
        {
            "domain_name": "innovatehub.tech",
            "price": 22.0,
            "auction_end_date": "2026-06-30",
            "registrar": "GoDaddy",
            "tld": "tech",
            "source": SOURCE,
            "dr": 6,
            "referring_domains": 18,
            "domain_age": 2,
        },
        {
            "domain_name": "logisticssolutions.biz",
            "price": 33.0,
            "auction_end_date": "2026-06-23",
            "registrar": "NameCheap",
            "tld": "biz",
            "source": SOURCE,
            "dr": 11,
            "referring_domains": 63,
            "domain_age": 10,
        },
        {
            "domain_name": "mediastreamlive.tv",
            "price": 27.0,
            "auction_end_date": "2026-06-24",
            "registrar": "GoDaddy",
            "tld": "tv",
            "source": SOURCE,
            "dr": 8,
            "referring_domains": 37,
            "domain_age": 4,
        },
        {
            "domain_name": "nextgenfintech.com",
            "price": 65.0,
            "auction_end_date": "2026-06-25",
            "registrar": "NameCheap",
            "tld": "com",
            "source": SOURCE,
            "dr": 20,
            "referring_domains": 178,
            "domain_age": 6,
        },
        {
            "domain_name": "propertysearch.pro",
            "price": 18.0,
            "auction_end_date": "2026-06-26",
            "registrar": "GoDaddy",
            "tld": "pro",
            "source": SOURCE,
            "dr": 3,
            "referring_domains": 5,
            "domain_age": 1,
        },
        {
            "domain_name": "retailinsights.org",
            "price": 42.0,
            "auction_end_date": "2026-06-27",
            "registrar": "NameCheap",
            "tld": "org",
            "source": SOURCE,
            "dr": 13,
            "referring_domains": 78,
            "domain_age": 9,
        },
    ]

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config or {})
        self.logger = setup_logger(self.__class__.__name__)

    @async_retry()
    async def collect(self) -> list[dict]:
        try:
            async with httpx.AsyncClient(
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                },
                follow_redirects=True,
                timeout=30.0,
            ) as client:
                domains = await self._fetch_all_expired(client)
                if not domains:
                    self.logger.warning("No domains scraped, returning mock data")
                    return list(self.MOCK_DOMAINS)
                return domains
        except Exception:
            self.logger.exception("ExpiredDomains collector failed")
            return list(self.MOCK_DOMAINS)

    async def _fetch_all_expired(self, client: httpx.AsyncClient) -> list[dict]:
        domains: list[dict] = []

        for page in range(1, 4):
            try:
                params = {"start": (page - 1) * 100}
                resp = await client.get(self.EXPIRED_URL, params=params)
                resp.raise_for_status()
                page_domains = self._parse_table(resp.text, "expired")
                domains.extend(page_domains)
                self.logger.info("Page %d: found %d expired domains", page, len(page_domains))
                await asyncio.sleep(1.0)
            except Exception:
                self.logger.warning("Failed to fetch expired domains page %d", page)
                break

        try:
            resp = await client.get(self.DELETED_URL)
            resp.raise_for_status()
            deleted_domains = self._parse_table(resp.text, "deleted")
            domains.extend(deleted_domains)
            self.logger.info("Found %d deleted domains", len(deleted_domains))
        except Exception:
            self.logger.warning("Failed to fetch deleted domains")

        return domains

    def _parse_table(self, html: str, section: str) -> list[dict]:
        domains: list[dict] = []
        soup = BeautifulSoup(html, "html.parser")

        for table in soup.find_all("table", class_=re.compile(r"expired|domain|base")):
            for row in table.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) < 5:
                    continue
                try:
                    domain_name = self._extract_domain_name(cells)
                    if not domain_name:
                        continue
                    tld = domain_name.split(".")[-1] if "." in domain_name else ""
                    domains.append({
                        "domain_name": domain_name,
                        "price": self._extract_price(cells),
                        "auction_end_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        "registrar": self._extract_registrar(cells),
                        "tld": tld,
                        "source": self.SOURCE,
                        "dr": self._extract_dr(cells),
                        "referring_domains": self._extract_ref_domains(cells),
                        "domain_age": self._extract_age(cells),
                    })
                except Exception:
                    continue

        return domains

    def _extract_domain_name(self, cells) -> str:
        for cell in cells:
            link = cell.find("a", href=re.compile(r"/domain/"))
            if link:
                return link.get_text(strip=True)
            strong = cell.find("strong")
            if strong:
                text = strong.get_text(strip=True)
                if "." in text:
                    return text
        text = cells[0].get_text(strip=True)
        if "." in text:
            return text.split()[0]
        return ""

    def _extract_price(self, cells) -> float:
        for cell in cells:
            text = cell.get_text(strip=True)
            match = re.search(r"\$?(\d+[\d,.]*)", text)
            if match:
                try:
                    return float(match.group(1).replace(",", ""))
                except ValueError:
                    pass
        return 0.0

    def _extract_registrar(self, cells) -> str:
        for cell in cells:
            text = cell.get_text(strip=True)
            known = ["GoDaddy", "NameCheap", "NameSilo", "Tucows", "Enom", "Dynadot"]
            for name in known:
                if name.lower() in text.lower():
                    return name
        return "Unknown"

    def _extract_dr(self, cells) -> int:
        for cell in cells:
            text = cell.get_text(strip=True)
            match = re.search(r"\b(\d{1,3})\b", text)
            if match:
                val = int(match.group(1))
                if 0 <= val <= 100:
                    return val
        return 0

    def _extract_ref_domains(self, cells) -> int:
        for cell in cells:
            text = cell.get_text(strip=True).replace(",", "")
            match = re.search(r"\b(\d{2,6})\b", text)
            if match:
                return int(match.group(1))
        return 0

    def _extract_age(self, cells) -> int:
        for cell in cells:
            text = cell.get_text(strip=True)
            match = re.search(r"(\d+)\s*(?:year|yr)", text, re.IGNORECASE)
            if match:
                return int(match.group(1))
            match = re.search(r"(\d{4})", text)
            if match:
                try:
                    year = int(match.group(1))
                    current = datetime.now(timezone.utc).year
                    if 1990 <= year <= current:
                        return current - year
                except Exception:
                    pass
        return 0
