"""Agent 2: Marketplace Playwright — scrapes Flippa/Sedo/Afternic with real browser."""

from __future__ import annotations

import asyncio
import re

from playwright.async_api import async_playwright

from src.utils import setup_logger

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

DOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.(com|io|ai|co|net|org|dev|app)$")


async def _scrape_flippa(page) -> list[dict]:
    """Scrape Flippa domain listings."""
    logger = setup_logger("FlippaScraper")
    results: list[dict] = []

    try:
        await page.goto("https://flippa.com/search?filter%5Bcategory%5D=domains&sort=created_at.desc", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)

        # Try to get listing cards
        listings = await page.query_selector_all("[class*='listing'], [class*='card'], [class*='auction'], article, [data-testid]")
        logger.info("Flippa: found %d potential listing elements", len(listings))

        # Fallback: get all links that look like domain listings
        links = await page.query_selector_all("a[href*='/domains/'], a[href*='/listing/']")
        logger.info("Flippa: found %d listing links", len(links))

        content = await page.content()
        text = await page.evaluate("() => document.body ? document.body.innerText : ''")

        # Extract domains from page text
        found_domains = re.findall(
            r'\b([a-z0-9-]{2,63}\.(?:com|io|ai|co|net|org|dev|app))\b',
            text.lower()
        )

        # Extract prices
        prices = re.findall(r'\$[\d,]+(?:\.\d{2})?', text)

        # Try to pair domains with prices
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

            results.append({
                "domain_name": domain,
                "price": price,
                "source": "flippa",
                "tld": domain.split(".")[-1],
                "status": "for_sale",
                "for_sale": True,
                "dr": 0, "referring_domains": 0, "domain_age": 0,
            })

        logger.info("Flippa: %d domains found", len(results))
    except Exception as e:
        logger.warning("Flippa scrape failed: %s", e)

    return results


async def _scrape_sedo(page) -> list[dict]:
    """Scrape Sedo domain listings."""
    logger = setup_logger("SedoScraper")
    results: list[dict] = []

    try:
        await page.goto("https://sedo.com/search/?keyword=&offer_type=&minprice=50&maxprice=50000&tlds=", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)

        text = await page.evaluate("() => document.body ? document.body.innerText : ''")
        content = await page.content()

        # Extract domains
        found_domains = re.findall(
            r'\b([a-z0-9-]{2,63}\.(?:com|io|ai|co|net|org|dev|app))\b',
            text.lower()
        )

        # Extract prices (Sedo shows prices next to domains)
        prices = re.findall(r'(?:EUR|USD|GBP)?\s*[\$€£]?[\d,]+(?:\.\d{2})?', text)

        seen = set()
        for i, domain in enumerate(found_domains):
            if domain in EXCLUDE or domain in seen:
                continue
            if not DOMAIN_RE.match(domain):
                continue
            seen.add(domain)

            price = 0
            if i < len(prices):
                price_str = re.sub(r'[^\d.]', '', prices[i])
                try:
                    price = float(price_str)
                except ValueError:
                    pass

            results.append({
                "domain_name": domain,
                "price": price,
                "source": "sedo",
                "tld": domain.split(".")[-1],
                "status": "for_sale",
                "for_sale": True,
                "dr": 0, "referring_domains": 0, "domain_age": 0,
            })

        logger.info("Sedo: %d domains found", len(results))
    except Exception as e:
        logger.warning("Sedo scrape failed: %s", e)

    return results


async def _scrape_afternic(page) -> list[dict]:
    """Scrape Afternic domain listings."""
    logger = setup_logger("AfternicScraper")
    results: list[dict] = []

    try:
        await page.goto("https://www.afternic.com/search?k=&flt=&pmin=50&pmax=50000", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)

        text = await page.evaluate("() => document.body ? document.body.innerText : ''")

        # Extract domains
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

            results.append({
                "domain_name": domain,
                "price": price,
                "source": "afternic",
                "tld": domain.split(".")[-1],
                "status": "for_sale",
                "for_sale": True,
                "dr": 0, "referring_domains": 0, "domain_age": 0,
            })

        logger.info("Afternic: %d domains found", len(results))
    except Exception as e:
        logger.warning("Afternic scrape failed: %s", e)

    return results


async def _scrape_dan(page) -> list[dict]:
    """Scrape Dan.com domain listings (uses MakeAnOffer)."""
    logger = setup_logger("DanScraper")
    results: list[dict] = []

    try:
        await page.goto("https://dan.com/marketplace/domains?sort=price_asc&min_price=50&max_price=50000", wait_until="networkidle", timeout=30000)
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

            results.append({
                "domain_name": domain,
                "price": price,
                "source": "dan.com",
                "tld": domain.split(".")[-1],
                "status": "for_sale",
                "for_sale": True,
                "dr": 0, "referring_domains": 0, "domain_age": 0,
            })

        logger.info("Dan.com: %d domains found", len(results))
    except Exception as e:
        logger.warning("Dan.com scrape failed: %s", e)

    return results


async def _scrape_godaddy_auctions(page) -> list[dict]:
    """Scrape GoDaddy Auctions for listing domains."""
    logger = setup_logger("GoDaddyAuctionScraper")
    results: list[dict] = []

    try:
        await page.goto("https://auctions.godaddy.com/trpSearchResults.aspx?t=22&k=&page=1", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)

        text = await page.evaluate("() => document.body ? document.body.innerText : ''")
        content = await page.content()

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

            results.append({
                "domain_name": domain,
                "price": price,
                "source": "godaddy_auctions",
                "tld": domain.split(".")[-1],
                "status": "auction",
                "for_sale": True,
                "dr": 0, "referring_domains": 0, "domain_age": 0,
            })

        logger.info("GoDaddy Auctions: %d domains found", len(results))
    except Exception as e:
        logger.warning("GoDaddy Auctions scrape failed: %s", e)

    return results


async def run() -> list[dict]:
    """Run all marketplace scrapers in parallel with Playwright."""
    logger = setup_logger("MarketplacePlaywright")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        )
        page = await context.new_page()

        # Run all scrapers in parallel
        results = await asyncio.gather(
            _scrape_flippa(page),
            _scrape_sedo(page),
            _scrape_afternic(page),
            _scrape_dan(page),
            _scrape_godaddy_auctions(page),
            return_exceptions=True,
        )

        await browser.close()

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

    logger.info("Marketplace playwright found %d unique domains", len(all_domains))
    return all_domains
