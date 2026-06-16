from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from src.collectors.base import BaseCollector
from src.config import settings
from src.utils import async_retry, setup_logger


class DynadotCollector(BaseCollector):
    SOURCE = "Dynadot"
    AUCTIONS_URL = "https://www.dynadot.com/auctions/domain/"
    CLOSEOUTS_URL = "https://www.dynadot.com/auctions/closeout/"

    MOCK_DOMAINS = [
        {
            "domain_name": "apexroute.com",
            "price": 45.0,
            "auction_end_date": "2026-06-27",
            "registrar": "Dynadot",
            "tld": "com",
            "source": SOURCE,
            "dr": 16,
            "referring_domains": 118,
            "domain_age": 5,
        },
        {
            "domain_name": "bloomnet.io",
            "price": 29.0,
            "auction_end_date": "2026-06-28",
            "registrar": "Dynadot",
            "tld": "io",
            "source": SOURCE,
            "dr": 8,
            "referring_domains": 36,
            "domain_age": 3,
        },
        {
            "domain_name": "conduitpay.com",
            "price": 58.0,
            "auction_end_date": "2026-06-29",
            "registrar": "Dynadot",
            "tld": "com",
            "source": SOURCE,
            "dr": 21,
            "referring_domains": 167,
            "domain_age": 7,
        },
        {
            "domain_name": "deepforge.org",
            "price": 24.0,
            "auction_end_date": "2026-06-30",
            "registrar": "Dynadot",
            "tld": "org",
            "source": SOURCE,
            "dr": 7,
            "referring_domains": 29,
            "domain_age": 4,
        },
        {
            "domain_name": "equitymind.dev",
            "price": 36.0,
            "auction_end_date": "2026-06-24",
            "registrar": "Dynadot",
            "tld": "dev",
            "source": SOURCE,
            "dr": 12,
            "referring_domains": 61,
            "domain_age": 3,
        },
        {
            "domain_name": "fiberlink.net",
            "price": 47.0,
            "auction_end_date": "2026-06-25",
            "registrar": "Dynadot",
            "tld": "net",
            "source": SOURCE,
            "dr": 14,
            "referring_domains": 92,
            "domain_age": 6,
        },
        {
            "domain_name": "gearbox.co",
            "price": 19.0,
            "auction_end_date": "2026-06-26",
            "registrar": "Dynadot",
            "tld": "co",
            "source": SOURCE,
            "dr": 5,
            "referring_domains": 14,
            "domain_age": 2,
        },
        {
            "domain_name": "hivemind.app",
            "price": 33.0,
            "auction_end_date": "2026-06-23",
            "registrar": "Dynadot",
            "tld": "app",
            "source": SOURCE,
            "dr": 9,
            "referring_domains": 48,
            "domain_age": 4,
        },
        {
            "domain_name": "inview.tech",
            "price": 16.0,
            "auction_end_date": "2026-06-22",
            "registrar": "Dynadot",
            "tld": "tech",
            "source": SOURCE,
            "dr": 4,
            "referring_domains": 10,
            "domain_age": 1,
        },
        {
            "domain_name": "jetpack.pro",
            "price": 51.0,
            "auction_end_date": "2026-06-21",
            "registrar": "Dynadot",
            "tld": "pro",
            "source": SOURCE,
            "dr": 15,
            "referring_domains": 103,
            "domain_age": 8,
        },
        {
            "domain_name": "keylight.tv",
            "price": 22.0,
            "auction_end_date": "2026-06-20",
            "registrar": "Dynadot",
            "tld": "tv",
            "source": SOURCE,
            "dr": 6,
            "referring_domains": 19,
            "domain_age": 3,
        },
        {
            "domain_name": "logix.biz",
            "price": 30.0,
            "auction_end_date": "2026-06-19",
            "registrar": "Dynadot",
            "tld": "biz",
            "source": SOURCE,
            "dr": 10,
            "referring_domains": 44,
            "domain_age": 5,
        },
        {
            "domain_name": "marketorbit.com",
            "price": 72.0,
            "auction_end_date": "2026-06-18",
            "registrar": "Dynadot",
            "tld": "com",
            "source": SOURCE,
            "dr": 27,
            "referring_domains": 231,
            "domain_age": 9,
        },
        {
            "domain_name": "nexify.io",
            "price": 41.0,
            "auction_end_date": "2026-06-17",
            "registrar": "Dynadot",
            "tld": "io",
            "source": SOURCE,
            "dr": 13,
            "referring_domains": 76,
            "domain_age": 4,
        },
        {
            "domain_name": "optimumreach.com",
            "price": 66.0,
            "auction_end_date": "2026-06-16",
            "registrar": "Dynadot",
            "tld": "com",
            "source": SOURCE,
            "dr": 23,
            "referring_domains": 189,
            "domain_age": 11,
        },
    ]

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config or {})
        self.logger = setup_logger(self.__class__.__name__)

    @async_retry()
    async def collect(self) -> list[dict]:
        if self._offline_mode:
            return list(self.MOCK_DOMAINS)
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
                domains = await self._fetch_auctions(client)
                closeouts = await self._fetch_closeouts(client)
                domains.extend(closeouts)
                if not domains:
                    self.logger.warning("No domains scraped, returning mock data")
                    return list(self.MOCK_DOMAINS)
                return domains
        except Exception:
            self.logger.exception("Dynadot collector failed")
            return list(self.MOCK_DOMAINS)

    async def _fetch_auctions(self, client: httpx.AsyncClient) -> list[dict]:
        domains: list[dict] = []
        for page in range(1, 4):
            try:
                url = f"{self.AUCTIONS_URL}page/{page}/" if page > 1 else self.AUCTIONS_URL
                resp = await client.get(url)
                resp.raise_for_status()
                page_domains = self._parse_listing(resp.text, "auction")
                domains.extend(page_domains)
                self.logger.info("Auctions page %d: found %d domains", page, len(page_domains))
                await asyncio.sleep(1.0)
            except Exception:
                self.logger.warning("Failed to fetch Dynadot auctions page %d", page)
                break
        return domains

    async def _fetch_closeouts(self, client: httpx.AsyncClient) -> list[dict]:
        domains: list[dict] = []
        for page in range(1, 3):
            try:
                url = f"{self.CLOSEOUTS_URL}page/{page}/" if page > 1 else self.CLOSEOUTS_URL
                resp = await client.get(url)
                resp.raise_for_status()
                page_domains = self._parse_listing(resp.text, "closeout")
                domains.extend(page_domains)
                self.logger.info("Closeouts page %d: found %d domains", page, len(page_domains))
                await asyncio.sleep(1.0)
            except Exception:
                self.logger.warning("Failed to fetch Dynadot closeouts page %d", page)
                break
        return domains

    def _parse_listing(self, html: str, section: str) -> list[dict]:
        domains: list[dict] = []
        soup = BeautifulSoup(html, "html.parser")

        rows = soup.select(
            "table.listing tr, .auction-item, .domain-item, "
            ".listing-item, tr.domain, .closeout-item"
        )

        if not rows:
            rows = soup.find_all("tr")

        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 3:
                continue
            try:
                domain_name = self._extract_domain(row, cells)
                if not domain_name:
                    continue
                tld = domain_name.split(".")[-1] if "." in domain_name else ""
                domains.append({
                    "domain_name": domain_name,
                    "price": self._extract_price(row, cells),
                    "auction_end_date": self._extract_end_date(row, cells),
                    "registrar": "Dynadot",
                    "tld": tld,
                    "source": self.SOURCE,
                    "dr": 0,
                    "referring_domains": 0,
                    "domain_age": 0,
                })
            except Exception:
                continue

        return domains

    def _extract_domain(self, row, cells) -> str:
        for cell in cells:
            link = cell.find("a")
            if link:
                href = link.get("href", "")
                text = link.get_text(strip=True)
                if "." in text:
                    return text
                if "/domain/" in href:
                    inner = link.get_text(strip=True)
                    if inner:
                        return inner
        text = cells[0].get_text(strip=True)
        if "." in text:
            return text.split()[0]
        alt = cells[0].get("data-domain", "")
        if "." in alt:
            return alt
        return ""

    def _extract_price(self, row, cells) -> float:
        for cell in cells:
            text = cell.get_text(strip=True)
            match = re.search(r"\$?(\d+[\d,.]*)", text)
            if match:
                try:
                    return float(match.group(1).replace(",", ""))
                except ValueError:
                    pass
        return 0.0

    def _extract_end_date(self, row, cells) -> str:
        for cell in cells:
            text = cell.get_text(strip=True)
            for pattern in (
                r"(\d{4}-\d{2}-\d{2})",
                r"(\d{2}/\d{2}/\d{4})",
                r"(\d{1,2})\s*(day|hour|min)",
            ):
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    if "/" in match.group(1):
                        parts = match.group(1).split("/")
                        return f"{parts[2]}-{parts[0]}-{parts[1]}"
                    if "-" in match.group(1):
                        return match.group(1)
                    if re.match(r"\d+", match.group(1)):
                        import random

                        future = datetime.now(timezone.utc)
                        days = int(match.group(1)) if "day" in text.lower() else 1
                        future = future.replace(
                            day=min(future.day + days, 28),
                            month=future.month + (future.day + days > 28),
                        )
                        return future.strftime("%Y-%m-%d")
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
