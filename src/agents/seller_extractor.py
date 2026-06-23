"""Subagent 4: Extracts seller contact info from WHOIS and contact pages."""

from __future__ import annotations

import asyncio
import re
import socket

import httpx

from src.utils import setup_logger

try:
    import whois as whois_lib
except ImportError:
    whois_lib = None

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")


async def _whois_lookup(domain: str) -> dict:
    """Look up WHOIS info for a domain."""
    logger = setup_logger("WhoisLookup")
    result = {
        "registrar": "",
        "registrant_name": "",
        "registrant_email": "",
        "registrant_org": "",
        "creation_date": "",
        "expiration_date": "",
        "name_servers": [],
    }

    if whois_lib is None:
        return result

    try:
        w = await asyncio.get_event_loop().run_in_executor(None, whois_lib.whois, domain)
        result["registrar"] = str(w.registrar) if w.registrar else ""
        result["registrant_name"] = str(w.name) if w.name else ""
        result["registrant_email"] = str(w.emails[0]) if w.emails else ""
        result["registrant_org"] = str(w.org) if w.org else ""
        result["creation_date"] = str(w.creation_date[0]) if w.creation_date else ""
        result["expiration_date"] = str(w.expiration_date[0]) if w.expiration_date else ""
        result["name_servers"] = [str(ns) for ns in (w.name_servers or [])[:3]]
    except Exception as e:
        logger.debug("WHOIS failed for %s: %s", domain, e)

    return result


async def _scrape_contact_page(client: httpx.AsyncClient, domain: str) -> dict:
    """Scrape the domain's contact/about page for emails."""
    result = {"emails": [], "phone": "", "contact_page_url": ""}

    contact_paths = [
        "/contact", "/contact-us", "/about", "/about-us",
        "/contact.html", "/contactus.html",
    ]

    for path in contact_paths:
        for scheme in ["https", "http"]:
            try:
                url = f"{scheme}://{domain}{path}"
                resp = await client.get(url, timeout=10.0, follow_redirects=True)
                if resp.status_code != 200:
                    continue

                html = resp.text

                # Extract emails
                emails = EMAIL_RE.findall(html)
                emails = [e.lower() for e in emails if not e.endswith((".png", ".jpg", ".gif", ".svg", ".css", ".js"))]
                emails = list(dict.fromkeys(emails))  # dedupe

                # Extract phone
                phones = PHONE_RE.findall(html)

                if emails or phones:
                    result["emails"] = emails[:5]
                    result["phone"] = phones[0] if phones else ""
                    result["contact_page_url"] = url
                    return result

            except Exception:
                continue

    return result


async def _check_whois_email(domain: str) -> str:
    """Get email from WHOIS."""
    whois_info = await _whois_lookup(domain)
    return whois_info.get("registrant_email", "")


async def run(domains: list[str]) -> list[dict]:
    """Extract seller contact info for a list of domains."""
    logger = setup_logger("SellerExtractor")

    async with httpx.AsyncClient(
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
        },
        follow_redirects=True,
        timeout=15.0,
    ) as client:
        semaphore = asyncio.Semaphore(10)
        results: list[dict] = []

        async def extract_one(domain: str):
            async with semaphore:
                # Get WHOIS info
                whois_info = await _whois_lookup(domain)

                # Get contact page emails
                contact_info = await _scrape_contact_page(client, domain)

                # Combine emails (WHOIS + contact page)
                all_emails = []
                if whois_info.get("registrant_email"):
                    all_emails.append(whois_info["registrant_email"])
                all_emails.extend(contact_info.get("emails", []))
                all_emails = list(dict.fromkeys(all_emails))  # dedupe

                results.append({
                    "domain_name": domain,
                    "registrar": whois_info.get("registrar", ""),
                    "registrant_name": whois_info.get("registrant_name", ""),
                    "registrant_org": whois_info.get("registrant_org", ""),
                    "seller_emails": all_emails[:5],
                    "phone": contact_info.get("phone", ""),
                    "contact_page_url": contact_info.get("contact_page_url", ""),
                    "creation_date": whois_info.get("creation_date", ""),
                    "expiration_date": whois_info.get("expiration_date", ""),
                    "name_servers": whois_info.get("name_servers", []),
                })

        tasks = [extract_one(d) for d in domains]
        await asyncio.gather(*tasks)

    logger.info("Seller extractor found contacts for %d domains", len(results))
    return results
