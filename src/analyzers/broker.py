from __future__ import annotations

import random
from typing import Any

from src.config import settings
from src.utils import setup_logger


LEADS_BY_NICHE: dict[str, list[str]] = {
    "ai": [
        "OpenAI", "Anthropic", "Cohere", "Hugging Face", "Stability AI",
        "Jasper AI", "Copy.ai", "Writer.com", "Runway ML", "Midjourney",
        "Scale AI", "DataRobot", "H2O.ai", "C3 AI", "Pathmind",
    ],
    "saas": [
        "Salesforce", "HubSpot", "Zendesk", "Slack", "Atlassian",
        "Notion", "Airtable", "Asana", "Monday.com", "ClickUp",
        "Freshworks", "Intercom", "DocuSign", "Box", "Dropbox",
    ],
    "finance": [
        "Stripe", "Square", "Plaid", "Robinhood", "Coinbase",
        "PayPal", "Revolut", "Wise", "Klarna", "Affirm",
        "Chime", "Betterment", "Wealthfront", "SoFi", "Nubank",
    ],
    "health": [
        "Teladoc", "Ro", "Hims", "Noom", "Calm",
        "Headspace", "MyFitnessPal", "Fitbit", "Whoop", "Oura",
        "One Medical", "Carbon Health", "Zymergen", "Illumina", "23andMe",
    ],
    "ecommerce": [
        "Shopify", "BigCommerce", "Wix", "Squarespace", "WooCommerce",
        "Magento", "Salesforce Commerce", "PrestaShop", "OpenCart", "Ecwid",
        "Etsy", "Amazon", "eBay", "Walmart", "Target",
    ],
    "education": [
        "Coursera", "Udemy", "edX", "Khan Academy", "Duolingo",
        "Chegg", "Quizlet", "Byju's", "MasterClass", "Skillshare",
        "Pluralsight", "DataCamp", "Brilliant", "Codecademy", "Knewton",
    ],
    "cybersecurity": [
        "CrowdStrike", "Palo Alto", "Fortinet", "Zscaler", "Cloudflare",
        "Okta", "SentinelOne", "Darktrace", "Snyk", "Rapid7",
        "Tenable", "Check Point", "McAfee", "Trend Micro", "Cisco Security",
    ],
    "realestate": [
        "Zillow", "Redfin", "Compass", "Opendoor", "Realtor.com",
        "Airbnb", "Vrbo", "Booking.com", "CoStar", "Zumper",
        "Trulia", "Homes.com", "Reonomy", "CREXi", "LoopNet",
    ],
    "productivity": [
        "Notion", "Todoist", "Evernote", "Bear", "Roam Research",
        "Obsidian", "Miro", "Trello", "Notability", "GoodNotes",
        "Forest", "Focusmate", "RescueTime", "Clockify", "Toggl",
    ],
    "legal": [
        "LegalZoom", "Rocket Lawyer", "Avvo", "Clio", "MyCase",
        "PractiFi", "CaseText", "Casetext", "Ironclad", "Evisort",
        "LexisNexis", "Thomson Reuters", "DocuSign Legal", "LawGeex", "Definely",
    ],
}

BUYER_PROFILES = {
    "startup": "Early-stage startup looking to establish brand in niche",
    "growth": "Growth-stage company expanding product line",
    "enterprise": "Enterprise seeking strategic domain acquisition",
    "investor": "Domain investor looking for premium assets",
    "founder": "Solo founder / indie hacker building in niche",
}


