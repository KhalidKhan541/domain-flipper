from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BuyerDiscovery")

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
LEADS_FILE = DATA_DIR / "buyer_leads.json"

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

NICHES = ["ai", "saas", "ecommerce", "finance", "health", "education", "realestate", "marketing", "crypto"]

HIGH_INTENT_PHRASES = [
    "buying", "wants to buy", "looking for", "need a domain", "need a website",
    "want a domain", "want to buy", "looking to buy", "searching for a domain",
]
MEDIUM_INTENT_PHRASES = [
    "domain", "website", "dot com", "startup", "online store", "ecommerce",
    "side project", "saas", "web app", "landing page",
]


async def search_reddit(client: httpx.AsyncClient) -> list[dict]:
    query = '(buying OR "looking for" OR "want to buy" OR "need a" OR "looking to buy") (domain OR website)'
    try:
        resp = await client.get(
            "https://www.reddit.com/search.json",
            params={"q": query, "sort": "new", "limit": 25, "t": "week", "restrict_sr": False},
            headers={"User-Agent": "DomainFlipper/1.0"},
            timeout=15,
        )
        if resp.status_code != 200:
            logger.warning("Reddit returned %d", resp.status_code)
            return []

        results = []
        for child in resp.json().get("data", {}).get("children", []):
            p = child.get("data", {})
            author = p.get("author", "")
            if not author or author == "[deleted]":
                continue
            text = ((p.get("title") or "") + " " + (p.get("selftext") or "")).lower()
            score, niche = score_intent(text)
            results.append({
                "source": "reddit",
                "username": author,
                "title": (p.get("title") or "")[:200],
                "url": "https://reddit.com" + (p.get("permalink") or ""),
                "score": score,
                "niche": niche,
                "created": datetime.now(timezone.utc).isoformat(),
            })
        logger.info("Reddit: %d results", len(results))
        return results
    except Exception as e:
        logger.error("Reddit search failed: %s", e)
        return []


async def search_hn(client: httpx.AsyncClient) -> list[dict]:
    try:
        resp = await client.get(
            "https://hn.algolia.com/api/v1/search_by_date",
            params={"query": "buying domain OR looking for domain OR need domain", "tags": "story", "hitsPerPage": 15},
            timeout=15,
        )
        if resp.status_code != 200:
            return []

        results = []
        for h in resp.json().get("hits", []):
            author = h.get("author", "")
            if not author:
                continue
            text = ((h.get("title") or "") + " " + (h.get("comment_text") or "")).lower()
            score, niche = score_intent(text)
            score += min((h.get("points") or 0), 20)
            results.append({
                "source": "hackernews",
                "username": author,
                "title": (h.get("title") or "")[:200],
                "url": h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID', '')}",
                "score": min(score, 100),
                "niche": niche,
                "created": h.get("created_at", ""),
            })
        logger.info("HN: %d results", len(results))
        return results
    except Exception as e:
        logger.error("HN search failed: %s", e)
        return []


def score_intent(text: str) -> tuple[int, str]:
    score = 0
    for phrase in HIGH_INTENT_PHRASES:
        if phrase in text:
            score += 30
            break
    for phrase in MEDIUM_INTENT_PHRASES:
        if phrase in text:
            score += 15
            break
    niche = ""
    for n in NICHES:
        if n in text:
            niche = n
            break
    return min(score, 100), niche


def load_existing() -> list[dict]:
    if LEADS_FILE.exists():
        try:
            return json.loads(LEADS_FILE.read_text())
        except Exception:
            return []
    return []


def save_leads(all_leads: list[dict]) -> None:
    all_leads.sort(key=lambda x: x.get("score", 0), reverse=True)
    LEADS_FILE.write_text(json.dumps(all_leads[:100], indent=2))
    logger.info("Saved %d leads to %s", min(len(all_leads), 100), LEADS_FILE)


async def send_discord_alert(lead: dict) -> bool:
    if not DISCORD_WEBHOOK_URL:
        return False

    embed = {
        "title": f"Potential Buyer Found on {lead['source']}",
        "color": 5814783,
        "url": lead.get("url", ""),
        "fields": [
            {"name": "Username", "value": lead["username"], "inline": True},
            {"name": "Intent Score", "value": f"{lead['score']}/100", "inline": True},
            {"name": "Niche", "value": lead.get("niche") or "Unknown", "inline": True},
            {"name": "Title", "value": lead.get("title", "")[:200], "inline": False},
        ],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    payload = {"username": "Domain Broker", "embeds": [embed]}

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.post(DISCORD_WEBHOOK_URL, json=payload)
            return resp.status_code < 400
        except Exception as e:
            logger.error("Discord send failed: %s", e)
            return False


async def run() -> list[dict]:
    logger.info("=" * 50)
    logger.info("Buyer Discovery Run at %s", datetime.now(timezone.utc).isoformat())
    logger.info("=" * 50)

    async with httpx.AsyncClient() as client:
        reddit, hn = await asyncio.gather(search_reddit(client), search_hn(client))

    all_results = reddit + hn
    all_results.sort(key=lambda x: x.get("score", 0), reverse=True)

    existing = load_existing()
    seen_urls = {r.get("url", "") for r in existing}
    new_leads = [r for r in all_results if r.get("url", "") not in seen_urls and r.get("score", 0) >= 30]

    if new_leads:
        logger.info("Found %d new high-intent leads!", len(new_leads))
        for lead in new_leads[:5]:
            ok = await send_discord_alert(lead)
            logger.info("Discord alert for %s: %s", lead["username"], "sent" if ok else "failed")
    else:
        logger.info("No new high-intent leads found")

    all_leads = existing + all_results
    save_leads(all_leads)

    logger.info("Run complete: %d total leads, %d new", len(all_leads), len(new_leads))
    return all_results


if __name__ == "__main__":
    asyncio.run(run())
