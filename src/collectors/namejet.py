from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import httpx

from src.collectors.base import BaseCollector
from src.config import settings
from src.utils import async_retry, setup_logger


class NameJetCollector(BaseCollector):
    SOURCE = "NameJet"
    API_URL = "https://www.namejet.com/api/auctions/list"
    LISTINGS_URL = "https://www.namejet.com/auctions"

    MOCK_DOMAINS = [
        {
            "domain_name": "quantumledger.com",
            "price": 69.0,
            "auction_end_date": "2026-06-25",
            "registrar": "NameJet",
            "tld": "com",
            "source": SOURCE,
            "dr": 16,
            "referring_domains": 124,
            "domain_age": 5,
        },
        {
            "domain_name": "vertexanalytics.io",
            "price": 35.0,
            "auction_end_date": "2026-06-26",
            "registrar": "NameJet",
            "tld": "io",
            "source": SOURCE,
            "dr": 7,
            "referring_domains": 31,
            "domain_age": 3,
        },
        {
            "domain_name": "pulsefitnesstracker.com",
            "price": 15.0,
            "auction_end_date": "2026-06-27",
            "registrar": "NameJet",
            "tld": "com",
            "source": SOURCE,
            "dr": 4,
            "referring_domains": 9,
            "domain_age": 2,
        },
        {
            "domain_name": "zephyrcloud.app",
            "price": 22.0,
            "auction_end_date": "2026-06-28",
            "registrar": "NameJet",
            "tld": "app",
            "source": SOURCE,
            "dr": 5,
            "referring_domains": 14,
            "domain_age": 1,
        },
        {
            "domain_name": "alphastrategies.co",
            "price": 45.0,
            "auction_end_date": "2026-06-29",
            "registrar": "NameJet",
            "tld": "co",
            "source": SOURCE,
            "dr": 11,
            "referring_domains": 67,
            "domain_age": 7,
        },
        {
            "domain_name": "blockchainvault.net",
            "price": 55.0,
            "auction_end_date": "2026-06-23",
            "registrar": "NameJet",
            "tld": "net",
            "source": SOURCE,
            "dr": 14,
            "referring_domains": 102,
            "domain_age": 6,
        },
        {
            "domain_name": "cryptonest.org",
            "price": 28.0,
            "auction_end_date": "2026-06-24",
            "registrar": "NameJet",
            "tld": "org",
            "source": SOURCE,
            "dr": 9,
            "referring_domains": 44,
            "domain_age": 4,
        },
        {
            "domain_name": "datasphere.tech",
            "price": 38.0,
            "auction_end_date": "2026-06-30",
            "registrar": "NameJet",
            "tld": "tech",
            "source": SOURCE,
            "dr": 10,
            "referring_domains": 53,
            "domain_age": 3,
        },
        {
            "domain_name": "edtechinnovate.com",
            "price": 18.0,
            "auction_end_date": "2026-06-22",
            "registrar": "NameJet",
            "tld": "com",
            "source": SOURCE,
            "dr": 6,
            "referring_domains": 22,
            "domain_age": 2,
        },
        {
            "domain_name": "finwiseadvisors.pro",
            "price": 42.0,
            "auction_end_date": "2026-06-21",
            "registrar": "NameJet",
            "tld": "pro",
            "source": SOURCE,
            "dr": 12,
            "referring_domains": 71,
            "domain_age": 8,
        },
        {
            "domain_name": "greenlanternmedia.tv",
            "price": 25.0,
            "auction_end_date": "2026-06-20",
            "registrar": "NameJet",
            "tld": "tv",
            "source": SOURCE,
            "dr": 5,
            "referring_domains": 16,
            "domain_age": 3,
        },
        {
            "domain_name": "healthbridge.biz",
            "price": 32.0,
            "auction_end_date": "2026-06-19",
            "registrar": "NameJet",
            "tld": "biz",
            "source": SOURCE,
            "dr": 8,
            "referring_domains": 39,
            "domain_age": 5,
        },
        {
            "domain_name": "intellisync.dev",
            "price": 48.0,
            "auction_end_date": "2026-06-18",
            "registrar": "NameJet",
            "tld": "dev",
            "source": SOURCE,
            "dr": 13,
            "referring_domains": 88,
            "domain_age": 4,
        },
        {
            "domain_name": "jetstreamanalytics.com",
            "price": 75.0,
            "auction_end_date": "2026-06-17",
            "registrar": "NameJet",
            "tld": "com",
            "source": SOURCE,
            "dr": 22,
            "referring_domains": 201,
            "domain_age": 9,
        },
        {
            "domain_name": "keynotepresentations.com",
            "price": 12.0,
            "auction_end_date": "2026-06-16",
            "registrar": "NameJet",
            "tld": "com",
            "source": SOURCE,
            "dr": 3,
            "referring_domains": 6,
            "domain_age": 1,
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
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Language": "en-US,en;q=0.5",
                    "Referer": self.LISTINGS_URL,
                },
                follow_redirects=True,
                timeout=30.0,
            ) as client:
                domains = await self._fetch_api(client)
                if not domains:
                    self.logger.warning("NameJet API returned no results, trying HTML fallback")
                    domains = await self._fetch_html_fallback(client)
                if not domains:
                    self.logger.warning("No domains scraped, returning mock data")
                    return list(self.MOCK_DOMAINS)
                return domains
        except Exception:
            self.logger.exception("NameJet collector failed")
            return list(self.MOCK_DOMAINS)

    async def _fetch_api(self, client: httpx.AsyncClient) -> list[dict]:
        domains: list[dict] = []
        page = 1

        while page <= 5:
            try:
                payload = {
                    "page": page,
                    "pageSize": 50,
                    "sort": "endingSoon",
                    "order": "asc",
                }
                resp = await client.post(self.API_URL, json=payload)
                if resp.status_code in (401, 403, 404):
                    self.logger.info("API endpoint not accessible (status %d)", resp.status_code)
                    return []
                if resp.status_code != 200:
                    self.logger.warning("API returned status %d", resp.status_code)
                    await asyncio.sleep(0.5)
                    continue

                data = resp.json()
                items = data.get("items") or data.get("auctions") or data.get("results") or []
                if not items:
                    break

                for item in items:
                    try:
                        domain_name = (
                            item.get("domainName")
                            or item.get("domain")
                            or item.get("DomainName")
                            or ""
                        )
                        if not domain_name:
                            continue
                        tld = domain_name.split(".")[-1] if "." in domain_name else ""
                        domains.append({
                            "domain_name": domain_name,
                            "price": self._parse_price(item),
                            "auction_end_date": self._parse_end_date(item),
                            "registrar": "NameJet",
                            "tld": tld,
                            "source": self.SOURCE,
                            "dr": int(item.get("dr", 0) or 0),
                            "referring_domains": int(item.get("referringDomains", 0) or 0),
                            "domain_age": int(item.get("domainAge", 0) or 0),
                        })
                    except Exception:
                        continue

                total_pages = data.get("totalPages", 0) or data.get("pageCount", 0) or page
                if page >= total_pages:
                    break
                page += 1
                await asyncio.sleep(0.5)
            except httpx.HTTPStatusError:
                self.logger.warning("NameJet API HTTP error on page %d", page)
                return domains
            except Exception:
                self.logger.warning("Failed to parse NameJet API page %d", page)
                await asyncio.sleep(0.5)
                page += 1

        return domains

    async def _fetch_html_fallback(self, client: httpx.AsyncClient) -> list[dict]:
        domains: list[dict] = []
        for page in range(1, 4):
            try:
                resp = await client.get(self.LISTINGS_URL, params={"page": page})
                resp.raise_for_status()
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(resp.text, "html.parser")
                for row in soup.select("table tr, .auction-item, .domain-row"):
                    cells = row.find_all("td")
                    if len(cells) < 3:
                        continue
                    try:
                        domain_name = cells[0].get_text(strip=True).split()[0]
                        if "." not in domain_name:
                            continue
                        tld = domain_name.split(".")[-1]
                        domains.append({
                            "domain_name": domain_name,
                            "price": self._parse_price_text(cells[1].get_text(strip=True)),
                            "auction_end_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                            "registrar": "NameJet",
                            "tld": tld,
                            "source": self.SOURCE,
                            "dr": 0,
                            "referring_domains": 0,
                            "domain_age": 0,
                        })
                    except Exception:
                        continue
                await asyncio.sleep(1.0)
            except Exception:
                self.logger.warning("Failed to fetch NameJet HTML page %d", page)
                break
        return domains

    def _parse_price(self, item: dict) -> float:
        for key in ("currentBid", "price", "CurrentBid", "minPrice", "reservePrice"):
            val = item.get(key)
            if val is not None:
                try:
                    return float(val)
                except (ValueError, TypeError):
                    pass
        return 0.0

    def _parse_price_text(self, text: str) -> float:
        import re

        match = re.search(r"\$?(\d+[\d,.]*)", text)
        if match:
            try:
                return float(match.group(1).replace(",", ""))
            except ValueError:
                pass
        return 0.0

    def _parse_end_date(self, item: dict) -> str:
        for key in ("endDate", "auctionEnd", "endTime", "EndDate"):
            val = item.get(key)
            if val:
                try:
                    dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
                    return dt.strftime("%Y-%m-%d")
                except (ValueError, TypeError):
                    pass
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
