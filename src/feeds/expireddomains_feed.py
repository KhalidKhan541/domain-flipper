from __future__ import annotations

import re

import httpx
from bs4 import BeautifulSoup

from src.feeds.base import BaseFeed
from src.feeds.quality_filter import filter_domains
from src.utils import setup_logger

DOMAIN_REGEX = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.[a-z]{2,}$")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
]

# Known websites to exclude (not actual expired domains)
EXCLUDE_DOMAINS = {
    "expireddomains.net", "domainsindex.com", "porkbun.com",
    "namecheap.com", "godaddy.com", "dynadot.com", "namesilo.com",
    "cloudflare.com", "google.com", "facebook.com", "twitter.com",
    "github.com", "stackoverflow.com", "amazon.com", "microsoft.com",
    "apple.com", "wikipedia.org", "reddit.com", "linkedin.com",
    "flippa.com", "afternic.com", "sedo.com", "dan.com",
    "catched.com", "gname.com", "nicsell.com", "majestic.com",
    "ahrefs.com", "semrush.com", "moz.com",
}


class ExpiredDomainsFeed(BaseFeed):
    """Fetches expired/expiring domains via simple HTTP requests (no Playwright)."""

    source = "expireddomains"

    SOURCES = {
        "porkbun": "https://porkbun.com/checkout/search?q=&tld=com",
        "expireddomains": "https://www.expireddomains.net/expired-domains/",
        "domainsindex": "https://domainsindex.com/expired-domains/",
    }

    def __init__(self) -> None:
        self.logger = setup_logger("ExpiredDomainsFeed")

    async def fetch(self, max_domains: int = 200) -> list[dict]:
        all_domains: list[str] = []

        async with httpx.AsyncClient(
            headers={
                "User-Agent": USER_AGENTS[0],
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
            follow_redirects=True,
            timeout=30.0,
        ) as client:
            for name, url in self.SOURCES.items():
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        self.logger.warning("HTTP %d from %s", resp.status_code, name)
                        continue

                    html = resp.text
                    domains = self._parse_domains(html)
                    if domains:
                        all_domains.extend(domains)
                        self.logger.info("Fetched %d domains from %s", len(domains), name)
                        if len(all_domains) >= max_domains:
                            break
                    else:
                        self.logger.warning("No domains parsed from %s", name)
                except Exception:
                    self.logger.exception("Failed to fetch %s", name)

        if not all_domains:
            self.logger.warning("All sources returned empty")

        unique_domains = list(dict.fromkeys(all_domains))
        domain_dicts = [self._make_domain_dict(d) for d in unique_domains[:max_domains]]
        return filter_domains(domain_dicts)

    def _parse_domains(self, html: str) -> list[str]:
        """Extract domain names from HTML using multiple strategies."""
        domains: list[str] = []
        soup = BeautifulSoup(html, "html.parser")

        # Strategy 1: Find domains in table cells
        for table in soup.find_all("table"):
            for row in table.find_all("tr"):
                cells = row.find_all("td")
                for cell in cells:
                    text = cell.get_text(strip=True).lower()
                    if DOMAIN_REGEX.match(text) and text not in EXCLUDE_DOMAINS:
                        domains.append(text)

        # Strategy 2: Find domains in links
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            text = link.get_text(strip=True).lower()
            # Match domains in link text
            if DOMAIN_REGEX.match(text) and text not in EXCLUDE_DOMAINS:
                domains.append(text)
            # Match domains in href (e.g., /domain/example.com)
            if "domain" in href.lower():
                parts = href.split("/")
                for part in parts:
                    if DOMAIN_REGEX.match(part.lower()) and part.lower() not in EXCLUDE_DOMAINS:
                        domains.append(part.lower())

        # Strategy 3: Regex scan the entire HTML
        found = re.findall(r'\b([a-z0-9-]{2,63}\.(?:com|io|ai|co|net|org|dev|app))\b', html)
        for d in found:
            if DOMAIN_REGEX.match(d) and d not in EXCLUDE_DOMAINS:
                domains.append(d)

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
