"""Agent 4: Buyer Finder Reddit — finds people looking to buy domains on Reddit."""

from __future__ import annotations

import asyncio
import re

import httpx
from bs4 import BeautifulSoup

from src.utils import setup_logger

# Subreddit-specific search queries — people looking to buy domains
SUBREDDIT_QUERIES = [
    ("Domains", "looking to buy"),
    ("Domains", "want to buy"),
    ("Domains", "for sale"),
    ("Domains", "selling my domain"),
    ("domainnames", "looking for domain"),
    ("domainnames", "want domain"),
    ("Domaining", "buying domains"),
    ("Domaining", "domain for sale"),
    ("Entrepreneur", "need domain name"),
    ("Entrepreneur", "looking for domain"),
    ("startups", "need domain"),
    ("startups", "looking for domain name"),
    ("SaaS", "need domain name"),
    ("SaaS", "looking for domain"),
    ("smallbusiness", "need website domain"),
    ("webdev", "domain name help"),
    ("juststart", "domain name"),
    ("SideProject", "need domain"),
]

# Global search queries
GLOBAL_QUERIES = [
    "looking to buy domain",
    "want to buy domain",
    "need domain name",
    "buying domains",
    "domain for sale",
    "looking for domain",
    "buy domain",
    "purchase domain",
    "acquire domain",
    "budget for domain",
    "how much for domain",
    "selling my domain",
    "domain appraisal",
    "is this domain worth",
    "domain name available",
    "looking to purchase",
]

REAL_BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"


async def _search_subreddit(client: httpx.AsyncClient, subreddit: str, query: str) -> list[dict]:
    """Search a specific subreddit for buyer intent posts."""
    results: list[dict] = []

    try:
        # Search within subreddit using subreddit-specific URL
        url = f"https://www.reddit.com/r/{subreddit}/search.json"
        resp = await client.get(
            url,
            params={
                "q": query,
                "sort": "new",
                "t": "month",
                "limit": 10,
                "restrict_sr": "on",
            },
            headers={
                "User-Agent": REAL_BROWSER_UA,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": f"https://www.reddit.com/r/{subreddit}/",
            },
        )

        if resp.status_code != 200:
            return results

        data = resp.json()
        posts = data.get("data", {}).get("children", [])

        for post in posts:
            p = post.get("data", {})
            title = p.get("title", "")
            selftext = p.get("selftext", "")
            author = p.get("author", "")
            subreddit_name = p.get("subreddit", "")
            permalink = f"https://reddit.com{p.get('permalink', '')}"

            combined = (title + " " + selftext).lower()

            # Check if this is someone looking to buy
            buyer_keywords = [
                "looking to buy", "want to buy", "need domain", "looking for domain",
                "buy domain", "purchase domain", "acquire domain", "interested in buying",
                "budget", "how much", "willing to pay", "anyone selling",
                "want to purchase", "looking to acquire", "searching for",
            ]
            if not any(kw in combined for kw in buyer_keywords):
                continue

            # Extract any domain names mentioned
            mentioned_domains = re.findall(
                r'\b([a-z0-9-]{2,63}\.(?:com|io|ai|co|net|org|dev|app))\b',
                combined,
            )

            # Extract budget if mentioned
            budget = 0
            budget_match = re.search(r'\$\s*([\d,]+)', combined)
            if budget_match:
                budget = float(budget_match.group(1).replace(",", ""))

            results.append({
                "author": author,
                "subreddit": subreddit_name,
                "title": title,
                "text": selftext[:500],
                "url": permalink,
                "mentioned_domains": mentioned_domains[:5],
                "budget": budget,
                "source": "reddit",
            })

    except Exception:
        pass

    return results


async def _search_global(client: httpx.AsyncClient, query: str) -> list[dict]:
    """Search Reddit globally for buyer intent posts."""
    results: list[dict] = []

    try:
        resp = await client.get(
            "https://www.reddit.com/search.json",
            params={"q": query, "sort": "new", "t": "month", "limit": 25},
            headers={
                "User-Agent": REAL_BROWSER_UA,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.reddit.com/",
            },
        )

        if resp.status_code != 200:
            return results

        data = resp.json()
        posts = data.get("data", {}).get("children", [])

        for post in posts:
            p = post.get("data", {})
            title = p.get("title", "")
            selftext = p.get("selftext", "")
            author = p.get("author", "")
            subreddit_name = p.get("subreddit", "")
            permalink = f"https://reddit.com{p.get('permalink', '')}"

            combined = (title + " " + selftext).lower()

            buyer_keywords = [
                "looking to buy", "want to buy", "need domain", "looking for domain",
                "buy domain", "purchase domain", "acquire domain", "interested in buying",
                "budget", "how much", "willing to pay", "anyone selling",
            ]
            if not any(kw in combined for kw in buyer_keywords):
                continue

            mentioned_domains = re.findall(
                r'\b([a-z0-9-]{2,63}\.(?:com|io|ai|co|net|org|dev|app))\b',
                combined,
            )

            budget = 0
            budget_match = re.search(r'\$\s*([\d,]+)', combined)
            if budget_match:
                budget = float(budget_match.group(1).replace(",", ""))

            results.append({
                "author": author,
                "subreddit": subreddit_name,
                "title": title,
                "text": selftext[:500],
                "url": permalink,
                "mentioned_domains": mentioned_domains[:5],
                "budget": budget,
                "source": "reddit",
            })

    except Exception:
        pass

    return results


