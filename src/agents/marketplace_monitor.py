"""Agent 2: Marketplace Monitor — scrapes Flippa/Sedo/Afternic for listed domains."""

from __future__ import annotations

import asyncio
import re

import httpx
from bs4 import BeautifulSoup

from src.utils import setup_logger

DOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.(com|io|ai|co|net|org|dev|app)$")

EXCLUDE = {
    "google.com", "facebook.com", "amazon.com", "microsoft.com", "apple.com",
    "github.com", "youtube.com", "twitter.com", "tiktok.com", "instagram.com",
    "linkedin.com", "reddit.com", "netflix.com", "cloudflare.com", "godaddy.com",
    "namecheap.com", "porkbun.com", "stripe.com", "paypal.com", "wikipedia.org",
    "flippa.com", "sedo.com", "afternic.com", "dan.com",
}


async def _scrape_flippa(client: httpx.AsyncClient) -> list[dict]:
    """Scrape Flippa domain listings."""
    logger = setup_logger("FlippaMonitor")
    results: list[dict] = []
    try:
        # Flippa search API endpoint (public)
        resp = await client.get(
            "https://flippa.com/search",
            params={"filter[property_type]": "domain", "filter[status]": "open", "sort": "recent"},
        )
        if resp.status_code != 200:
            return results

        soup = BeautifulSoup(resp.text, "html.parser")

        # Find listing cards
        for card in soup.find_all(["div", "a"], class_=re.compile(r"listing|card|auction|result", re.I)):
            domain_el = card.find(["h2", "h3", "h4", "a", "span"], class_=re.compile(r"title|name|heading|domain", re.I))
            if not domain_el:
                continue
            text = domain_el.get_text(strip=True).lower()
            if not DOMAIN_RE.match(text) or text in EXCLUDE:
                continue

            price = 0.0
            price_el = card.find(["span", "div"], class_=re.compile(r"price|bid|amount", re.I))
            if price_el:
                match = re.search(r"\$?([\d,]+)", price_el.get_text(strip=True))
                if match:
                    price = float(match.group(1).replace(",", ""))

            link = card.find("a", href=True)
            url = ""
            if link:
                href = link.get("href", "")
                if "/listing/" in href:
                    url = f"https://flippa.com{href}" if href.startswith("/") else href

            results.append({
                "domain_name": text, "price": price, "source": "flippa",
                "tld": text.split(".")[-1], "listing_url": url,
                "status": "for_sale", "dr": 0, "referring_domains": 0, "domain_age": 0,
            })

        logger.info("Flippa: %d listings", len(results))
    except Exception as e:
        logger.warning("Flippa failed: %s", e)
    return results


async def _scrape_sedo(client: httpx.AsyncClient) -> list[dict]:
    """Scrape Sedo marketplace."""
    logger = setup_logger("SedoMonitor")
    results: list[dict] = []
    try:
        resp = await client.get("https://sedo.com/search/?keyword=&attr[104]=com&attr[105]=net&attr[106]=org&attr[107]=io")
        if resp.status_code != 200:
            return results

        soup = BeautifulSoup(resp.text, "html.parser")
        for card in soup.find_all(["div", "tr"], class_=re.compile(r"result|listing|row|domain", re.I)):
            domain_el = card.find(["a", "span", "td"], class_=re.compile(r"domain|name|title", re.I))
            if not domain_el:
                continue
            text = domain_el.get_text(strip=True).lower()
            if not DOMAIN_RE.match(text) or text in EXCLUDE:
                continue

            price = 0.0
            price_el = card.find(["span", "td"], class_=re.compile(r"price|amount|cost", re.I))
            if price_el:
                match = re.search(r"\$?([\d,]+)", price_el.get_text(strip=True))
                if match:
                    price = float(match.group(1).replace(",", ""))

            results.append({
                "domain_name": text, "price": price, "source": "sedo",
                "tld": text.split(".")[-1], "status": "for_sale",
                "dr": 0, "referring_domains": 0, "domain_age": 0,
            })

        logger.info("Sedo: %d listings", len(results))
    except Exception as e:
        logger.warning("Sedo failed: %s", e)
    return results


async def _scrape_afternic(client: httpx.AsyncClient) -> list[dict]:
    """Scrape Afternic."""
    logger = setup_logger("AfternicMonitor")
    results: list[dict] = []
    try:
        resp = await client.get("https://www.afternic.com/search?k=&t=com")
        if resp.status_code != 200:
            return results

        soup = BeautifulSoup(resp.text, "html.parser")
        for card in soup.find_all(["div", "li"], class_=re.compile(r"domain|listing|result", re.I)):
            domain_el = card.find(["a", "span"], class_=re.compile(r"domain|name|title", re.I))
            if not domain_el:
                continue
            text = domain_el.get_text(strip=True).lower()
            if not DOMAIN_RE.match(text) or text in EXCLUDE:
                continue

            price = 0.0
            price_el = card.find(["span", "div"], class_=re.compile(r"price|amount", re.I))
            if price_el:
                match = re.search(r"\$?([\d,]+)", price_el.get_text(strip=True))
                if match:
                    price = float(match.group(1).replace(",", ""))

            results.append({
                "domain_name": text, "price": price, "source": "afternic",
                "tld": text.split(".")[-1], "status": "for_sale",
                "dr": 0, "referring_domains": 0, "domain_age": 0,
            })

        logger.info("Afternic: %d listings", len(results))
    except Exception as e:
        logger.warning("Afternic failed: %s", e)
    return results


async def run() -> list[dict]:
    """Scrape all marketplaces in parallel."""
    logger = setup_logger("MarketplaceMonitor")
    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        follow_redirects=True, timeout=30.0,
    ) as client:
        results = await asyncio.gather(
            _scrape_flippa(client),
            _scrape_sedo(client),
            _scrape_afternic(client),
            return_exceptions=True,
        )

    all_domains: list[dict] = []
    for r in results:
        if isinstance(r, list):
            all_domains.extend(r)

    unique = {d["domain_name"]: d for d in all_domains}
    final = list(unique.values())
    logger.info("Marketplace monitor found %d unique for-sale domains", len(final))
    return final
