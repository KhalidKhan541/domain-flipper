from __future__ import annotations

import asyncio
import random
import re
from datetime import datetime, timedelta, timezone

import httpx
from bs4 import BeautifulSoup

from src.collectors.base import BaseCollector
from src.config import settings
from src.utils import async_retry, setup_logger


class GoDaddyCollector(BaseCollector):
    SOURCE = "GoDaddy"
    source = SOURCE
    API_URL = "https://auctions.godaddy.com/api/v1/search"
    SEARCH_URL = "https://auctions.godaddy.com/search"

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    ]

    MOCK_DOMAINS = [
        {
            "domain_name": "aifinancehub.com",
            "price": 42.0,
            "auction_end_date": "2026-06-20",
            "registrar": "GoDaddy",
            "tld": "com",
            "source": SOURCE,
            "dr": 34,
            "referring_domains": 187,
            "domain_age": 8,
        },
        {
            "domain_name": "cloudpulse.io",
            "price": 28.0,
            "auction_end_date": "2026-06-21",
            "registrar": "GoDaddy",
            "tld": "io",
            "source": SOURCE,
            "dr": 18,
            "referring_domains": 94,
            "domain_age": 3,
        },
        {
            "domain_name": "datavaultpro.com",
            "price": 55.0,
            "auction_end_date": "2026-06-22",
            "registrar": "GoDaddy",
            "tld": "com",
            "source": SOURCE,
            "dr": 27,
            "referring_domains": 203,
            "domain_age": 6,
        },
        {
            "domain_name": "edgecompute.net",
            "price": 33.0,
            "auction_end_date": "2026-06-23",
            "registrar": "GoDaddy",
            "tld": "net",
            "source": SOURCE,
            "dr": 12,
            "referring_domains": 68,
            "domain_age": 4,
        },
        {
            "domain_name": "fintechbridge.co",
            "price": 47.0,
            "auction_end_date": "2026-06-24",
            "registrar": "GoDaddy",
            "tld": "co",
            "source": SOURCE,
            "dr": 21,
            "referring_domains": 156,
            "domain_age": 5,
        },
        {
            "domain_name": "globalreach.org",
            "price": 19.0,
            "auction_end_date": "2026-06-25",
            "registrar": "GoDaddy",
            "tld": "org",
            "source": SOURCE,
            "dr": 9,
            "referring_domains": 42,
            "domain_age": 7,
        },
        {
            "domain_name": "horizonanalytics.com",
            "price": 68.0,
            "auction_end_date": "2026-06-26",
            "registrar": "GoDaddy",
            "tld": "com",
            "source": SOURCE,
            "dr": 31,
            "referring_domains": 245,
            "domain_age": 9,
        },
        {
            "domain_name": "intellisync.dev",
            "price": 39.0,
            "auction_end_date": "2026-06-27",
            "registrar": "GoDaddy",
            "tld": "dev",
            "source": SOURCE,
            "dr": 15,
            "referring_domains": 87,
            "domain_age": 2,
        },
        {
            "domain_name": "jetstreammedia.tv",
            "price": 24.0,
            "auction_end_date": "2026-06-28",
            "registrar": "GoDaddy",
            "tld": "tv",
            "source": SOURCE,
            "dr": 7,
            "referring_domains": 23,
            "domain_age": 3,
        },
        {
            "domain_name": "keyframe.pro",
            "price": 15.0,
            "auction_end_date": "2026-06-29",
            "registrar": "GoDaddy",
            "tld": "pro",
            "source": SOURCE,
            "dr": 5,
            "referring_domains": 14,
            "domain_age": 2,
        },
        {
            "domain_name": "logixplatform.com",
            "price": 72.0,
            "auction_end_date": "2026-06-30",
            "registrar": "GoDaddy",
            "tld": "com",
            "source": SOURCE,
            "dr": 38,
            "referring_domains": 312,
            "domain_age": 10,
        },
        {
            "domain_name": "meridianhealth.app",
            "price": 31.0,
            "auction_end_date": "2026-06-19",
            "registrar": "GoDaddy",
            "tld": "app",
            "source": SOURCE,
            "dr": 11,
            "referring_domains": 56,
            "domain_age": 4,
        },
        {
            "domain_name": "nexuspayments.biz",
            "price": 26.0,
            "auction_end_date": "2026-06-18",
            "registrar": "GoDaddy",
            "tld": "biz",
            "source": SOURCE,
            "dr": 8,
            "referring_domains": 35,
            "domain_age": 5,
        },
        {
            "domain_name": "opendataspace.com",
            "price": 51.0,
            "auction_end_date": "2026-06-17",
            "registrar": "GoDaddy",
            "tld": "com",
            "source": SOURCE,
            "dr": 23,
            "referring_domains": 178,
            "domain_age": 6,
        },
        {
            "domain_name": "quantumcode.io",
            "price": 88.0,
            "auction_end_date": "2026-06-16",
            "registrar": "GoDaddy",
            "tld": "io",
            "source": SOURCE,
            "dr": 42,
            "referring_domains": 397,
            "domain_age": 12,
        },
        {
            "domain_name": "servicenowhub.com",
            "price": 0.0,
            "auction_end_date": "2026-06-15",
            "registrar": "GoDaddy",
            "tld": "com",
            "source": SOURCE,
            "dr": 14,
            "referring_domains": 73,
            "domain_age": 3,
        },
        {
            "domain_name": "techventures.xyz",
            "price": 11.0,
            "auction_end_date": "2026-06-14",
            "registrar": "GoDaddy",
            "tld": "xyz",
            "source": SOURCE,
            "dr": 3,
            "referring_domains": 8,
            "domain_age": 1,
        },
        {
            "domain_name": "velocitylabs.tech",
            "price": 44.0,
            "auction_end_date": "2026-06-13",
            "registrar": "GoDaddy",
            "tld": "tech",
            "source": SOURCE,
            "dr": 17,
            "referring_domains": 109,
            "domain_age": 5,
        },
    ]

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config or {})
        self.logger = setup_logger(self.__class__.__name__)

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "application/json, text/html, application/xhtml+xml, application/xml;q=0.9, */*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://auctions.godaddy.com/",
            "DNT": "1",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }

    @async_retry()
    async def collect(self) -> list[dict]:
        if self._offline_mode:
            return list(self.MOCK_DOMAINS)
        try:
            async with httpx.AsyncClient(
                headers=self._headers(),
                follow_redirects=True,
                timeout=30.0,
            ) as client:
                domains = await self._fetch_from_api(client)
                if domains:
                    filtered = self._filter_by_budget(domains)
                    self.logger.info(
                        "Collected %d domains from GoDaddy (%d after budget filter)",
                        len(domains),
                        len(filtered),
                    )
                    return filtered

                self.logger.info("API returned no results, trying HTML fallback")
                domains = await self._fetch_from_html(client)
                if domains:
                    filtered = self._filter_by_budget(domains)
                    self.logger.info(
                        "Collected %d domains via HTML (%d after budget filter)",
                        len(domains),
                        len(filtered),
                    )
                    return filtered

                self.logger.warning("No domains from GoDaddy, returning mock data")
                return list(self.MOCK_DOMAINS)
        except Exception:
            self.logger.exception("GoDaddy collector failed")
            return list(self.MOCK_DOMAINS)

    async def _fetch_from_api(self, client: httpx.AsyncClient) -> list[dict]:
        domains: list[dict] = []
        for page in range(1, 4):
            try:
                params = {
                    "page": page,
                    "perPage": 50,
                    "sort": "ending_soonest",
                    "type": "auction,buynow",
                }
                resp = await client.get(self.API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
                page_domains = self._parse_api_response(data)
                domains.extend(page_domains)
                self.logger.debug("API page %d: %d domains", page, len(page_domains))
                if len(page_domains) < 50:
                    break
                await asyncio.sleep(random.uniform(1.5, 3.0))
            except httpx.HTTPStatusError as e:
                self.logger.warning("API page %d returned %s", page, e.response.status_code)
                break
            except Exception:
                self.logger.warning("Failed to parse API page %d", page)
                break
        return domains

    async def _fetch_from_html(self, client: httpx.AsyncClient) -> list[dict]:
        domains: list[dict] = []
        for page in range(1, 4):
            try:
                params = {
                    "page": page,
                    "perPage": 50,
                    "sort": "ending_soonest",
                }
                resp = await client.get(self.SEARCH_URL, params=params)
                resp.raise_for_status()
                page_domains = self._parse_html(resp.text)
                domains.extend(page_domains)
                self.logger.debug("HTML page %d: %d domains", page, len(page_domains))
                if len(page_domains) < 50:
                    break
                await asyncio.sleep(random.uniform(2.0, 4.0))
            except Exception:
                self.logger.warning("Failed to fetch HTML page %d", page)
                break
        return domains

    def _parse_api_response(self, data: dict) -> list[dict]:
        domains: list[dict] = []
        results = data.get("results") or data.get("domains") or []
        if isinstance(results, dict):
            results = results.get("domains", [])
        for item in results:
            try:
                domain = self._parse_api_item(item)
                if domain:
                    domains.append(domain)
            except Exception:
                continue
        return domains

    def _parse_api_item(self, item: dict) -> dict | None:
        domain_name = item.get("domainName") or item.get("domain", "")
        if not domain_name:
            return None

        price = 0.0
        buy_now = item.get("buyNowPrice") or item.get("buyNow")
        current_bid = item.get("currentBid") or item.get("currentPrice")
        if buy_now:
            price = float(buy_now)
        elif current_bid:
            price = float(current_bid)

        tld = domain_name.split(".")[-1] if "." in domain_name else ""
        raw_tld = item.get("tld", "")
        if raw_tld and raw_tld.startswith("."):
            tld = raw_tld[1:]

        time_left = item.get("timeLeft", "")
        auction_end = self._parse_time_left(time_left)

        return {
            "domain_name": domain_name,
            "price": price,
            "auction_end_date": auction_end,
            "registrar": "GoDaddy",
            "tld": tld,
            "source": self.SOURCE,
            "dr": int(item.get("dr", 0)),
            "referring_domains": int(item.get("referringDomains", 0)),
            "domain_age": int(item.get("domainAge", 0)),
        }

    def _parse_html(self, html: str) -> list[dict]:
        domains: list[dict] = []
        soup = BeautifulSoup(html, "html.parser")

        for row in soup.select("div.listing-row, tr.listing, [data-domain]"):
            try:
                domain_name = ""
                domain_el = (
                    row.select_one("[data-cy='domain-name'], .domain-name, .domain a")
                    or row.find("a", href=re.compile(r"/domain/"))
                )
                if domain_el:
                    domain_name = domain_el.get_text(strip=True).lower()
                if not domain_name:
                    domain_name = (row.get("data-domain") or "").strip()
                if not domain_name or "." not in domain_name:
                    continue

                price = 0.0
                price_el = (
                    row.select_one("[data-cy='current-bid'], .current-bid, .price, .buy-now")
                    or row.find("span", class_=re.compile(r"price|bid|cost"))
                )
                if price_el:
                    price_text = price_el.get_text(strip=True)
                    match = re.search(r"\$?([\d,]+(?:\.\d{1,2})?)", price_text)
                    if match:
                        price = float(match.group(1).replace(",", ""))

                tld = domain_name.split(".")[-1] if "." in domain_name else ""

                time_left = ""
                time_el = (
                    row.select_one("[data-cy='time-left'], .time-left, .time, .countdown")
                    or row.find("span", class_=re.compile(r"time|countdown|remaining"))
                )
                if time_el:
                    time_left = time_el.get_text(strip=True)

                domains.append({
                    "domain_name": domain_name,
                    "price": price,
                    "auction_end_date": self._parse_time_left(time_left),
                    "registrar": "GoDaddy",
                    "tld": tld,
                    "source": self.SOURCE,
                    "dr": 0,
                    "referring_domains": 0,
                    "domain_age": 0,
                })
            except Exception:
                continue

        return domains

    def _parse_time_left(self, time_left: str) -> str:
        if not time_left:
            return datetime.now(timezone.utc).strftime("%Y-%m-%d")
        text = time_left.lower().strip()
        if text in ("ended", "closed", "sold", "expired"):
            return datetime.now(timezone.utc).strftime("%Y-%m-%d")

        days = hours = mins = 0
        d_match = re.search(r"(\d+)\s*d(?:ays?)?", text)
        h_match = re.search(r"(\d+)\s*h(?:ours?)?", text)
        m_match = re.search(r"(\d+)\s*m(?:in(?:s|utes?))?", text)

        if d_match:
            days = int(d_match.group(1))
        if h_match:
            hours = int(h_match.group(1))
        if m_match:
            mins = int(m_match.group(1))

        if days == 0 and hours == 0 and mins == 0:
            return datetime.now(timezone.utc).strftime("%Y-%m-%d")

        end = datetime.now(timezone.utc) + timedelta(days=days, hours=hours, minutes=mins)
        return end.strftime("%Y-%m-%d")

    def _filter_by_budget(self, domains: list[dict]) -> list[dict]:
        return [
            d for d in domains
            if d["price"] == 0 or d["price"] <= settings.max_bid
        ]
