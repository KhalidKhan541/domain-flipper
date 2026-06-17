from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.integrations.apollo_client import ApolloClient
from src.integrations.tomba_client import TombaClient
from src.integrations.social_search import SocialSearcher
from src.config import settings

logger = logging.getLogger(__name__)

CREDIT_FILE = Path("data/credit_usage.json")

# Free tier monthly limits
APOLLO_MONTHLY_LIMIT = 100
TOMBA_MONTHLY_LIMIT = 50

# Only use paid credits for domains with score >= this threshold
CREDIT_THRESHOLD = 70

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


class CreditTracker:
    """Tracks monthly API credit usage to stay within free tier limits."""

    def __init__(self) -> None:
        self._data = self._load()

    def _load(self) -> dict[str, Any]:
        if CREDIT_FILE.exists():
            try:
                data = json.loads(CREDIT_FILE.read_text())
                # Reset if month changed
                if data.get("month") != self._current_month():
                    return self._fresh_data()
                return data
            except (json.JSONDecodeError, KeyError):
                return self._fresh_data()
        return self._fresh_data()

    def _fresh_data(self) -> dict[str, Any]:
        return {
            "month": self._current_month(),
            "apollo_used": 0,
            "tomba_used": 0,
        }

    def _current_month(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m")

    def save(self) -> None:
        CREDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
        CREDIT_FILE.write_text(json.dumps(self._data, indent=2))

    def apollo_available(self) -> int:
        return max(0, APOLLO_MONTHLY_LIMIT - self._data.get("apollo_used", 0))

    def tomba_available(self) -> int:
        return max(0, TOMBA_MONTHLY_LIMIT - self._data.get("tomba_used", 0))

    def use_apollo(self, count: int = 1) -> int:
        """Use Apollo credits. Returns actual credits used (may be less than requested)."""
        available = self.apollo_available()
        used = min(count, available)
        self._data["apollo_used"] = self._data.get("apollo_used", 0) + used
        self.save()
        if used < count:
            logger.warning("Apollo credits exhausted: requested %d, used %d", count, used)
        return used

    def use_tomba(self, count: int = 1) -> int:
        """Use Tomba credits. Returns actual credits used (may be less than requested)."""
        available = self.tomba_available()
        used = min(count, available)
        self._data["tomba_used"] = self._data.get("tomba_used", 0) + used
        self.save()
        if used < count:
            logger.warning("Tomba credits exhausted: requested %d, used %d", count, used)
        return used

    def status(self) -> dict[str, Any]:
        return {
            "month": self._current_month(),
            "apollo_used": self._data.get("apollo_used", 0),
            "apollo_limit": APOLLO_MONTHLY_LIMIT,
            "apollo_available": self.apollo_available(),
            "tomba_used": self._data.get("tomba_used", 0),
            "tomba_limit": TOMBA_MONTHLY_LIMIT,
            "tomba_available": self.tomba_available(),
        }


class BuyerDiscovery:
    def __init__(self) -> None:
        self.apollo = ApolloClient(api_key=getattr(settings, "apollo_api_key", None))
        self.tomba = TombaClient(api_key=getattr(settings, "tomba_api_key", None))
        self.social = SocialSearcher(
            twitter_bearer_token=getattr(settings, "twitter_bearer_token", None),
        )
        self.credits = CreditTracker()

    async def discover_buyers(
        self,
        domain_name: str,
        niche: str,
        broker_score: float = 0.0,
    ) -> dict[str, Any]:
        """
        Find potential buyers for a domain.

        Strategy based on broker_score:
        - Score >= 70: Use Apollo + Tomba (paid credits) for high-quality leads
        - Score < 70: Use only free social search (save credits for best opportunities)
        """
        logger.info(
            "Starting buyer discovery for %s (niche: %s, score: %.1f)",
            domain_name, niche, broker_score,
        )

        keywords = self._extract_keywords(domain_name, niche)
        logger.info("Extracted keywords: %s", keywords)

        companies: list[dict[str, Any]] = []
        contacts: list[dict[str, Any]] = []
        social_signals: dict[str, Any] = {"reddit": [], "twitter": [], "hackernews": [], "total": 0}
        social_intent_signals: list[str] = []
        credits_used = {"apollo": 0, "tomba": 0}
        source = "social"

        # Decide strategy based on score
        use_paid_apis = broker_score >= CREDIT_THRESHOLD and self._has_api_keys()

        if use_paid_apis:
            logger.info(
                "Domain %s scored %.1f (>= %d) — using Apollo + Tomba credits",
                domain_name, broker_score, CREDIT_THRESHOLD,
            )
            source = "apollo+tomba+social"

            # Step 2: Find companies via Apollo (use 5 credits)
            companies = await self._search_companies(keywords, credits_used)

            # Step 3: Find contacts via Tomba (use up to 15 credits)
            contacts = await self._search_contacts(companies, credits_used)

        else:
            reason = "low score" if broker_score < CREDIT_THRESHOLD else "no API keys"
            logger.info(
                "Domain %s — using free social search only (%s)",
                domain_name, reason,
            )
            source = "social"

        # Step 4: Find social signals (always free)
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
            "source": source,
            "credits_used": credits_used,
            "credit_status": self.credits.status(),
        }

        logger.info(
            "Buyer discovery complete for %s — %d leads found (credits: apollo=%d, tomba=%d)",
            domain_name, len(top_leads),
            credits_used["apollo"], credits_used["tomba"],
        )
        return result

    def _has_api_keys(self) -> bool:
        """Check if we have API keys configured."""
        has_apollo = bool(getattr(settings, "apollo_api_key", None))
        has_tomba = bool(getattr(settings, "tomba_api_key", None))
        return has_apollo or has_tomba

    async def _search_companies(
        self, keywords: list[str], credits_used: dict[str, int],
    ) -> list[dict[str, Any]]:
        """Search companies via Apollo, respecting credit limits."""
        available = self.credits.apollo_available()
        if available <= 0:
            logger.warning("Apollo credits exhausted — skipping company search")
            return []

        try:
            companies = await self.apollo.search_companies(
                keywords=keywords,
                min_employees=10,
                max_employees=500,
                limit=min(25, available),
            )
            used = self.credits.use_apollo(len(companies))
            credits_used["apollo"] = used
            logger.info("Found %d companies from Apollo (used %d credits)", len(companies), used)
            return companies
        except Exception as exc:
            logger.error("Apollo company search failed: %s", exc)
            return []

    async def _search_contacts(
        self, companies: list[dict[str, Any]], credits_used: dict[str, int],
    ) -> list[dict[str, Any]]:
        """Find contacts via Tomba, respecting credit limits."""
        contacts: list[dict[str, Any]] = []
        available = self.credits.tomba_available()

        if available <= 0:
            logger.warning("Tomba credits exhausted — skipping contact search")
            return contacts

        # Process companies until we run out of credits
        credits_remaining = available
        for company in companies:
            if credits_remaining <= 0:
                break

            company_domain = company.get("company_domain", "")
            if not company_domain:
                continue

            try:
                # Use 1 credit per email finder call
                emails = await self.tomba.find_emails(domain=company_domain, limit=3)
                if emails:
                    used = self.credits.use_tomba(1)
                    credits_used["tomba"] += used
                    credits_remaining -= used

                for entry in emails:
                    position = entry.get("position", "").upper()
                    if any(
                        title in position
                        for title in ("CEO", "CTO", "CFO", "COO", "FOUNDER", "PRESIDENT", "VP", "DIRECTOR")
                    ):
                        # Verify email (1 credit)
                        if credits_remaining > 0:
                            verification = await self.tomba.verify_email(entry.get("email", ""))
                            used = self.credits.use_tomba(1)
                            credits_used["tomba"] += used
                            credits_remaining -= used
                        else:
                            verification = {"valid": False}

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
        return contacts

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
