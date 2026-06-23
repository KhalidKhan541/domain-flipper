"""Agent 1: Expiring Domain Scout — finds domains about to expire from free sources."""

from __future__ import annotations

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
    "googleapis.com", "gstatic.com", "cloudfront.net", "googletagmanager.com",
}


async def run() -> list[dict]:
    """Scrape free sources for expiring domains."""
    logger = setup_logger("ExpiringDomainScout")
    results: list[dict] = []

    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        follow_redirects=True, timeout=30.0,
    ) as client:
        # Source 1: Expireddomains.net expiring list
        try:
            resp = await client.get("https://www.expireddomains.net/expiring-domains/")
            if resp.status_code == 200:
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
                            if DOMAIN_RE.match(text) and text not in EXCLUDE:
                                # Try to extract price/bid from other cells
                                price = 0
                                for cell in cells[1:]:
                                    price_text = cell.get_text(strip=True)
                                    match = re.search(r"\$?([\d,]+)", price_text)
                                    if match:
                                        price = float(match.group(1).replace(",", ""))
                                        break
                                results.append({
                                    "domain_name": text, "price": price,
                                    "source": "expireddomains_expiring",
                                    "tld": text.split(".")[-1], "status": "expiring",
                                    "dr": 0, "referring_domains": 0, "domain_age": 0,
                                })
                logger.info("Expireddomains.net expiring: %d domains", len(results))
        except Exception as e:
            logger.warning("Expireddomains.net failed: %s", e)

        # Source 2: Expireddomains.net dropped list
        try:
            resp = await client.get("https://www.expireddomains.net/domains/dropped/")
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for table in soup.find_all("table"):
                    for row in table.find_all("tr"):
                        cells = row.find_all("td")
                        if len(cells) < 2:
                            continue
                        first_cell = cells[0]
                        link = first_cell.find("a")
                        if link:
                            text = link.get_text(strip=True).lower()
                            if DOMAIN_RE.match(text) and text not in EXCLUDE:
                                results.append({
                                    "domain_name": text, "price": 0,
                                    "source": "expireddomains_dropped",
                                    "tld": text.split(".")[-1], "status": "dropped",
                                    "dr": 0, "referring_domains": 0, "domain_age": 0,
                                })
                logger.info("Expireddomains.net dropped: %d domains", len(results))
        except Exception as e:
            logger.warning("Dropped list failed: %s", e)

        # Source 3: NameJet last chance (HTML scraping)
        try:
            resp = await client.get("https://www.namejet.com/")
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for row in soup.find_all("tr"):
                    cells = row.find_all("td")
                    if len(cells) >= 2:
                        link = cells[0].find("a")
                        if link:
                            text = link.get_text(strip=True).lower()
                            if DOMAIN_RE.match(text) and text not in EXCLUDE:
                                price_text = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                                match = re.search(r"\$?([\d,]+)", price_text)
                                price = float(match.group(1).replace(",", "")) if match else 0
                                results.append({
                                    "domain_name": text, "price": price,
                                    "source": "namejet", "tld": text.split(".")[-1],
                                    "status": "expiring", "dr": 0, "referring_domains": 0, "domain_age": 0,
                                })
                logger.info("NameJet: %d domains", len(results))
        except Exception as e:
            logger.warning("NameJet failed: %s", e)

        # Source 4: GoDaddy Auctions HTML
        try:
            resp = await client.get("https://auctions.godaddy.com/")
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for row in soup.find_all("tr"):
                    cells = row.find_all("td")
                    if len(cells) >= 2:
                        link = cells[0].find("a")
                        if link:
                            text = link.get_text(strip=True).lower()
                            if DOMAIN_RE.match(text) and text not in EXCLUDE:
                                price_text = cells[1].get_text(strip=True)
                                match = re.search(r"\$?([\d,]+)", price_text)
                                price = float(match.group(1).replace(",", "")) if match else 0
                                results.append({
                                    "domain_name": text, "price": price,
                                    "source": "godaddy", "tld": text.split(".")[-1],
                                    "status": "expiring", "dr": 0, "referring_domains": 0, "domain_age": 0,
                                })
                logger.info("GoDaddy: %d domains", len(results))
        except Exception as e:
            logger.warning("GoDaddy failed: %s", e)

    unique = {d["domain_name"]: d for d in results}
    final = list(unique.values())
    logger.info("Expiring scout found %d unique domains", len(final))
    return final
