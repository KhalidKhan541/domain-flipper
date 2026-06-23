"""Agent 4: Buyer Finder Reddit — finds people looking to buy domains and extracts what they want."""

from __future__ import annotations

import asyncio
import re

import httpx

from src.utils import setup_logger

# Categories of domains buyers look for
DOMAIN_CATEGORIES = {
    "ai": ["ai", "artificial intelligence", "machine learning", "ml", "deep learning", "neural", "chatbot", "gpt", "llm"],
    "crypto": ["crypto", "bitcoin", "blockchain", "defi", "nft", "web3", "token", "coin", "wallet", "exchange"],
    "health": ["health", "medical", "doctor", "clinic", "hospital", "wellness", "fitness", "nutrition", "pharma", "biotech"],
    "finance": ["finance", "fintech", "banking", "payment", "invest", "trading", "stock", "insurance", "loan", "credit"],
    "saas": ["saas", "software", "app", "platform", "tool", "dashboard", "analytics", "crm", "erp", "automation"],
    "ecommerce": ["shop", "store", "ecommerce", "marketplace", "buy", "sell", "retail", "commerce", "cart", "checkout"],
    "education": ["learn", "education", "course", "school", "university", "training", "tutor", "academy", "study"],
    "realestate": ["real estate", "property", "rent", "lease", "mortgage", "home", "house", "apartment", "condo"],
    "food": ["food", "restaurant", "delivery", "recipe", "cook", "meal", "pizza", "burger", "cafe", "coffee"],
    "travel": ["travel", "hotel", "flight", "tourism", "vacation", "booking", "airline", "rental", "adventure"],
    "gaming": ["game", "gaming", "esport", "player", "rpg", "mmo", "stream", "twitch", "discord"],
    "social": ["social", "community", "forum", "chat", "messaging", "network", "dating", "relationship"],
    "tech": ["tech", "cloud", "server", "api", "devops", "code", "developer", "programming", "data"],
    "green": ["eco", "green", "solar", "energy", "sustainable", "climate", "environment", "renewable"],
    "media": ["media", "news", "blog", "podcast", "video", "streaming", "content", "digital", "press"],
}

REAL_BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"


def _extract_buyer_needs(title: str, text: str) -> list[str]:
    """Extract what kind of domain the buyer is looking for."""
    combined = (title + " " + text).lower()
    needs = []

    for category, keywords in DOMAIN_CATEGORIES.items():
        for kw in keywords:
            if kw in combined:
                needs.append(category)
                break

    # Extract specific TLD preferences
    tld_matches = re.findall(r'\b(\w+)\s*(?:domain|\.com|\.io|\.ai|\.co|\.net|\.org)\b', combined)
    for tld in tld_matches:
        if tld in DOMAIN_CATEGORIES:
            needs.append(tld)

    # Extract industry mentions
    industry_patterns = [
        r'(?:looking for|need|want)\s+(?:a\s+)?(\w+)\s*(?:domain|site|website)',
        r'(?:for|in)\s+(?:the\s+)?(\w+)\s+(?:industry|space|sector|field|niche)',
        r'(?:my|our)\s+(\w+)\s+(?:startup|project|company|business|app)',
    ]
    for pattern in industry_patterns:
        matches = re.findall(pattern, combined)
        for match in matches:
            for category, keywords in DOMAIN_CATEGORIES.items():
                if match in keywords:
                    needs.append(category)
                    break

    return list(set(needs))


def _generate_domain_suggestions(needs: list[str]) -> list[str]:
    """Generate domain name suggestions based on buyer needs."""
    suggestions = []

    for need in needs:
        if need in DOMAIN_CATEGORIES:
            # Generate some suggestions
            for kw in DOMAIN_CATEGORIES[need][:3]:
                suggestions.append(f"{kw}.com")
                suggestions.append(f"{kw}.io")
                suggestions.append(f"{kw}.ai")

    return suggestions[:5]


