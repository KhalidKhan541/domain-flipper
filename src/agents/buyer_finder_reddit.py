"""Agent 4: Buyer Finder Reddit — finds people looking to buy domains on Reddit."""

from __future__ import annotations

import re

import httpx

from src.utils import setup_logger

# Search queries for people looking to buy domains
BUYER_QUERIES = [
    "looking to buy domain",
    "want to buy domain",
    "need domain name",
    "buying domains",
    "domain for sale",
    "looking for domain",
    "want domain name",
    "buy domain",
    "purchase domain",
    "acquire domain",
    "domain name available",
    "looking to purchase",
    "interested in buying",
    "willing to buy",
    "budget for domain",
    "how much for domain",
]

SUBREDDITS = [
    "Domains",
    "domainnames",
    "Domaining",
    "flippa",
    "juststart",
    "Entrepreneur",
    "smallbusiness",
    "startups",
    "SaaS",
    "webdev",
]


async def _search_reddit(client: httpx.AsyncClient, query: str) -> list[dict]:
    """Search Reddit for posts about buying domains."""
    results: list[dict] = []

    try:
        # Use Reddit JSON API
        resp = await client.get(
            "https://www.reddit.com/search.json",
            params={"q": query, "sort": "new", "t": "month", "limit": 25},
            headers={"User-Agent": "DomainBroker/1.0"},
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
            subreddit = p.get("subreddit", "")
            url = p.get("url", "")
            permalink = f"https://reddit.com{p.get('permalink', '')}"

            # Check if this is someone looking to buy
            combined = (title + " " + selftext).lower()
            if not any(kw in combined for kw in ["buy", "looking for", "want", "need", "purchase", "acquire"]):
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
        headers={"User-Agent": "DomainBroker/1.0"},
        follow_redirects=True, timeout=30.0,
    ) as client:
        # Search with multiple queries
        for query in BUYER_QUERIES[:5]:  # Limit to 5 queries
            results = await _search_reddit(client, query)
            all_results.extend(results)

    # Deduplicate by URL
    seen = set()
    unique: list[dict] = []
    for r in all_results:
        if r["url"] not in seen:
            seen.add(r["url"])
            unique.append(r)

    logger.info("Reddit buyer finder: %d potential buyers found", len(unique))
    return unique
