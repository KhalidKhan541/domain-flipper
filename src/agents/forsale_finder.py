"""Agent 3: For-Sale Page Finder — checks expiring domains for 'for sale' pages."""

from __future__ import annotations

import asyncio
import re

from playwright.async_api import async_playwright

from src.utils import setup_logger

SALE_KEYWORDS = re.compile(
    r"(for\s+sale|buy\s+now|make\s+offer|this\s+domain|"
    r"domain\s+is?\s+for|purchase|acquire|asking\s+price|"
    r"premium\s+domain|parked|domain\s+broker|listed\s+for|"
    r"buynow|buyitnow|price|offer)",
    re.IGNORECASE,
)


async def _check_domain(page, domain: str) -> dict | None:
    """Check if a domain has a 'for sale' page."""
    for scheme in ["https", "http"]:
        try:
            url = f"{scheme}://{domain}"
            await page.goto(url, wait_until="domcontentloaded", timeout=10000)
            content = await page.content()
            text = await page.evaluate("() => document.body ? document.body.innerText : ''")

            if not text or len(text) < 20:
                continue

            if not SALE_KEYWORDS.search(text):
                continue

            # Extract emails
            emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", content)
            emails = [e.lower() for e in emails if not e.endswith((".png", ".jpg", ".gif", ".svg", ".css", ".js"))]

            # Extract price
            price = 0.0
            price_match = re.search(r"\$\s*([\d,]+(?:\.\d{2})?)", text)
            if price_match:
                price = float(price_match.group(1).replace(",", ""))

            # Check platform
            platform = ""
            content_lower = content.lower()
            if "dan.com" in content_lower:
                platform = "dan.com"
            elif "afternic" in content_lower:
                platform = "afternic"
            elif "sedo" in content_lower:
                platform = "sedo"
            elif "hugedomains" in content_lower:
                platform = "hugedomains"
            elif "undeveloped" in content_lower:
                platform = "undeveloped"

            return {
                "domain_name": domain,
                "price": price,
                "source": "forsale_finder",
                "tld": domain.split(".")[-1],
                "seller_emails": emails[:3],
                "platform": platform,
                "status": "for_sale",
                "for_sale": True,
                "dr": 0, "referring_domains": 0, "domain_age": 0,
            }

        except Exception:
            continue

    return None


async def run(candidate_domains: list[str] | None = None) -> list[dict]:
    """Check candidate domains for 'for sale' pages using Playwright."""
    logger = setup_logger("ForSaleFinder")

    if not candidate_domains:
        # Default: check common short .com domains that might be parked/for-sale
        words = [
            "ai", "app", "cloud", "data", "dev", "flow", "go", "hub",
            "lab", "link", "map", "net", "pay", "pro", "run", "shop",
            "site", "tech", "tool", "web", "work", "zone", "buy", "sell",
            "trade", "market", "store", "deal", "health", "finance",
            "crypto", "nft", "defi", "web3", "saas", "api", "bot",
            "chat", "docs", "email", "farm", "game", "home", "jobs",
            "kids", "life", "love", "mail", "news", "pics", "quiz",
            "rent", "sale", "tour", "vote", "wall", "yoga", "zen",
        ]
        candidate_domains = []
        for w in words:
            for tld in ["com", "io", "ai", "co"]:
                candidate_domains.append(f"{w}.{tld}")

    logger.info("Checking %d domains for 'for sale' pages", len(candidate_domains))

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )
        page = await context.new_page()

        semaphore = asyncio.Semaphore(5)
        results: list[dict] = []

        async def check_one(domain: str):
            async with semaphore:
                result = await _check_domain(page, domain)
                if result:
                    results.append(result)

        tasks = [check_one(d) for d in candidate_domains[:80]]
        await asyncio.gather(*tasks)
        await browser.close()

    logger.info("For-sale finder found %d domains with sale pages", len(results))
    return results
