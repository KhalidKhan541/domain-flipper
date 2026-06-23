"""Subagent 3: Finds domains with 'for sale' pages — discovers sellers actively selling."""

from __future__ import annotations

import asyncio
import re

import httpx
from bs4 import BeautifulSoup

from src.feeds.quality_filter import filter_domains
from src.utils import setup_logger

DOMAIN_RE = re.compile(
    r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.(com|io|ai|co|net|org|dev|app)$"
)

SALE_KEYWORDS = re.compile(
    r"(for\s+sale|buy\s+now|make\s+offer|price|domain\s+is?\s+for|"
    r"this\s+domain|buy\s+this|purchase|acquire|inquire|contact\s+owner|"
    r"listed\s+for|asking\s+price|best\s+offer|domain\s+broker|"
    r"premium\s+domain|parked\s+domain|domain\s+auction)",
    re.IGNORECASE,
)

EXCLUDE_DOMAINS: set[str] = {
    "google.com", "facebook.com", "amazon.com", "microsoft.com", "apple.com",
    "github.com", "stackoverflow.com", "linkedin.com", "twitter.com", "x.com",
    "youtube.com", "tiktok.com", "instagram.com", "reddit.com", "netflix.com",
    "cloudflare.com", "godaddy.com", "namecheap.com", "porkbun.com",
    "flippa.com", "afternic.com", "dan.com", "sedo.com", "escrow.com",
    "stripe.com", "paypal.com", "shopify.com", "wix.com", "squarespace.com",
    "wordpress.com", "blogspot.com", "medium.com", "substack.com",
    "hugedomains.com", "huge domains.com",
}


async def _check_domain_for_sale(client: httpx.AsyncClient, domain: str) -> dict | None:
    """Check if a domain has a 'for sale' page."""
    for scheme in ["https", "http"]:
        try:
            resp = await client.get(f"{scheme}://{domain}", timeout=15.0, follow_redirects=True)
            if resp.status_code != 200:
                continue

            html = resp.text.lower()

            # Check if page mentions sale keywords
            if not SALE_KEYWORDS.search(html):
                continue

            # Extract contact email
            emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", resp.text)
            emails = [e for e in emails if not e.endswith((".png", ".jpg", ".gif", ".svg"))]

            # Extract price if mentioned
            price = 0.0
            price_match = re.search(r"\$\s*([\d,]+(?:\.\d{2})?)", resp.text)
            if price_match:
                price = float(price_match.group(1).replace(",", ""))

            # Check for standard "for sale" platforms
            platform = ""
            if "dan.com" in html or "undeveloped" in html:
                platform = "dan.com"
            elif "afternic" in html:
                platform = "afternic"
            elif "sedo" in html:
                platform = "sedo"
            elif "hugedomains" in html:
                platform = "hugedomains"

            return {
                "domain_name": domain,
                "price": price,
                "source": "forsale_finder",
                "tld": domain.split(".")[-1],
                "seller_emails": emails[:3],
                "platform": platform,
                "for_sale": True,
                "dr": 0,
                "referring_domains": 0,
                "domain_age": 0,
            }

        except Exception:
            continue

    return None


async def _find_expired_with_forsale(client: httpx.AsyncClient) -> list[str]:
    """Find expired domains that had 'for sale' pages."""
    logger = setup_logger("ForSaleFinder")
    domains: list[str] = []

    # Search for expired domains on various listing sites
    urls = [
        "https://www.expireddomains.net/expired-domains/",
    ]

    for url in urls:
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            for table in soup.find_all("table"):
                headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
                if not any("domain" in h for h in headers):
                    continue
                for row in table.find_all("tr"):
                    cells = row.find_all("td")
                    if len(cells) < 2:
                        continue
                    first_cell = cells[0]
                    link = first_cell.find("a")
                    if link:
                        text = link.get_text(strip=True).lower()
                        if DOMAIN_RE.match(text) and text not in EXCLUDE_DOMAINS:
                            domains.append(text)
                    text = first_cell.get_text(strip=True).lower()
                    if DOMAIN_RE.match(text) and text not in EXCLUDE_DOMAINS:
                        domains.append(text)
        except Exception:
            continue

    return list(dict.fromkeys(domains))


async def run() -> list[dict]:
    """Find domains with 'for sale' pages."""
    logger = setup_logger("ForSaleAgent")

    async with httpx.AsyncClient(
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
        },
        follow_redirects=True,
        timeout=20.0,
    ) as client:
        # Step 1: Get candidate domains
        candidates = await _find_expired_with_forsale(client)
        logger.info("Checking %d candidate domains for 'for sale' pages", len(candidates))

        # Step 2: Check each domain (with concurrency limit)
        semaphore = asyncio.Semaphore(10)
        results: list[dict] = []

        async def check_one(domain: str):
            async with semaphore:
                result = await _check_domain_for_sale(client, domain)
                if result:
                    results.append(result)

        # Check first 100 candidates
        tasks = [check_one(d) for d in candidates[:100]]
        await asyncio.gather(*tasks)

    logger.info("For-sale agent found %d domains with sale pages", len(results))
    return results
