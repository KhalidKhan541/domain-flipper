from __future__ import annotations

import random
import re

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from src.feeds.base import BaseFeed
from src.utils import setup_logger

DOMAIN_RE = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
]

PAGE_TIMEOUT_MS = 60_000


class AuctionFeed(BaseFeed):
    source = "auctionfeed"

    SOURCES = {
        "namecheap": "https://www.namecheap.com/domains/expired/",
        "domainpunch": "https://domainpunch.com/tlds/expired.php",
        "namebright": "https://www.namebright.com/expired",
    }

    def __init__(self) -> None:
        self.logger = setup_logger(self.__class__.__name__)

    async def fetch(self, max_domains: int = 200) -> list[dict]:
        collected: list[str] = []

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                try:
                    for name, url in self.SOURCES.items():
                        if len(collected) >= max_domains:
                            break
                        try:
                            html = await self._fetch_page(browser, url)
                            if not html:
                                self.logger.warning("Empty HTML from %s", name)
                                continue
                            domains = self._parse_page(html, name)
                            if domains:
                                self.logger.info("Fetched %d domains from %s", len(domains), name)
                                collected.extend(domains)
                            else:
                                self.logger.warning("No domains parsed from %s", name)
                        except Exception:
                            self.logger.warning("Scrape failed for %s", name, exc_info=True)
                finally:
                    await browser.close()
        except Exception:
            self.logger.exception("Failed to launch Playwright browser")

        if not collected:
            self.logger.warning("All sources returned empty — returning empty (no fallback)")

        result_domains = list(dict.fromkeys(collected))[:max_domains]
        return [self._build_domain(d) for d in result_domains]

    async def _fetch_page(self, browser, url: str) -> str:
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
        )
        try:
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
            try:
                await page.wait_for_load_state("networkidle", timeout=PAGE_TIMEOUT_MS)
            except Exception:
                self.logger.debug("networkidle timed out for %s, proceeding", url)
            return await page.content()
        finally:
            await context.close()

    def _parse_page(self, html: str, source: str) -> list[str]:
        if source == "namecheap":
            return self._parse_namecheap(html)
        if source == "domainpunch":
            return self._parse_domainpunch(html)
        if source == "namebright":
            return self._parse_namebright(html)
        return []

    def _parse_namecheap(self, html: str) -> list[str]:
        domains: list[str] = []
        soup = BeautifulSoup(html, "html.parser")

        for el in soup.select("a[href*='/domains/expired/']"):
            text = el.get_text(strip=True)
            if DOMAIN_RE.match(text):
                domains.append(text.lower())

        for el in soup.find_all("td", class_=re.compile(r"domain|name", re.I)):
            text = el.get_text(strip=True)
            if DOMAIN_RE.match(text):
                domains.append(text.lower())

        for el in soup.find_all("div", class_=re.compile(r"domain|name", re.I)):
            text = el.get_text(strip=True)
            match = re.search(
                r"([a-zA-Z0-9][a-zA-Z0-9.-]+[a-zA-Z0-9]\.[a-zA-Z]{2,})", text
            )
            if match and DOMAIN_RE.match(match.group(1)):
                domains.append(match.group(1).lower())

        return list(dict.fromkeys(domains))

    def _parse_domainpunch(self, html: str) -> list[str]:
        domains: list[str] = []
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup.find_all(["a", "td", "li"]):
            text = tag.get_text(strip=True)
            for word in text.split():
                word = word.strip(",;.")
                if DOMAIN_RE.match(word):
                    domains.append(word.lower())

        for pre in soup.find_all("pre"):
            for line in pre.get_text().splitlines():
                line = line.strip()
                if DOMAIN_RE.match(line):
                    domains.append(line.lower())

        for el in soup.find_all("div", class_=re.compile(r"domain|expired", re.I)):
            text = el.get_text(strip=True)
            for word in text.split():
                word = word.strip(",;.")
                if DOMAIN_RE.match(word):
                    domains.append(word.lower())

        return list(dict.fromkeys(domains))

    def _parse_namebright(self, html: str) -> list[str]:
        domains: list[str] = []
        soup = BeautifulSoup(html, "html.parser")

        for el in soup.select("a[href*='/domain/']"):
            text = el.get_text(strip=True)
            if DOMAIN_RE.match(text):
                domains.append(text.lower())

        for el in soup.find_all("td", class_=re.compile(r"domain|name", re.I)):
            text = el.get_text(strip=True)
            if DOMAIN_RE.match(text):
                domains.append(text.lower())

        for row in soup.select("table tr"):
            cells = row.find_all("td")
            if len(cells) >= 3:
                text = cells[0].get_text(strip=True)
                if DOMAIN_RE.match(text):
                    domains.append(text.lower())
                text2 = cells[1].get_text(strip=True)
                if DOMAIN_RE.match(text2):
                    domains.append(text2.lower())

        return list(dict.fromkeys(domains))

    def _build_domain(self, domain_name: str) -> dict:
        tld = domain_name.split(".")[-1] if "." in domain_name else ""
        return {
            "domain_name": domain_name,
            "price": 0.0,
            "source": self.source,
            "tld": tld,
            "registrar": "",
            "dr": 0,
            "referring_domains": 0,
            "domain_age": 0,
        }
