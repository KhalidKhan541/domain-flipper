"""Agent 1: Expiring Domain Scout — finds domains about to expire and categorizes them."""

from __future__ import annotations

import asyncio
import re

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from src.utils import setup_logger

DOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.(com|io|ai|co|net|org|dev|app)$")

EXCLUDE = {
    "google.com", "facebook.com", "amazon.com", "microsoft.com", "apple.com",
    "github.com", "youtube.com", "twitter.com", "tiktok.com", "instagram.com",
    "linkedin.com", "reddit.com", "netflix.com", "cloudflare.com", "godaddy.com",
    "namecheap.com", "porkbun.com", "stripe.com", "paypal.com", "wikipedia.org",
    "flippa.com", "sedo.com", "afternic.com", "dan.com", "hugedomains.com",
    "googleapis.com", "gstatic.com", "cloudfront.net", "googletagmanager.com",
    "edgesuite.net", "akamai.net", "akamai.com", "edgecast.net",
    "yahoo.com", "bing.com", "msn.com", "aol.com", "ask.com",
    "walmart.com", "target.com", "bestbuy.com", "costco.com", "homedepot.com",
    "craigslist.org", "ebay.com", "etsy.com", "alibaba.com", "aliexpress.com",
    "wordpress.com", "wix.com", "squarespace.com", "shopify.com", "weebly.com",
    "godaddyhosting.com", "hostgator.com", "bluehost.com", "siteground.com",
}

# Category keywords for domain categorization
CATEGORY_KEYWORDS = {
    "ai": ["ai", "ml", "gpt", "llm", "neural", "deep", "machine", "learning", "chat", "bot", "intelligence"],
    "crypto": ["crypto", "coin", "token", "defi", "nft", "web3", "block", "chain", "wallet", "swap"],
    "health": ["health", "med", "doctor", "care", "well", "fit", "nutri", "pharma", "bio", "clinic"],
    "finance": ["fin", "bank", "pay", "invest", "trade", "stock", "insur", "loan", "credit", "money"],
    "saas": ["saas", "app", "soft", "tool", "dash", "analyt", "auto", "cloud", "data", "api"],
    "ecommerce": ["shop", "store", "buy", "sell", "market", "retail", "cart", "deal", "price", "sale"],
    "education": ["learn", "edu", "course", "school", "train", "tutor", "acad", "study", "teach"],
    "realestate": ["home", "house", "real", "estate", "rent", "lease", "mort", "prop", "land"],
    "food": ["food", "eat", "cook", "meal", "pizza", "cafe", "coffee", "delivery", "recipe"],
    "travel": ["travel", "hotel", "flight", "tour", "vacat", "book", "rent", "adventure"],
    "gaming": ["game", "play", "esport", "rpg", "mmo", "stream", "twitch"],
    "social": ["social", "community", "forum", "chat", "date", "friend", "connect"],
    "tech": ["tech", "dev", "code", "hack", "server", "host", "domain", "web", "net"],
    "green": ["eco", "green", "solar", "energy", "climate", "renew", "sustain"],
    "media": ["news", "blog", "pod", "video", "stream", "content", "press", "mag"],
}


def _categorize_domain(domain_name: str) -> list[str]:
    """Categorize a domain based on its name."""
    name = domain_name.split(".")[0].lower()
    categories = []

    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in name:
                categories.append(category)
                break

    return categories if categories else ["generic"]


def _estimate_value(domain_name: str, categories: list[str]) -> float:
    """Estimate domain value based on name and categories."""
    name = domain_name.split(".")[0]
    tld = domain_name.split(".")[-1]

    # Base value by TLD
    tld_values = {"com": 100, "io": 80, "ai": 90, "co": 70, "net": 50, "org": 40, "dev": 60, "app": 60}
    base = tld_values.get(tld, 30)

    # Premium categories get higher value
    premium_cats = {"ai": 1.5, "crypto": 1.3, "finance": 1.4, "health": 1.2, "saas": 1.3}
    multiplier = 1.0
    for cat in categories:
        if cat in premium_cats:
            multiplier = max(multiplier, premium_cats[cat])

    # Short domains are worth more
    if len(name) <= 4:
        multiplier *= 2.0
    elif len(name) <= 6:
        multiplier *= 1.5
    elif len(name) <= 8:
        multiplier *= 1.2

    return base * multiplier


async def _scrape_expireddomains_httpx(client: httpx.AsyncClient) -> list[dict]:
    """Scrape expireddomains.net via HTTP."""
    logger = setup_logger("ExpiredDomainsHTTPX")
    results: list[dict] = []

    # Expiring domains
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
                            price = 0
                            for cell in cells[1:]:
                                price_text = cell.get_text(strip=True)
                                match = re.search(r"\$?([\d,]+)", price_text)
                                if match:
                                    price = float(match.group(1).replace(",", ""))
                                    break

                            categories = _categorize_domain(text)
                            estimated_value = _estimate_value(text, categories)

                            results.append({
                                "domain_name": text, "price": price,
                                "source": "expireddomains_expiring",
                                "tld": text.split(".")[-1], "status": "expiring",
                                "categories": categories,
                                "estimated_value": estimated_value,
                                "dr": 0, "referring_domains": 0, "domain_age": 0,
                            })
            logger.info("Expireddomains.net expiring: %d domains", len(results))
    except Exception as e:
        logger.warning("Expireddomains.net expiring failed: %s", e)

    # Dropped domains
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
                            categories = _categorize_domain(text)
                            estimated_value = _estimate_value(text, categories)

                            results.append({
                                "domain_name": text, "price": 0,
                                "source": "expireddomains_dropped",
                                "tld": text.split(".")[-1], "status": "dropped",
                                "categories": categories,
                                "estimated_value": estimated_value,
                                "dr": 0, "referring_domains": 0, "domain_age": 0,
                            })
            logger.info("Expireddomains.net dropped: %d domains", len(results))
    except Exception as e:
        logger.warning("Expireddomains.net dropped failed: %s", e)

    return results


