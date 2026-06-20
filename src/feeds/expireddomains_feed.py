from __future__ import annotations

import re

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from src.feeds.base import BaseFeed
from src.feeds.quality_filter import filter_domains
from src.utils import setup_logger

DOMAIN_REGEX = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.[a-z]{2,}$")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]


class ExpiredDomainsFeed(BaseFeed):
    """Fetches expired/expiring domains via Playwright browser automation."""

    source = "expireddomains"

    SOURCES = {
        "domainsindex": "https://domainsindex.com/expired-domains/",
        "expireddomains": "https://www.expireddomains.net/expired-domains/",
    }

    def __init__(self) -> None:
        self.logger = setup_logger("ExpiredDomainsFeed")

    async def fetch(self, max_domains: int = 200) -> list[dict]:
        all_domains: list[str] = []

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                try:
                    for name, url in self.SOURCES.items():
                        try:
                            user_agent = USER_AGENTS[hash(url) % len(USER_AGENTS)]
                            context = await browser.new_context(
                                user_agent=user_agent,
                                viewport={"width": 1920, "height": 1080},
                            )
                            page = await context.new_page()
                            try:
                                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                                await page.wait_for_selector("table", timeout=15000)
                                html = await page.content()
                                domains = self._parse_domain_table(html)
                                if domains:
                                    all_domains.extend(domains)
                                    self.logger.info("Fetched %d domains from %s", len(domains), name)
                                    if len(all_domains) >= max_domains:
                                        break
                                else:
                                    self.logger.warning("No domains parsed from %s", name)
                            except Exception:
                                self.logger.exception("Playwright scrape failed for %s", name)
                            finally:
                                await context.close()
                        except Exception:
                            self.logger.exception("Failed to create context for %s", name)
                finally:
                    await browser.close()
        except Exception:
            self.logger.exception("Failed to launch Playwright browser")

        if not all_domains:
            self.logger.warning("All sources returned empty")

        unique_domains = list(dict.fromkeys(all_domains))
        domain_dicts = [self._make_domain_dict(d) for d in unique_domains[:max_domains]]
        return filter_domains(domain_dicts)

    def _parse_domain_table(self, html: str) -> list[str]:
        domains: list[str] = []
        soup = BeautifulSoup(html, "html.parser")

        for table in soup.find_all("table"):
            for row in table.find_all("tr"):
                cells = row.find_all("td")
                for cell in cells:
                    text = cell.get_text(strip=True).lower()
                    if DOMAIN_REGEX.match(text):
                        domains.append(text)

        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if "domain" in href.lower() and "." in href:
                candidate = link.get_text(strip=True).lower()
                if DOMAIN_REGEX.match(candidate) and candidate not in domains:
                    domains.append(candidate)

        return list(dict.fromkeys(domains))

    def _make_domain_dict(self, domain_name: str) -> dict:
        tld = domain_name.split(".")[-1] if "." in domain_name else ""
        return {
            "domain_name": domain_name,
            "price": 0.0,
            "source": self.source,
            "tld": tld,
            "dr": 0,
            "referring_domains": 0,
            "domain_age": 0,
        }
