"""
Free Domain Scraper — adapted from agent-os scraper pattern.
Uses simple HTTP requests with proper User-Agent headers.
No Playwright, no API keys, completely free.
"""

from __future__ import annotations

import re

import httpx
from bs4 import BeautifulSoup

from src.feeds.quality_filter import filter_domains
from src.utils import setup_logger

DOMAIN_RE = re.compile(
    r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.(com|io|ai|co|net|org|dev|app)$"
)

PREMIUM_TLDS = {"com", "io", "ai", "co", "net", "org", "dev", "app"}

# Known websites to exclude (not actual expired domains)
EXCLUDE_DOMAINS: set[str] = {
    "expireddomains.net", "domainsindex.com", "porkbun.com",
    "namecheap.com", "godaddy.com", "dynadot.com", "namesilo.com",
    "cloudflare.com", "google.com", "facebook.com", "twitter.com",
    "github.com", "stackoverflow.com", "amazon.com", "microsoft.com",
    "apple.com", "wikipedia.org", "reddit.com", "linkedin.com",
    "flippa.com", "afternic.com", "sedo.com", "dan.com",
    "catched.com", "gname.com", "nicsell.com", "majestic.com",
    "ahrefs.com", "semrush.com", "moz.com", "googletagmanager.com",
    "gstatic.com", "cloudfront.net", "bugsnag.com", "googleapis.com",
    "google-analytics.com", "googlesyndication.com", "doubleclick.net",
    "googletagservices.com", "googleadservices.com", "youtube.com",
    "w3.org", "schema.org", "jquery.com", "cloudflare-dns.com",
    "facebook.net", "twitter.com", "instagram.com", "tiktok.com",
}


