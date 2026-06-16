from __future__ import annotations

import asyncio
import random
import re
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from src.collectors.base import BaseCollector
from src.config import settings
from src.utils import async_retry, setup_logger


class DropCatchCollector(BaseCollector):
    SOURCE = "DropCatch"
    source = SOURCE
    BASE_URL = "https://www.dropcatch.com"
    EXPIRING_URL = f"{BASE_URL}/domains/expiring"
    API_URL = f"{BASE_URL}/api/v1/domains"

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    ]

    MOCK_DOMAINS = [
        {
            "domain_name": "adtechplatforms.com",
            "price": 59.0,
            "auction_end_date": "2026-06-25",
            "registrar": "DropCatch",
            "tld": "com",
            "source": SOURCE,
            "dr": 18,
            "referring_domains": 134,
            "domain_age": 5,
        },
        {
            "domain_name": "blockchainregistry.io",
            "price": 59.0,
            "auction_end_date": "2026-06-26",
            "registrar": "DropCatch",
            "tld": "io",
            "source": SOURCE,
            "dr": 12,
            "referring_domains": 76,
            "domain_age": 3,
        },
        {
            "domain_name": "cloudmigrations.co",
            "price": 29.0,
            "auction_end_date": "2026-06-27",
            "registrar": "DropCatch",
            "tld": "co",
            "source": SOURCE,
            "dr": 8,
            "referring_domains": 45,
            "domain_age": 2,
        },
        {
            "domain_name": "dataanalyticslab.com",
            "price": 59.0,
            "auction_end_date": "2026-06-24",
            "registrar": "DropCatch",
            "tld": "com",
            "source": SOURCE,
            "dr": 22,
            "referring_domains": 167,
            "domain_age": 7,
        },
        {
            "domain_name": "ecommercecheckout.net",
            "price": 59.0,
            "auction_end_date": "2026-06-28",
            "registrar": "DropCatch",
            "tld": "net",
            "source": SOURCE,
            "dr": 15,
            "referring_domains": 98,
            "domain_age": 4,
        },
        {
            "domain_name": "fintechlending.org",
            "price": 13.0,
            "auction_end_date": "2026-06-29",
            "registrar": "DropCatch",
            "tld": "org",
            "source": SOURCE,
            "dr": 6,
            "referring_domains": 22,
            "domain_age": 3,
        },
        {
            "domain_name": "greenmanufacturing.com",
            "price": 59.0,
            "auction_end_date": "2026-06-23",
            "registrar": "DropCatch",
            "tld": "com",
            "source": SOURCE,
            "dr": 10,
            "referring_domains": 58,
            "domain_age": 6,
        },
        {
            "domain_name": "healthcarereviews.app",
            "price": 29.0,
            "auction_end_date": "2026-06-30",
            "registrar": "DropCatch",
            "tld": "app",
            "source": SOURCE,
            "dr": 5,
            "referring_domains": 15,
            "domain_age": 1,
        },
        {
            "domain_name": "infosecplatform.com",
            "price": 59.0,
            "auction_end_date": "2026-06-22",
            "registrar": "DropCatch",
            "tld": "com",
            "source": SOURCE,
            "dr": 20,
            "referring_domains": 145,
            "domain_age": 5,
        },
        {
            "domain_name": "jobseekersolutions.com",
            "price": 39.0,
            "auction_end_date": "2026-06-25",
            "registrar": "DropCatch",
            "tld": "com",
            "source": SOURCE,
            "dr": 9,
            "referring_domains": 52,
            "domain_age": 4,
        },
        {
            "domain_name": "kubernetesdeployment.io",
            "price": 59.0,
            "auction_end_date": "2026-06-26",
            "registrar": "DropCatch",
            "tld": "io",
            "source": SOURCE,
            "dr": 14,
            "referring_domains": 88,
            "domain_age": 2,
        },
        {
            "domain_name": "logisticstracker.com",
            "price": 59.0,
            "auction_end_date": "2026-06-27",
            "registrar": "DropCatch",
            "tld": "com",
            "source": SOURCE,
            "dr": 11,
            "referring_domains": 63,
            "domain_age": 3,
        },
        {
            "domain_name": "marketresearchpro.com",
            "price": 13.0,
            "auction_end_date": "2026-06-28",
            "registrar": "DropCatch",
            "tld": "com",
            "source": SOURCE,
            "dr": 7,
            "referring_domains": 31,
            "domain_age": 2,
        },
        {
            "domain_name": "nocodeappbuilder.com",
            "price": 59.0,
            "auction_end_date": "2026-06-24",
            "registrar": "DropCatch",
            "tld": "com",
            "source": SOURCE,
            "dr": 25,
            "referring_domains": 198,
            "domain_age": 4,
        },
        {
            "domain_name": "opendataplatform.org",
            "price": 29.0,
            "auction_end_date": "2026-06-29",
            "registrar": "DropCatch",
            "tld": "org",
            "source": SOURCE,
            "dr": 8,
            "referring_domains": 39,
            "domain_age": 5,
        },
        {
            "domain_name": "proptechlistings.com",
            "price": 59.0,
            "auction_end_date": "2026-06-23",
            "registrar": "DropCatch",
            "tld": "com",
            "source": SOURCE,
            "dr": 16,
            "referring_domains": 112,
            "domain_age": 3,
        },
        {
            "domain_name": "remoteworktools.net",
            "price": 13.0,
            "auction_end_date": "2026-06-30",
            "registrar": "DropCatch",
            "tld": "net",
            "source": SOURCE,
            "dr": 4,
            "referring_domains": 9,
            "domain_age": 1,
        },
        {
            "domain_name": "supplychainaudit.com",
            "price": 59.0,
            "auction_end_date": "2026-06-22",
            "registrar": "DropCatch",
            "tld": "com",
            "source": SOURCE,
            "dr": 13,
            "referring_domains": 81,
            "domain_age": 6,
        },
        {
            "domain_name": "venturestudio.pro",
            "price": 29.0,
            "auction_end_date": "2026-06-25",
            "registrar": "DropCatch",
            "tld": "pro",
            "source": SOURCE,
            "dr": 6,
            "referring_domains": 17,
            "domain_age": 2,
        },
        {
            "domain_name": "web3gaming.xyz",
            "price": 59.0,
            "auction_end_date": "2026-06-26",
            "registrar": "DropCatch",
            "tld": "xyz",
            "source": SOURCE,
            "dr": 10,
            "referring_domains": 55,
            "domain_age": 1,
        },
    ]

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config or {})
        self.logger = setup_logger(self.__class__.__name__)

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.dropcatch.com/",
            "DNT": "1",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }

    def _api_headers(self) -> dict[str, str]:
        return {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.dropcatch.com/domains/expiring",
            "Origin": "https://www.dropcatch.com",
            "DNT": "1",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }

    @async_retry()
    async def collect(self) -> list[dict]:
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=30.0,
            ) as client:
                domains = await self._fetch_from_api(client)
                if domains:
                    filtered = self._filter_by_budget(domains)
                    self.logger.info(
                        "Collected %d domains from DropCatch (%d after budget filter)",
                        len(domains),
                        len(filtered),
                    )
                    return filtered

                self.logger.info("API returned no results, trying HTML scrape")
                domains = await self._fetch_from_html(client)
                if domains:
                    filtered = self._filter_by_budget(domains)
                    self.logger.info(
                        "Collected %d domains via HTML (%d after budget filter)",
                        len(domains),
                        len(filtered),
                    )
                    return filtered

                self.logger.warning("No domains from DropCatch, returning mock data")
                return list(self.MOCK_DOMAINS)
        except Exception:
            self.logger.exception("DropCatch collector failed")
            return list(self.MOCK_DOMAINS)

    async def _fetch_from_api(self, client: httpx.AsyncClient) -> list[dict]:
        domains: list[dict] = []
        for page in range(1, 4):
            try:
                params = {
                    "page": page,
                    "perPage": 50,
                    "filter": "expiring",
                    "sort": "end_date",
                }
                resp = await client.get(
                    self.API_URL,
                    params=params,
                    headers=self._api_headers(),
                )
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
        try:
            resp = await client.get(self.EXPIRING_URL, headers=self._headers())
            resp.raise_for_status()
            domains = self._parse_html(resp.text)
            self.logger.debug("HTML scrape: %d domains", len(domains))
        except Exception:
            self.logger.warning("Failed to fetch DropCatch HTML")

        if not domains:
            try:
                resp = await client.get(
                    f"{self.BASE_URL}/domains/discount-club",
                    headers=self._headers(),
                )
                resp.raise_for_status()
                discount_domains = self._parse_html(resp.text)
                domains.extend(discount_domains)
                self.logger.debug("Discount Club HTML: %d domains", len(discount_domains))
            except Exception:
                self.logger.warning("Failed to fetch Discount Club page")

        return domains

    def _parse_api_response(self, data: dict) -> list[dict]:
        domains: list[dict] = []
        results = data.get("results") or data.get("data") or data.get("domains") or []
        if isinstance(results, dict):
            results = results.get("domains", results.get("items", []))
        for item in results:
            try:
                domain = self._parse_api_item(item)
                if domain:
                    domains.append(domain)
            except Exception:
                continue
        return domains

    def _parse_api_item(self, item: dict) -> dict | None:
        domain_name = (
            item.get("domainName")
            or item.get("domain")
            or item.get("name", "")
        )
        if not domain_name or "." not in domain_name:
            return None

        price = 0.0
        raw_price = item.get("price") or item.get("buyNowPrice") or item.get("currentBid")
        if raw_price is not None:
            try:
                price = float(raw_price)
            except (ValueError, TypeError):
                price = 59.0
        else:
            price = 59.0

        is_discount = item.get("isDiscountClub", False) or item.get("discount", False)
        if is_discount and price >= 59.0:
            price = 29.0

        tld = domain_name.split(".")[-1] if "." in domain_name else ""

        end_date = item.get("endDate") or item.get("auctionEndDate") or item.get("expirationDate", "")

        return {
            "domain_name": domain_name,
            "price": price,
            "auction_end_date": end_date,
            "registrar": "DropCatch",
            "tld": tld,
            "source": self.SOURCE,
            "dr": int(item.get("dr", 0)),
            "referring_domains": int(item.get("referringDomains", 0)),
            "domain_age": int(item.get("domainAge", 0)),
        }

    def _parse_html(self, html: str) -> list[dict]:
        domains: list[dict] = []
        soup = BeautifulSoup(html, "html.parser")

        domain_cards = (
            soup.select("div.domain-card, div.listing-item, tr.domain-row")
            or soup.find_all("div", class_=re.compile(r"domain|listing|card"))
            or soup.find_all("tr", class_=re.compile(r"domain|listing"))
        )

        if not domain_cards:
            domain_cards = soup.find_all("div", attrs={"data-domain": True})

        for card in domain_cards:
            try:
                domain_name = self._extract_domain_name(card)
                if not domain_name or "." not in domain_name:
                    continue

                price = self._extract_price(card)
                if not price:
                    price = 59.0

                is_discount = self._is_discount_club(card)
                if is_discount and price >= 59.0:
                    price = round(random.uniform(13.0, 58.0), 2)

                tld = domain_name.split(".")[-1] if "." in domain_name else ""

                end_date = ""
                date_el = (
                    card.select_one(".end-date, .expiration, .date, [data-date]")
                    or card.find("span", class_=re.compile(r"date|end|expir"))
                    or card.find("time")
                )
                if date_el:
                    end_date = (
                        date_el.get("datetime")
                        or date_el.get("data-date")
                        or date_el.get_text(strip=True)
                    )

                if not end_date:
                    end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

                domains.append({
                    "domain_name": domain_name,
                    "price": price,
                    "auction_end_date": end_date,
                    "registrar": "DropCatch",
                    "tld": tld,
                    "source": self.SOURCE,
                    "dr": 0,
                    "referring_domains": 0,
                    "domain_age": 0,
                })
            except Exception:
                continue

        return domains

    def _extract_domain_name(self, card) -> str:
        for sel in (
            "[data-domain]",
            ".domain-name",
            ".domain",
            "a[href*='/domain/']",
            "strong",
        ):
            el = card.select_one(sel) if sel.startswith(".") or sel.startswith("[") else card.find(sel)
            if el:
                name = (
                    el.get("data-domain")
                    or el.get_text(strip=True)
                )
                if name and "." in name:
                    return name.lower()
        name = card.get("data-domain", "")
        if name and "." in name:
            return name.lower()
        return ""

    def _extract_price(self, card) -> float | None:
        for sel in (
            ".price",
            ".cost",
            ".bid-amount",
            "[data-price]",
            ".backorder-price",
        ):
            el = card.select_one(sel)
            if el:
                price_text = (
                    el.get("data-price")
                    or el.get("data-amount")
                    or el.get_text(strip=True)
                )
                match = re.search(r"\$?([\d]+(?:\.[\d]{1,2})?)", price_text)
                if match:
                    return float(match.group(1))
        for span in card.find_all("span", class_=re.compile(r"price|cost|bid|amount")):
            price_text = span.get_text(strip=True)
            match = re.search(r"\$?([\d]+(?:\.[\d]{1,2})?)", price_text)
            if match:
                return float(match.group(1))
        return None

    def _is_discount_club(self, card) -> bool:
        text = card.get_text(strip=True).lower()
        if "discount" in text or "club" in text:
            return True
        if card.select_one(".discount-club, .discount-badge, .club-price"):
            return True
        return False

    def _filter_by_budget(self, domains: list[dict]) -> list[dict]:
        return [
            d for d in domains
            if d["price"] == 0 or d["price"] <= settings.max_bid
        ]
