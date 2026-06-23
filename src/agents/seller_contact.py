"""Agent 6: Seller Contact Extractor — finds owner emails via WHOIS + contact pages."""

from __future__ import annotations

import asyncio
import re

import httpx

from src.utils import setup_logger

try:
    import whois as whois_lib
except ImportError:
    whois_lib = None

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


async def _whois_lookup(domain: str) -> dict:
    """WHOIS lookup for domain owner info."""
    result = {
        "registrar": "", "registrant_name": "", "registrant_email": "",
        "registrant_org": "", "creation_date": "", "expiration_date": "",
    }

    if whois_lib is None:
        return result

    try:
        w = await asyncio.get_event_loop().run_in_executor(None, whois_lib.whois, domain)
        result["registrar"] = str(w.registrar) if w.registrar else ""
        result["registrant_name"] = str(w.name) if w.name else ""
        emails = w.emails if w.emails else []
        result["registrant_email"] = str(emails[0]) if emails else ""
        result["registrant_org"] = str(w.org) if w.org else ""
        result["creation_date"] = str(w.creation_date[0]) if w.creation_date else ""
        result["expiration_date"] = str(w.expiration_date[0]) if w.expiration_date else ""
    except Exception:
        pass

    return result


async def _scrape_contact_page(client: httpx.AsyncClient, domain: str) -> list[str]:
    """Scrape domain's contact page for emails."""
    contact_paths = ["/contact", "/contact-us", "/about", "/about-us"]

    for path in contact_paths:
        for scheme in ["https", "http"]:
            try:
                url = f"{scheme}://{domain}{path}"
                resp = await client.get(url, timeout=10.0, follow_redirects=True)
                if resp.status_code != 200:
                    continue

                emails = EMAIL_RE.findall(resp.text)
                emails = [e.lower() for e in emails if not e.endswith((".png", ".jpg", ".gif", ".svg", ".css", ".js"))]
                emails = list(dict.fromkeys(emails))

                if emails:
                    return emails[:5]
            except Exception:
                continue

    return []


async def run(domains: list[str]) -> list[dict]:
    """Extract seller contact info for a list of domains."""
    logger = setup_logger("SellerContactExtractor")

    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        follow_redirects=True, timeout=15.0,
    ) as client:
        semaphore = asyncio.Semaphore(10)
        results: list[dict] = []

        async def extract_one(domain: str):
            async with semaphore:
                whois_info = await _whois_lookup(domain)
                contact_emails = await _scrape_contact_page(client, domain)

                all_emails = []
                if whois_info.get("registrant_email"):
                    all_emails.append(whois_info["registrant_email"])
                all_emails.extend(contact_emails)
                all_emails = list(dict.fromkeys(all_emails))

                # Filter out privacy/redacted emails
                real_emails = [
                    e for e in all_emails
                    if "redact" not in e.lower()
                    and "privacy" not in e.lower()
                    and "proxy" not in e.lower()
                    and "whois" not in e.lower()
                ]

                results.append({
                    "domain_name": domain,
                    "registrar": whois_info.get("registrar", ""),
                    "registrant_name": whois_info.get("registrant_name", ""),
                    "registrant_org": whois_info.get("registrant_org", ""),
                    "seller_emails": real_emails[:5],
                    "creation_date": whois_info.get("creation_date", ""),
                    "expiration_date": whois_info.get("expiration_date", ""),
                })

        tasks = [extract_one(d) for d in domains]
        await asyncio.gather(*tasks)

    logger.info("Seller extractor found contacts for %d domains", len(results))
    return results