class FreeDomainScraper:
    """Scrapes expired domains from free sources using simple HTTP requests."""

    def __init__(self) -> None:
        self.logger = setup_logger("FreeDomainScraper")

    async def fetch_all(self, max_domains: int = 300) -> list[dict]:
        """Fetch domains from all sources."""
        all_domains: list[str] = []

        async with httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
            follow_redirects=True,
            timeout=30.0,
        ) as client:
            # Source 1: ExpiredDomains.net
            try:
                domains = await self._scrape_expireddomains_net(client)
                all_domains.extend(domains)
                self.logger.info("expireddomains.net: %d domains", len(domains))
            except Exception as e:
                self.logger.warning("expireddomains.net failed: %s", e)

            # Source 2: ExpiredDomains.net drop list
            try:
                domains = await self._scrape_drop_list(client)
                all_domains.extend(domains)
                self.logger.info("drop list: %d domains", len(domains))
            except Exception as e:
                self.logger.warning("drop list failed: %s", e)

            # Source 3: Flippa (free listings)
            try:
                domains = await self._scrape_flippa(client)
                all_domains.extend(domains)
                self.logger.info("flippa: %d domains", len(domains))
            except Exception as e:
                self.logger.warning("flippa failed: %s", e)

            # Source 4: Domain marketplace listings
            try:
                domains = await self._scrape_marketplaces(client)
                all_domains.extend(domains)
                self.logger.info("marketplaces: %d domains", len(domains))
            except Exception as e:
                self.logger.warning("marketplaces failed: %s", e)

        # Deduplicate
        unique = list(dict.fromkeys(all_domains))
        self.logger.info("Total unique domains: %d", len(unique))

        # Convert to dicts and filter
        domain_dicts = [self._make_dict(d) for d in unique[:max_domains]]
        return filter_domains(domain_dicts)

    async def _scrape_expireddomains_net(self, client: httpx.AsyncClient) -> list[str]:
        """Scrape expireddomains.net for expired domains."""
        domains: list[str] = []

        urls = [
            "https://www.expireddomains.net/expired-domains/",
            "https://www.expireddomains.net/expiring-domains/",
        ]

        for url in urls:
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")

                # Look for domain names in table cells (primary source)
                for table in soup.find_all("table"):
                    for row in table.find_all("tr"):
                        cells = row.find_all("td")
                        for cell in cells:
                            text = cell.get_text(strip=True).lower()
                            if DOMAIN_RE.match(text) and text not in EXCLUDE_DOMAINS:
                                domains.append(text)

                # Look for domain names in links with domain-related href
                for a in soup.find_all("a", href=True):
                    href = a.get("href", "")
                    text = a.get_text(strip=True).lower()
                    if DOMAIN_RE.match(text) and text not in EXCLUDE_DOMAINS:
                        domains.append(text)
                    # Check if href contains domain name
                    if "/domain/" in href or "/expired/" in href:
                        parts = href.split("/")
                        for part in parts:
                            if DOMAIN_RE.match(part) and part not in EXCLUDE_DOMAINS:
                                domains.append(part)

            except Exception:
                continue

        return list(dict.fromkeys(domains))

    async def _scrape_drop_list(self, client: httpx.AsyncClient) -> list[str]:
        """Scrape drop list / expiring domain lists."""
        domains: list[str] = []

        urls = [
            "https://www.expireddomains.net/domains/catched/",
            "https://www.expireddomains.net/domains/dropped/",
        ]

        for url in urls:
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")

                # Focus on table data
                for table in soup.find_all("table"):
                    for row in table.find_all("tr"):
                        cells = row.find_all("td")
                        for cell in cells:
                            text = cell.get_text(strip=True).lower()
                            if DOMAIN_RE.match(text) and text not in EXCLUDE_DOMAINS:
                                domains.append(text)

            except Exception:
                continue

        return list(dict.fromkeys(domains))

    async def _scrape_flippa(self, client: httpx.AsyncClient) -> list[str]:
        """Scrape Flippa free domain listings."""
        domains: list[str] = []

        try:
            resp = await client.get("https://flippa.com/domains")
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")

                # Look for domain names in listing cards
                for card in soup.find_all(["div", "a", "span"], class_=re.compile(r"listing|card|title|name", re.I)):
                    text = card.get_text(strip=True).lower()
                    # Extract domain from text
                    match = re.search(r'([a-z0-9-]{2,63}\.(?:com|io|ai|co|net|org|dev|app))', text)
                    if match:
                        domain = match.group(1)
                        if DOMAIN_RE.match(domain) and domain not in EXCLUDE_DOMAINS:
                            domains.append(domain)

                # Also check links
                for a in soup.find_all("a", href=True):
                    text = a.get_text(strip=True).lower()
                    if DOMAIN_RE.match(text) and text not in EXCLUDE_DOMAINS:
                        domains.append(text)

        except Exception:
            pass

        return list(dict.fromkeys(domains))

    async def _scrape_marketplaces(self, client: httpx.AsyncClient) -> list[str]:
        """Scrape various domain marketplaces."""
        domains: list[str] = []

        # Try Afternic free listings
        try:
            resp = await client.get("https://www.afternic.com/search?k=&t=com")
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for el in soup.find_all(["div", "span", "a"], class_=re.compile(r"domain|name|title", re.I)):
                    text = el.get_text(strip=True).lower()
                    if DOMAIN_RE.match(text) and text not in EXCLUDE_DOMAINS:
                        domains.append(text)
        except Exception:
            pass

        # Try Dan.com listings
        try:
            resp = await client.get("https://dan.com/buy-domain")
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for el in soup.find_all(["div", "span", "a"], class_=re.compile(r"domain|name|title", re.I)):
                    text = el.get_text(strip=True).lower()
                    if DOMAIN_RE.match(text) and text not in EXCLUDE_DOMAINS:
                        domains.append(text)
        except Exception:
            pass

        return list(dict.fromkeys(domains))

    def _make_dict(self, domain_name: str) -> dict:
        tld = domain_name.split(".")[-1]
        return {
            "domain_name": domain_name,
            "price": 0.0,
            "source": "free_scraper",
            "tld": tld,
            "dr": 0,
            "referring_domains": 0,
            "domain_age": 0,
        }
