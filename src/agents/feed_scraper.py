"""Subagent 1: Scrapes expired domain feeds (expireddomains.net, drop lists)."""

from __future__ import annotations

import re

import httpx
from bs4 import BeautifulSoup

from src.feeds.quality_filter import filter_domains
from src.utils import setup_logger

DOMAIN_RE = re.compile(
    r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.(com|io|ai|co|net|org|dev|app)$"
)

# Known corporate domains to exclude
EXCLUDE_DOMAINS: set[str] = {
    "google.com", "googleapis.com", "gstatic.com", "youtube.com", "youtu.be",
    "facebook.com", "facebook.net", "fbcdn.net", "instagram.com",
    "twitter.com", "x.com", "tiktok.com", "tiktokcdn.com",
    "apple.com", "icloud.com", "microsoft.com", "live.com", "office.com",
    "azure.com", "bing.com", "msn.com", "skype.com",
    "linkedin.com", "licdn.com", "amazon.com", "amazonaws.com", "cloudfront.net",
    "netflix.com", "spotify.com", "slack.com", "salesforce.com",
    "adobe.com", "oracle.com", "ibm.com", "intel.com", "cisco.com",
    "reddit.com", "redditstatic.com", "pinterest.com", "snapchat.com",
    "discord.com", "twitch.tv", "vimeo.com", "medium.com",
    "github.com", "github.io", "gitlab.com", "stackoverflow.com",
    "cloudflare.com", "heroku.com", "vercel.com", "netlify.com",
    "godaddy.com", "namecheap.com", "namesilo.com", "dynadot.com", "porkbun.com",
    "stripe.com", "paypal.com", "square.com",
    "wikipedia.org", "wikimedia.org",
    "ebay.com", "etsy.com", "walmart.com", "aliexpress.com",
    "booking.com", "airbnb.com", "uber.com",
    "zoom.us", "dropbox.com", "mailchimp.com",
    "hubspot.com", "intercom.com", "sentry.io",
    "bugsnag.com", "newrelic.com",
}


async def run() -> list[dict]:
    """Scrape expired domain feeds and return filtered domains."""
    logger = setup_logger("FeedScraperAgent")
    all_domains: list[str] = []

    async with httpx.AsyncClient(
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        },
        follow_redirects=True,
        timeout=30.0,
    ) as client:
        # Source 1: ExpiredDomains.net
        try:
            resp = await client.get("https://www.expireddomains.net/expired-domains/")
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for table in soup.find_all("table"):
                    headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
                    if not any("domain" in h for h in headers):
                        continue
                    for row in table.find_all("tr"):
                        cells = row.find_all("td")
                        if len(cells) < 2:
                            continue
                        first_cell = cells[0]
                        link = first_cell.find("a")
                        if link:
                            text = link.get_text(strip=True).lower()
                            if DOMAIN_RE.match(text) and text not in EXCLUDE_DOMAINS:
                                all_domains.append(text)
                        text = first_cell.get_text(strip=True).lower()
                        if DOMAIN_RE.match(text) and text not in EXCLUDE_DOMAINS:
                            all_domains.append(text)
                logger.info("expireddomains.net: %d domains", len(all_domains))
        except Exception as e:
            logger.warning("expireddomains.net failed: %s", e)

        # Source 2: Drop list
        try:
            resp = await client.get("https://www.expireddomains.net/domains/catched/")
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for table in soup.find_all("table"):
                    for row in table.find_all("tr"):
                        cells = row.find_all("td")
                        for cell in cells:
                            text = cell.get_text(strip=True).lower()
                            if DOMAIN_RE.match(text) and text not in EXCLUDE_DOMAINS:
                                all_domains.append(text)
        except Exception:
            pass

    unique = list(dict.fromkeys(all_domains))
    logger.info("Feed scraper found %d unique domains", len(unique))

    domain_dicts = [
        {"domain_name": d, "price": 0.0, "source": "feed_scraper", "tld": d.split(".")[-1],
         "dr": 0, "referring_domains": 0, "domain_age": 0}
        for d in unique
    ]
    return filter_domains(domain_dicts)
