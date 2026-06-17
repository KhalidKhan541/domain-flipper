from __future__ import annotations

import logging
import re
from typing import Any

from src.integrations.apollo_client import ApolloClient
from src.integrations.tomba_client import TombaClient
from src.integrations.social_search import SocialSearcher
from src.config import settings

logger = logging.getLogger(__name__)

NICHE_SYNONYMS: dict[str, list[str]] = {
    "ai": ["artificial intelligence", "machine learning", "deep learning", "neural network", "nlp"],
    "cloud": ["saas", "cloud computing", "infrastructure", "hosting", "devops"],
    "finance": ["fintech", "banking", "investment", "payments", "crypto"],
    "health": ["healthcare", "medtech", "biotech", "pharma", "wellness"],
    "ecommerce": ["e-commerce", "retail", "marketplace", "shopping", "store"],
    "security": ["cybersecurity", "infosec", "privacy", "compliance", "protection"],
    "data": ["analytics", "big data", "data science", "business intelligence", "database"],
    "education": ["edtech", "learning", "training", "elearning", "courses"],
    "marketing": ["adtech", "advertising", "growth", "seo", "content"],
    "realestate": ["proptech", "real estate", "property", "housing", "commercial"],
}


class BuyerDiscovery:
    def __init__(self) -> None:
        self.apollo = ApolloClient(api_key=getattr(settings, "apollo_api_key", None))
        self.tomba = TombaClient(api_key=getattr(settings, "tomba_api_key", None))
        self.social = SocialSearcher(
            twitter_bearer_token=getattr(settings, "twitter_bearer_token", None),
        )

    async def discover_buyers(self, domain_name: str, niche: str) -> dict[str, Any]:
        logger.info("Starting buyer discovery for %s (niche: %s)", domain_name, niche)

        keywords = self._extract_keywords(domain_name, niche)
        logger.info("Extracted keywords: %s", keywords)

        companies: list[dict[str, Any]] = []
        contacts: list[dict[str, Any]] = []
        social_signals: dict[str, Any] = {"reddit": [], "twitter": [], "hackernews": [], "total": 0}
        social_intent_signals: list[str] = []

        # Step 2: Find companies via Apollo
        try:
            companies = await self.apollo.search_companies(
                keywords=keywords,
                min_employees=10,
                max_employees=500,
                limit=25,
            )
            logger.info("Found %d companies from Apollo", len(companies))
        except Exception as exc:
            logger.error("Apollo company search failed: %s — continuing with other sources", exc)

        # Step 3: Find contacts via Tomba
        if companies:
            for company in companies[:15]:
                company_domain = company.get("company_domain", "")
                if not company_domain:
                    continue

                try:
                    emails = await self.tomba.find_emails(domain=company_domain, limit=5)
                    for entry in emails:
                        position = entry.get("position", "").upper()
                        if any(
                            title in position
                            for title in ("CEO", "CTO", "CFO", "COO", "FOUNDER", "PRESIDENT", "VP", "DIRECTOR")
                        ):
                            verification = await self.tomba.verify_email(entry.get("email", ""))
                            contacts.append({
                                "company": company.get("company", ""),
                                "company_domain": company_domain,
                                "contact_name": entry.get("first_name", "") + " " + entry.get("last_name", ""),
                                "contact_title": entry.get("position", ""),
                                "email": entry.get("email", ""),
                                "email_valid": verification.get("valid", False),
                                "email_confidence": entry.get("confidence", 0),
                                "employee_count": company.get("employee_count", 0),
                                "industry": company.get("industry", ""),
                                "location": company.get("location", ""),
                                "source": "apollo+tomba",
                            })
                except Exception as exc:
                    logger.error("Tomba contact search failed for %s: %s", company_domain, exc)

            logger.info("Found %d contacts from Tomba", len(contacts))

        # Step 4: Find social signals
        try:
            social_signals = await self.social.search_all(domain_name, niche, keywords)
            social_intent_signals = self.social.extract_intent_signals(social_signals)
            logger.info("Found %d social signals", social_signals.get("total", 0))
        except Exception as exc:
            logger.error("Social search failed: %s — continuing with other sources", exc)

        # Merge social intent signals into relevant contacts
        for contact in contacts:
            contact["social_signals"] = social_intent_signals[:3] if social_intent_signals else []

        # Step 5: Score and rank leads
        leads = self._build_leads(contacts, social_intent_signals)
        leads.sort(key=lambda x: x["lead_score"], reverse=True)
        top_leads = leads[:10]

        result = {
            "domain": domain_name,
            "niche": niche,
            "total_leads": len(top_leads),
            "leads": top_leads,
            "social_signals": social_signals,
        }

        logger.info(
            "Buyer discovery complete for %s — %d leads found",
            domain_name,
            len(top_leads),
        )
        return result

    def _extract_keywords(self, domain_name: str, niche: str) -> list[str]:
        base = domain_name.split(".")[0]
        parts: list[str] = []

        # Split camelCase
        camel_split = re.sub(r"([a-z])([A-Z])", r"\1 \2", base)
        parts.extend(camel_split.split())

        # Split hyphens and underscores
        expanded: list[str] = []
        for part in parts:
            expanded.extend(re.split(r"[-_]+", part))

        keywords = [kw.lower() for kw in expanded if len(kw) > 1]

        # Add niche and its synonyms
        if niche:
            keywords.append(niche.lower())
            synonyms = NICHE_SYNONYMS.get(niche.lower(), [])
            keywords.extend(synonyms)

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower not in seen:
                seen.add(kw_lower)
                unique.append(kw_lower)

        return unique

    def _build_leads(
        self,
        contacts: list[dict[str, Any]],
        social_intent_signals: list[str],
    ) -> list[dict[str, Any]]:
        leads: list[dict[str, Any]] = []

        for contact in contacts:
            lead = {
                "company": contact.get("company", ""),
                "company_domain": contact.get("company_domain", ""),
                "contact_name": contact.get("contact_name", ""),
                "contact_title": contact.get("contact_title", ""),
                "email": contact.get("email", ""),
                "email_valid": contact.get("email_valid", False),
                "employee_count": contact.get("employee_count", 0),
                "social_signals": contact.get("social_signals", []),
                "lead_score": self._score_lead(contact),
                "source": contact.get("source", "apollo+tomba"),
            }
            leads.append(lead)

        # If no contacts from APIs, create synthetic leads from social signals
        if not leads and social_intent_signals:
            for i, signal in enumerate(social_intent_signals[:5]):
                leads.append({
                    "company": "",
                    "company_domain": "",
                    "contact_name": "",
                    "contact_title": "",
                    "email": "",
                    "email_valid": False,
                    "employee_count": 0,
                    "social_signals": [signal],
                    "lead_score": self._score_lead({"social_signals": [signal]}),
                    "source": "social",
                })

        return leads

    def _score_lead(self, lead: dict[str, Any]) -> float:
        score = 0.0

        # Has valid email: +30 points
        if lead.get("email_valid", False):
            score += 30.0

        # Email exists but not verified: +15 points
        elif lead.get("email"):
            score += 15.0

        # Company in right niche: +25 points
        industry = (lead.get("industry") or "").lower()
        if industry:
            score += 25.0

        # Right size (10-500 employees): +20 points
        emp = lead.get("employee_count", 0)
        if 10 <= emp <= 500:
            score += 20.0
        elif emp > 0:
            score += 10.0

        # Social intent signal: +25 points
        social = lead.get("social_signals", [])
        if social:
            score += 25.0

        # Bonus: executive title
        title = (lead.get("contact_title") or "").upper()
        if any(t in title for t in ("CEO", "CTO", "FOUNDER", "PRESIDENT")):
            score += 10.0
        elif any(t in title for t in ("VP", "DIRECTOR", "HEAD")):
            score += 5.0

        return round(score, 1)
