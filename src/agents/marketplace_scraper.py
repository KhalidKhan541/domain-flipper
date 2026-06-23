"""Subagent 2: Scrapes domain marketplaces (Flippa, Afternic, Dan.com, Sedo)."""

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

EXCLUDE_DOMAINS: set[str] = {
    "google.com", "facebook.com", "amazon.com", "microsoft.com", "apple.com",
    "github.com", "stackoverflow.com", "linkedin.com", "twitter.com", "x.com",
    "youtube.com", "tiktok.com", "instagram.com", "reddit.com", "netflix.com",
    "cloudflare.com", "godaddy.com", "namecheap.com", "porkbun.com",
    "flippa.com", "afternic.com", "dan.com", "sedo.com", "escrow.com",
    "stripe.com", "paypal.com", "shopify.com", "wix.com", "squarespace.com",
    "wordpress.com", "blogspot.com", "medium.com", "substack.com",
}


async def _scrape_flippa(client: httpx.AsyncClient) -> list[dict]:
    """Scrape Flippa domain listings with prices."""
    logger = setup_logger("FlippaScraper")
    results: list[dict] = []

    try:
        # Flippa API-like endpoint for domain listings
        resp = await client.get(
            "https://flippa.com/domains",
            params={"type": "domain", "status": "live"},
        )
        if resp.status_code != 200:
            return results

        soup = BeautifulSoup(resp.text, "html.parser")

        # Find listing cards
        for card in soup.find_all(["div", "a"], class_=re.compile(r"listing|card|auction|item", re.I)):
            # Extract domain name
            domain_el = card.find(["h2", "h3", "h4", "a", "span"], class_=re.compile(r"title|name|heading|domain", re.I))
            if not domain_el:
                continue

            text = domain_el.get_text(strip=True).lower()
            if not DOMAIN_RE.match(text) or text in EXCLUDE_DOMAINS:
                continue

            # Extract price
            price = 0.0
            price_el = card.find(["span", "div"], class_=re.compile(r"price|bid|amount|cost", re.I))
            if price_el:
                price_text = price_el.get_text(strip=True)
                match = re.search(r"\$?([\d,]+(?:\.\d{2})?)", price_text)
                if match:
                    price = float(match.group(1).replace(",", ""))

            # Extract listing URL
            link = card.find("a", href=True)
            url = ""
            if link:
                href = link.get("href", "")
                if "/listing/" in href or "/domain/" in href:
                    url = f"https://flippa.com{href}" if href.startswith("/") else href

            results.append({
                "domain_name": text,
                "price": price,
                "source": "flippa",
                "tld": text.split(".")[-1],
                "listing_url": url,
                "dr": 0,
                "referring_domains": 0,
                "domain_age": 0,
            })

        logger.info("Flippa: %d listings found", len(results))
    except Exception as e:
        logger.warning("Flippa scrape failed: %s", e)

    return results


async def _scrape_afternic(client: httpx.AsyncClient) -> list[dict]:
    """Scrape Afternic fast-transfer listings."""
    logger = setup_logger("AfternicScraper")
    results: list[dict] = []

    try:
        resp = await client.get("https://www.afternic.com/search?k=&t=com&pricelt=500")
        if resp.status_code != 200:
            return results

        soup = BeautifulSoup(resp.text, "html.parser")

        for card in soup.find_all(["div", "li"], class_=re.compile(r"domain|listing|card|result", re.I)):
            domain_el = card.find(["a", "span", "div"], class_=re.compile(r"domain|name|title", re.I))
            if not domain_el:
                continue

            text = domain_el.get_text(strip=True).lower()
            if not DOMAIN_RE.match(text) or text in EXCLUDE_DOMAINS:
                continue

            price = 0.0
            price_el = card.find(["span", "div"], class_=re.compile(r"price|cost|amount", re.I))
            if price_el:
                match = re.search(r"\$?([\d,]+)", price_el.get_text(strip=True))
                if match:
                    price = float(match.group(1).replace(",", ""))

            results.append({
                "domain_name": text,
                "price": price,
                "source": "afternic",
                "tld": text.split(".")[-1],
                "dr": 0,
                "referring_domains": 0,
                "domain_age": 0,
            })

        logger.info("Afternic: %d listings found", len(results))
    except Exception as e:
        logger.warning("Afternic scrape failed: %s", e)

    return results


async def _scrape_dan(client: httpx.AsyncClient) -> list[dict]:
    """Scrape Dan.com marketplace."""
    logger = setup_logger("DanScraper")
    results: list[dict] = []

    try:
        resp = await client.get("https://dan.com/buy-domain")
        if resp.status_code != 200:
            return results

        soup = BeautifulSoup(resp.text, "html.parser")

        for card in soup.find_all(["div", "a"], class_=re.compile(r"domain|listing|card|item", re.I)):
            domain_el = card.find(["h2", "h3", "span", "a"], class_=re.compile(r"name|title|domain", re.I))
            if not domain_el:
                continue

            text = domain_el.get_text(strip=True).lower()
            if not DOMAIN_RE.match(text) or text in EXCLUDE_DOMAINS:
                continue

            price = 0.0
            price_el = card.find(["span", "div"], class_=re.compile(r"price|amount", re.I))
            if price_el:
                match = re.search(r"\$?([\d,]+)", price_el.get_text(strip=True))
                if match:
                    price = float(match.group(1).replace(",", ""))

            results.append({
                "domain_name": text,
                "price": price,
                "source": "dan",
                "tld": text.split(".")[-1],
                "dr": 0,
                "referring_domains": 0,
                "domain_age": 0,
            })

        logger.info("Dan.com: %d listings found", len(results))
    except Exception as e:
        logger.warning("Dan.com scrape failed: %s", e)

    return results


async def run() -> list[dict]:
    """Scrape all marketplaces and return domains with prices."""
    logger = setup_logger("MarketplaceAgent")
    all_results: list[dict] = []

    async with httpx.AsyncClient(
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        },
        follow_redirects=True,
        timeout=30.0,
    ) as client:
        results = await asyncio.gather(
            _scrape_flippa(client),
            _scrape_afternic(client),
            _scrape_dan(client),
            return_exceptions=True,
        )
        for r in results:
            if isinstance(r, list):
                all_results.extend(r)

    logger.info("Marketplace agent found %d total listings", len(all_results))
    return all_results