async def _scrape_snapnames_playwright() -> list[dict]:
    """Scrape SnapNames with Playwright."""
    logger = setup_logger("SnapNamesPlaywright")
    results: list[dict] = []

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            )
            page = await context.new_page()

            await page.goto("https://www.snapnames.com/", wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)

            text = await page.evaluate("() => document.body ? document.body.innerText : ''")

            # Extract domains from page
            found_domains = re.findall(
                r'\b([a-z0-9-]{2,63}\.(?:com|io|ai|co|net|org|dev|app))\b',
                text.lower()
            )

            # Extract prices
            prices = re.findall(r'\$[\d,]+(?:\.\d{2})?', text)

            seen = set()
            for i, domain in enumerate(found_domains):
                if domain in EXCLUDE or domain in seen:
                    continue
                if not DOMAIN_RE.match(domain):
                    continue
                seen.add(domain)

                price = 0
                if i < len(prices):
                    price_str = prices[i].replace("$", "").replace(",", "")
                    try:
                        price = float(price_str)
                    except ValueError:
                        pass

                categories = _categorize_domain(domain)
                estimated_value = _estimate_value(domain, categories)

                results.append({
                    "domain_name": domain,
                    "price": price,
                    "source": "snapnames",
                    "tld": domain.split(".")[-1],
                    "status": "expiring",
                    "categories": categories,
                    "estimated_value": estimated_value,
                    "dr": 0, "referring_domains": 0, "domain_age": 0,
                })

            await browser.close()

        logger.info("SnapNames Playwright: %d domains found", len(results))
    except Exception as e:
        logger.warning("SnapNames Playwright failed: %s", e)

    return results


async def _scrape_namejet_httpx(client: httpx.AsyncClient) -> list[dict]:
    """Scrape NameJet via HTTP."""
    logger = setup_logger("NameJetHTTPX")
    results: list[dict] = []

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

                            categories = _categorize_domain(text)
                            estimated_value = _estimate_value(text, categories)

                            results.append({
                                "domain_name": text, "price": price,
                                "source": "namejet", "tld": text.split(".")[-1],
                                "status": "expiring",
                                "categories": categories,
                                "estimated_value": estimated_value,
                                "dr": 0, "referring_domains": 0, "domain_age": 0,
                            })
            logger.info("NameJet: %d domains", len(results))
    except Exception as e:
        logger.warning("NameJet failed: %s", e)

    return results


async def _scrape_godaddy_playwright() -> list[dict]:
    """Scrape GoDaddy Auctions with Playwright."""
    logger = setup_logger("GoDaddyPlaywright")
    results: list[dict] = []

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            )
            page = await context.new_page()

            await page.goto("https://auctions.godaddy.com/trpSearchResults.aspx?t=22&k=&page=1", wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)

            text = await page.evaluate("() => document.body ? document.body.innerText : ''")

            found_domains = re.findall(
                r'\b([a-z0-9-]{2,63}\.(?:com|io|ai|co|net|org|dev|app))\b',
                text.lower()
            )

            prices = re.findall(r'\$[\d,]+(?:\.\d{2})?', text)

            seen = set()
            for i, domain in enumerate(found_domains):
                if domain in EXCLUDE or domain in seen:
                    continue
                if not DOMAIN_RE.match(domain):
                    continue
                seen.add(domain)

                price = 0
                if i < len(prices):
                    price_str = prices[i].replace("$", "").replace(",", "")
                    try:
                        price = float(price_str)
                    except ValueError:
                        pass

                categories = _categorize_domain(domain)
                estimated_value = _estimate_value(domain, categories)

                results.append({
                    "domain_name": domain,
                    "price": price,
                    "source": "godaddy_auctions",
                    "tld": domain.split(".")[-1],
                    "status": "auction",
                    "categories": categories,
                    "estimated_value": estimated_value,
                    "dr": 0, "referring_domains": 0, "domain_age": 0,
                })

            await browser.close()

        logger.info("GoDaddy Playwright: %d domains found", len(results))
    except Exception as e:
        logger.warning("GoDaddy Playwright failed: %s", e)

    return results


async def run() -> list[dict]:
    """Scrape free sources for expiring domains and categorize them."""
    logger = setup_logger("ExpiringDomainScout")

    # Run HTTPX and Playwright scrapers in parallel
    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"},
        follow_redirects=True, timeout=30.0,
    ) as client:
        results = await asyncio.gather(
            _scrape_expireddomains_httpx(client),
            _scrape_snapnames_playwright(),
            _scrape_namejet_httpx(client),
            _scrape_godaddy_playwright(),
            return_exceptions=True,
        )

    # Merge results
    all_domains: list[dict] = []
    seen: set[str] = set()
    for result in results:
        if isinstance(result, list):
            for d in result:
                name = d.get("domain_name", "")
                if name and name not in seen:
                    seen.add(name)
                    all_domains.append(d)

    # Log category distribution
    category_counts: dict[str, int] = {}
    for d in all_domains:
        for cat in d.get("categories", ["generic"]):
            category_counts[cat] = category_counts.get(cat, 0) + 1

    logger.info("Expiring scout found %d unique domains", len(all_domains))
    logger.info("Category distribution: %s", dict(sorted(category_counts.items(), key=lambda x: -x[1])[:10]))

    return all_domains