async def _search_subreddit(client: httpx.AsyncClient, subreddit: str, query: str) -> list[dict]:
    """Search a specific subreddit for buyer intent posts."""
    results: list[dict] = []

    try:
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
            buyer_keywords = [
                "looking to buy", "want to buy", "need domain", "looking for domain",
                "buy domain", "purchase domain", "acquire domain", "interested in buying",
                "budget", "how much", "willing to pay", "anyone selling",
            ]
            if not any(kw in combined for kw in buyer_keywords):
                continue

            # Extract what kind of domain they want
            buyer_needs = _extract_buyer_needs(title, selftext)

            # Generate suggestions based on needs
            suggested_domains = _generate_domain_suggestions(buyer_needs)

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
                "buyer_needs": buyer_needs,
                "suggested_domains": suggested_domains,
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

            # Extract what kind of domain they want
            buyer_needs = _extract_buyer_needs(title, selftext)

            # Generate suggestions based on needs
            suggested_domains = _generate_domain_suggestions(buyer_needs)

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
                "buyer_needs": buyer_needs,
                "suggested_domains": suggested_domains,
                "budget": budget,
                "source": "reddit",
            })

    except Exception:
        pass

    return results


async def _scrape_subreddit_new(client: httpx.AsyncClient, subreddit: str) -> list[dict]:
    """Scrape subreddit /new page for recent posts."""
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
            domain_keywords = [
                "domain", "buy", "sell", "sale", "website", "url",
                "looking for", "need", "want", "purchase", "acquire",
            ]
            if not any(kw in combined for kw in domain_keywords):
                continue

            # Extract what kind of domain they want
            buyer_needs = _extract_buyer_needs(title, selftext)

            # Generate suggestions based on needs
            suggested_domains = _generate_domain_suggestions(buyer_needs)

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
                "buyer_needs": buyer_needs,
                "suggested_domains": suggested_domains,
                "budget": budget,
                "source": "reddit",
            })

    except Exception:
        pass

    return results


async def run() -> list[dict]:
    """Search Reddit for people looking to buy domains and extract what they want."""
    logger = setup_logger("RedditBuyerFinder")
    all_results: list[dict] = []

    async with httpx.AsyncClient(
        follow_redirects=True, timeout=30.0,
    ) as client:
        # Strategy 1: Subreddit-specific search
        subreddit_tasks = []
        subreddit_queries = [
            ("Domains", "looking to buy"),
            ("Domains", "want to buy"),
            ("Domains", "for sale"),
            ("domainnames", "looking for domain"),
            ("domainnames", "want domain"),
            ("Entrepreneur", "need domain name"),
            ("Entrepreneur", "looking for domain"),
            ("startups", "need domain"),
            ("startups", "looking for domain name"),
            ("SaaS", "need domain name"),
            ("SaaS", "looking for domain"),
        ]
        for subreddit, query in subreddit_queries[:8]:
            subreddit_tasks.append(_search_subreddit(client, subreddit, query))

        subreddit_results = await asyncio.gather(*subreddit_tasks, return_exceptions=True)
        for result in subreddit_results:
            if isinstance(result, list):
                all_results.extend(result)

        logger.info("Subreddit search: %d results", len(all_results))

        # Strategy 2: Global search
        global_tasks = []
        global_queries = [
            "looking to buy domain",
            "want to buy domain",
            "need domain name",
            "buying domains",
            "domain for sale",
        ]
        for query in global_queries[:3]:
            global_tasks.append(_search_global(client, query))

        global_results = await asyncio.gather(*global_tasks, return_exceptions=True)
        for result in global_results:
            if isinstance(result, list):
                all_results.extend(result)

        logger.info("Global search: %d results", len(all_results))

        # Strategy 3: Scrape /new pages
        new_tasks = []
        for sub in ["Domains", "domainnames", "Entrepreneur", "startups"]:
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
