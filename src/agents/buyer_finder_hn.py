"""Agent 5: Buyer Finder HN + Twitter — finds people looking to buy domains."""

from __future__ import annotations

import re

import httpx

from src.utils import setup_logger

BUYER_QUERIES = [
    "looking to buy domain",
    "want to buy domain",
    "need domain name",
    "buying domains",
    "looking for domain",
    "domain for sale",
    "purchase domain",
    "acquire domain",
    "domain name available",
    "how much is domain worth",
]


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
            created_at = hit.get("created_at", "")

            combined = (title + " " + (hit.get("story_text", "") or "")).lower()
            if not any(kw in combined for kw in ["buy", "looking", "want", "need", "purchase", "acquire", "domain"]):
                continue

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
                "text": (hit.get("story_text", "") or "")[:500],
                "url": hn_url,
                "original_url": url,
                "mentioned_domains": mentioned_domains[:5],
                "budget": budget,
                "points": points,
                "source": "hackernews",
            })

    except Exception:
        pass

    return results


async def _search_godaddy_auctions(client: httpx.AsyncClient) -> list[dict]:
    """Search GoDaddy Auctions for expiring domains."""
    results: list[dict] = []

    try:
        resp = await client.get(
            "https://auctions.godaddy.com/trpSearchResults.aspx",
            params={"t": "22", "sp": "1"},
        )

        if resp.status_code != 200:
            return results

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")

        DOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.(com|io|ai|co|net|org|dev|app)$")

        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= 3:
                domain_cell = cells[0]
                link = domain_cell.find("a")
                if link:
                    text = link.get_text(strip=True).lower()
                    if DOMAIN_RE.match(text):
                        price_text = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                        match = re.search(r"\$?([\d,]+)", price_text)
                        price = float(match.group(1).replace(",", "")) if match else 0

                        results.append({
                            "domain_name": text,
                            "price": price,
                            "source": "godaddy_auctions",
                            "tld": text.split(".")[-1],
                            "status": "auction",
                            "dr": 0, "referring_domains": 0, "domain_age": 0,
                        })

    except Exception:
        pass

    return results


async def run() -> list[dict]:
    """Search HN + GoDaddy for domain buyers/auctions."""
    logger = setup_logger("HNTwitterBuyerFinder")
    buyer_leads: list[dict] = []
    auction_domains: list[dict] = []

    async with httpx.AsyncClient(
        headers={"User-Agent": "DomainBroker/1.0"},
        follow_redirects=True, timeout=30.0,
    ) as client:
        # Search HN
        for query in BUYER_QUERIES[:3]:
            results = await _search_hn(client, query)
            buyer_leads.extend(results)

        # Search GoDaddy Auctions
        auctions = await _search_godaddy_auctions(client)
        auction_domains.extend(auctions)

    # Deduplicate buyers
    seen = set()
    unique_buyers: list[dict] = []
    for r in buyer_leads:
        if r["url"] not in seen:
            seen.add(r["url"])
            unique_buyers.append(r)

    # Deduplicate auctions
    seen_domains = set()
    unique_auctions: list[dict] = []
    for d in auction_domains:
        if d["domain_name"] not in seen_domains:
            seen_domains.add(d["domain_name"])
            unique_auctions.append(d)

    logger.info("HN buyer finder: %d potential buyers", len(unique_buyers))
    logger.info("GoDaddy auctions: %d domains", len(unique_auctions))

    return {"buyers": unique_buyers, "auctions": unique_auctions}
