"""Subagent 5: Analyzes domains for quality and estimated value."""

from __future__ import annotations

import asyncio
import re

import httpx

from src.utils import setup_logger

try:
    import whois as whois_lib
except ImportError:
    whois_lib = None


def _estimate_value(domain: str, seo_score: float, commercial_score: float) -> float:
    """Estimate domain value based on various factors."""
    name = domain.split(".")[0]
    tld = domain.split(".")[-1] if "." in domain else ""

    base_value = 100.0

    # TLD multiplier
    tld_mult = {
        "com": 1.5, "io": 1.3, "ai": 1.4, "co": 1.1,
        "net": 0.8, "org": 0.9, "dev": 1.0, "app": 1.0,
    }
    base_value *= tld_mult.get(tld, 0.7)

    # Length multiplier (shorter = more valuable)
    if len(name) <= 4:
        base_value *= 3.0
    elif len(name) <= 6:
        base_value *= 2.0
    elif len(name) <= 8:
        base_value *= 1.5
    elif len(name) <= 12:
        base_value *= 1.0
    else:
        base_value *= 0.7

    # No hyphens bonus
    if "-" not in name:
        base_value *= 1.3

    # SEO score bonus
    base_value += seo_score * 5

    # Commercial score bonus
    base_value += commercial_score * 3

    # Keyword value (common valuable keywords)
    high_value_keywords = [
        "ai", "tech", "cloud", "data", "pay", "buy", "shop", "sell",
        "market", "trade", "invest", "finance", "health", "crypto",
        "app", "web", "digital", "online", "smart", "auto",
    ]
    for kw in high_value_keywords:
        if kw in name.lower():
            base_value *= 1.2
            break

    return round(base_value, 2)


async def _check_http_status(client: httpx.AsyncClient, domain: str) -> dict:
    """Check if domain is live, parked, or dead."""
    for scheme in ["https", "http"]:
        try:
            resp = await client.get(f"{scheme}://{domain}", timeout=10.0, follow_redirects=True)
            html = resp.text.lower()

            # Check if parked
            parked_indicators = [
                "domain is for sale", "buy this domain", "this domain",
                "parked", "under construction", "coming soon",
                "domain expired", "domain available",
            ]
            is_parked = any(ind in html for ind in parked_indicators)

            # Check if live website
            is_live = resp.status_code == 200 and not is_parked

            return {
                "status_code": resp.status_code,
                "is_live": is_live,
                "is_parked": is_parked,
                "content_length": len(resp.text),
            }
        except Exception:
            continue

    return {"status_code": 0, "is_live": False, "is_parked": False, "content_length": 0}


async def _get_whois_age(domain: str) -> int:
    """Get domain age in days from WHOIS."""
    if whois_lib is None:
        return 0

    try:
        w = await asyncio.get_event_loop().run_in_executor(None, whois_lib.whois, domain)
        if w.creation_date:
            from datetime import datetime
            created = w.creation_date[0] if isinstance(w.creation_date, list) else w.creation_date
            if isinstance(created, datetime):
                return (datetime.now() - created).days
    except Exception:
        pass

    return 0


async def analyze_one(client: httpx.AsyncClient, domain: str) -> dict:
    """Analyze a single domain."""
    # Check HTTP status
    http_info = await _check_http_status(client, domain)

    # Get domain age
    age_days = await _get_whois_age(domain)

    # Calculate scores
    name = domain.split(".")[0]
    seo_score = 0.0
    if http_info.get("is_live"):
        seo_score = min(50.0, http_info.get("content_length", 0) / 10000)
    elif http_info.get("is_parked"):
        seo_score = 10.0

    # Commercial score (based on name characteristics)
    commercial_score = 50.0
    if len(name) <= 6:
        commercial_score += 20
    if "-" not in name:
        commercial_score += 10
    if any(kw in name.lower() for kw in ["buy", "shop", "pay", "sell", "trade", "market"]):
        commercial_score += 20

    # Estimate value
    estimated_value = _estimate_value(domain, seo_score, commercial_score)

    # Commission (15%)
    commission = round(estimated_value * 0.15, 2)

    return {
        "domain_name": domain,
        "http_status": http_info.get("status_code", 0),
        "is_live": http_info.get("is_live", False),
        "is_parked": http_info.get("is_parked", False),
        "domain_age_days": age_days,
        "seo_score": round(seo_score, 1),
        "commercial_score": round(commercial_score, 1),
        "estimated_value": estimated_value,
        "commission": commission,
    }


async def run(domains: list[dict]) -> list[dict]:
    """Analyze a list of domains and enrich with scores."""
    logger = setup_logger("DomainAnalyzer")
    domain_names = [d.get("domain_name", "") for d in domains if d.get("domain_name")]

    async with httpx.AsyncClient(
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        },
        follow_redirects=True,
        timeout=15.0,
    ) as client:
        semaphore = asyncio.Semaphore(10)
        results: list[dict] = []

        async def analyze(domain: str, original: dict):
            async with semaphore:
                analysis = await analyze_one(client, domain)
                # Merge original data with analysis
                merged = {**original, **analysis}
                results.append(merged)

        tasks = [analyze(d["domain_name"], d) for d in domains if d.get("domain_name")]
        await asyncio.gather(*tasks)

    # Sort by estimated value
    results.sort(key=lambda x: x.get("estimated_value", 0), reverse=True)

    logger.info("Analyzed %d domains, top value: $%.0f",
                len(results),
                results[0]["estimated_value"] if results else 0)
    return results
