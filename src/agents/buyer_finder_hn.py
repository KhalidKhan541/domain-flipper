"""Agent 5: Buyer Finder HN — finds people looking to buy domains and extracts what they want."""

from __future__ import annotations

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


async def _search_hn(client: httpx.AsyncClient, query: str) -> list[dict]:
    """Search Hacker News for people looking to buy domains."""
    results: list[dict] = []

    try:
        resp = await client.get(
            "https://hn.algolia.com/api/v1/search",
            params={"query": query, "tags": "story", "numericFilters": "created_at_i>1716000000"},
        )

        if resp.status_code != 200:
            return results

        data = resp.json()
        hits = data.get("hits", [])

        for hit in hits:
            title = hit.get("title", "")
            url = hit.get("url", "")
            author = hit.get("author", "")
            points = hit.get("points", 0)
            story_text = hit.get("story_text", "") or ""

            combined = (title + " " + story_text).lower()
            if not any(kw in combined for kw in ["buy", "looking", "want", "need", "purchase", "acquire", "domain"]):
                continue

            # Extract what kind of domain they want
            buyer_needs = _extract_buyer_needs(title, story_text)

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

            hn_url = f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"

            results.append({
                "author": author,
                "title": title,
                "text": story_text[:500],
                "url": hn_url,
                "original_url": url,
                "mentioned_domains": mentioned_domains[:5],
                "buyer_needs": buyer_needs,
                "suggested_domains": suggested_domains,
                "budget": budget,
                "points": points,
                "source": "hackernews",
            })

    except Exception:
        pass

    return results


async def run() -> dict:
    """Search HN for domain buyers and extract what they want."""
    logger = setup_logger("HNNBuyerFinder")
    buyer_leads: list[dict] = []

    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        follow_redirects=True, timeout=30.0,
    ) as client:
        # Search with multiple queries
        queries = [
            "looking to buy domain",
            "want to buy domain",
            "need domain name",
            "domain for sale",
            "looking for domain",
            "buy domain",
            "purchase domain",
            "acquire domain",
        ]

        for query in queries[:5]:
            results = await _search_hn(client, query)
            buyer_leads.extend(results)

    # Deduplicate buyers
    seen = set()
    unique_buyers: list[dict] = []
    for r in buyer_leads:
        if r["url"] not in seen:
            seen.add(r["url"])
            unique_buyers.append(r)

    logger.info("HN buyer finder: %d potential buyers", len(unique_buyers))
    return {"buyers": unique_buyers, "auctions": []}