class BrokerAnalyzer:
    def __init__(self) -> None:
        self.logger = setup_logger("BrokerAnalyzer")

    async def analyze(self, domain_name: str, niche: str = "general") -> dict[str, Any]:
        self.logger.info("Broker analysis for %s (niche: %s)", domain_name, niche)

        marketplace = await self._check_marketplaces(domain_name)
        leads = self._find_buyer_leads(domain_name, niche)
        estimated_value = self._estimate_value(domain_name, niche)
        commission = self._estimate_commission(estimated_value)
        buyer_count = leads.get("total_leads", 0)

        broker_score = self._calculate_broker_score(
            marketplace_score=marketplace.get("score", 50),
            buyer_count=buyer_count,
            estimated_value=estimated_value,
        )

        return {
            "domain_name": domain_name,
            "niche": niche,
            "marketplace": marketplace,
            "buyer_leads": leads,
            "estimated_value": estimated_value,
            "commission": commission,
            "broker_score": broker_score,
            "broker_grade": self._assign_broker_grade(broker_score),
        }

    async def _check_marketplaces(self, domain_name: str) -> dict[str, Any]:
        if settings.offline_mode:
            self.logger.info("Offline mode — using mock marketplace data for %s", domain_name)
            marketplaces = ["GoDaddy Auctions", "Afternic", "Sedo", "NameCheap", "Flippa"]
            listing_count = random.randint(0, 3)
            selected = random.sample(marketplaces, listing_count) if listing_count > 0 else []
            return {
                "is_listed": listing_count > 0,
                "listings": selected,
                "min_price": random.randint(100, 5000) if selected else 0,
                "score": min(100, listing_count * 30 + random.randint(0, 20)),
            }

        listings: list[str] = []
        prices: list[int] = []
        marketplaces = [
            ("GoDaddy Auctions", "https://auctions.godaddy.com/trpSearch/1"),
            ("Afternic", "https://www.afternic.com/forsale/"),
            ("Sedo", "https://sedo.com/search/details.php4?domain="),
            ("NameCheap", "https://www.namecheap.com/domains/domain-broker/"),
        ]

        for name, base_url in marketplaces:
            import httpx
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(f"{base_url}{domain_name}")
                    if resp.status_code == 200:
                        listings.append(name)
                        if name == "Afternic" and "buynow" in resp.text.lower():
                            import re
                            m = re.search(r"\$([0-9,]+)", resp.text)
                            if m:
                                prices.append(int(m.group(1).replace(",", "")))
            except Exception:
                continue

        score = min(100, len(listings) * 30) if listings else 10
        return {
            "is_listed": len(listings) > 0,
            "listings": listings,
            "min_price": min(prices) if prices else 0,
            "score": score,
        }

    def _find_buyer_leads(self, domain_name: str, niche: str) -> dict[str, Any]:
        base_keywords = domain_name.replace(f".{domain_name.split('.')[-1]}", "").split("-")

        leads: list[dict[str, str]] = []
        seen: set[str] = set()

        niche_companies = LEADS_BY_NICHE.get(niche, [])
        for company in niche_companies:
            if company.lower() not in seen:
                profile_type = random.choice(list(BUYER_PROFILES.keys()))
                leads.append({
                    "company": company,
                    "type": profile_type,
                    "profile": BUYER_PROFILES[profile_type],
                    "reason": f"Active in {niche} niche — domain matches their industry",
                })
                seen.add(company.lower())

        for kw in base_keywords:
            if kw and len(kw) > 2:
                related = [c for c in niche_companies if kw[:3].lower() in c.lower()]
                for company in related[:2]:
                    if company.lower() not in seen:
                        leads.append({
                            "company": company,
                            "type": "growth",
                            "profile": BUYER_PROFILES["growth"],
                            "reason": f"Keyword '{kw}' overlaps with their brand",
                        })
                        seen.add(company.lower())

        startup_names = [f"{kw} Technologies" for kw in base_keywords[:2] if kw and len(kw) > 2]
        for name in startup_names:
            if name.lower() not in seen:
                leads.append({
                    "company": name,
                    "type": "startup",
                    "profile": BUYER_PROFILES["startup"],
                    "reason": "Natural brand fit for a new startup",
                })
                seen.add(name.lower())

        return {
            "total_leads": len(leads),
            "leads": leads[:10],
        }

    def _estimate_value(self, domain_name: str, niche: str) -> int:
        tld = domain_name.split(".")[-1] if "." in domain_name else "com"
        name_part = domain_name.replace(f".{tld}", "")
        length = len(name_part)
        hyphens = name_part.count("-")

        base_value = 500 if tld == "com" else 100
        length_bonus = max(0, 1000 - length * 50)
        hyphen_penalty = max(0, hyphens * 100)
        niche_multiplier = LEADS_BY_NICHE.get(niche, [])
        niche_bonus = len(niche_multiplier) * 20

        value = base_value + length_bonus - hyphen_penalty + niche_bonus
        return max(50, value)

    def _estimate_commission(self, estimated_value: int) -> dict[str, Any]:
        commission_rate = 0.15
        return {
            "rate": commission_rate,
            "amount": round(estimated_value * commission_rate),
            "currency": "USD",
            "notes": "Standard 15% broker commission",
        }

    def _calculate_broker_score(
        self,
        marketplace_score: float,
        buyer_count: int,
        estimated_value: int,
    ) -> float:
        buyer_score = min(100, buyer_count * 10)
        value_score = min(100, estimated_value / 20)

        score = (
            0.30 * marketplace_score
            + 0.40 * buyer_score
            + 0.30 * value_score
        )
        return round(max(0.0, min(100.0, score)), 2)

    def _assign_broker_grade(self, score: float) -> str:
        if score >= 80:
            return "Hot Lead"
        if score >= 60:
            return "Warm"
        if score >= 40:
            return "Lukewarm"
        return "Cold"