async def _scrape_subreddit_new(client: httpx.AsyncClient, subreddit: str) -> list[dict]:
    """Scrape subreddit /new page for recent posts (JSON endpoint)."""
    results: list[dict] = []

    try:
        resp = await client.get(
            f"https://www.reddit.com/r/{subreddit}/new.json",
            params={"limit": 25},
            headers={
                "User-Agent": REAL_BROWSER_UA,
                "Accept": "application/json",
                "Referer": f"https://www.reddit.com/r/{subreddit}/new",
            },
        )

        if resp.status_code != 200:
            return results

        data = resp.json()
        posts = data.get("data", {}).get("children", [])

        for post in posts:
            p = post.get("data", {})
            title = p.get("title", "")
            selftext = p.get("selftext", "")
            author = p.get("author", "")
            permalink = f"https://reddit.com{p.get('permalink', '')}"

            combined = (title + " " + selftext).lower()

            # Check for domain-related keywords
            domain_keywords = [
                "domain", "buy", "sell", "sale", "website", "url",
                "looking for", "need", "want", "purchase", "acquire",
            ]
            if not any(kw in combined for kw in domain_keywords):
                continue

            mentioned_domains = re.findall(
                r'\b([a-z0-9-]{2,63}\.(?:com|io|ai|co|net|org|dev|app))\b',
                combined,
            )

            budget = 0
            budget_match = re.search(r'\$\s*([\d,]+)', combined)
            if budget_match:
                budget = float(budget_match.group(1).replace(",", ""))

            results.append({
                "author": author,
                "subreddit": subreddit,
                "title": title,
                "text": selftext[:500],
                "url": permalink,
                "mentioned_domains": mentioned_domains[:5],
                "budget": budget,
                "source": "reddit",
            })

    except Exception:
        pass

    return results


async def run() -> list[dict]:
    """Search Reddit for people looking to buy domains."""
    logger = setup_logger("RedditBuyerFinder")
    all_results: list[dict] = []

    async with httpx.AsyncClient(
        follow_redirects=True, timeout=30.0,
    ) as client:
        # Strategy 1: Subreddit-specific search (most targeted)
        subreddit_tasks = []
        for subreddit, query in SUBREDDIT_QUERIES[:12]:
            subreddit_tasks.append(_search_subreddit(client, subreddit, query))

        subreddit_results = await asyncio.gather(*subreddit_tasks, return_exceptions=True)
        for result in subreddit_results:
            if isinstance(result, list):
                all_results.extend(result)

        logger.info("Subreddit search: %d results", len(all_results))

        # Strategy 2: Global search with top queries
        global_tasks = []
        for query in GLOBAL_QUERIES[:8]:
            global_tasks.append(_search_global(client, query))

        global_results = await asyncio.gather(*global_tasks, return_exceptions=True)
        for result in global_results:
            if isinstance(result, list):
                all_results.extend(result)

        logger.info("Global search: %d results", len(all_results))

        # Strategy 3: Scrape /new pages of key subreddits
        new_tasks = []
        for sub in ["Domains", "domainnames", "Entrepreneur", "startups", "SaaS"]:
            new_tasks.append(_scrape_subreddit_new(client, sub))

        new_results = await asyncio.gather(*new_tasks, return_exceptions=True)
        for result in new_results:
            if isinstance(result, list):
                all_results.extend(result)

        logger.info("Subreddit /new scrape: %d results", len(all_results))

    # Deduplicate by URL
    seen = set()
    unique: list[dict] = []
    for r in all_results:
        url = r.get("url", "")
        if url and url not in seen:
            seen.add(url)
            unique.append(r)

    logger.info("Reddit buyer finder: %d unique potential buyers found", len(unique))
    return unique
