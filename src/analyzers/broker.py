from __future__ import annotations

import asyncio
import re
from typing import Any

from src.outreach.buyer_discovery import BuyerDiscovery
from src.utils import setup_logger

NICHE_MULTIPLIERS: dict[str, float] = {
    "ai": 1.8,
    "saas": 1.5,
    "finance": 1.4,
    "health": 1.3,
    "ecommerce": 1.2,
    "education": 1.1,
    "cybersecurity": 1.3,
    "realestate": 1.2,
    "productivity": 1.1,
    "legal": 1.0,
}

NICHE_BUYER_POTENTIAL: dict[str, str] = {
    "ai": "very_high",
    "saas": "high",
    "finance": "high",
    "cybersecurity": "high",
    "health": "medium",
    "ecommerce": "medium",
    "education": "medium",
    "realestate": "medium",
    "productivity": "medium",
    "legal": "low",
}

TLD_SCORES: dict[str, float] = {
    "com": 90,
    "io": 75,
    "ai": 85,
    "co": 70,
    "net": 60,
    "org": 55,
    "dev": 65,
    "app": 65,
    "xyz": 40,
}


class BrokerAnalyzer:
    def __init__(self) -> None:
        self.logger = setup_logger("BrokerAnalyzer")
        self.buyer_discovery = BuyerDiscovery()

    async def analyze(self, domain_name: str, niche: str = "general") -> dict[str, Any]:
        self.logger.info("Broker analysis for %s (niche: %s)", domain_name, niche)

        availability = await self._check_domain_availability(domain_name)
        marketplace_score = self._estimate_marketplace_score(domain_name, niche)

        try:
            leads = await self.buyer_discovery.discover_buyers(domain_name, niche)
            self.logger.info(
                "Buyer discovery found %d leads for %s",
                leads.get("total_leads", 0),
                domain_name,
            )
        except Exception as exc:
            self.logger.warning("Buyer discovery failed for %s: %s", domain_name, exc)
            leads = {
                "total_leads": 0,
                "leads": [],
                "buyer_potential": "unknown",
                "estimated_buyers_in_niche": 0,
                "source": "fallback",
                "error": str(exc),
            }

        estimated_value = self._estimate_value(domain_name, niche)
        commission = self._estimate_commission(estimated_value)
        buyer_count = leads.get("total_leads", 0)

        broker_score = self._calculate_broker_score(
            marketplace_score=marketplace_score,
            buyer_count=buyer_count,
            estimated_value=estimated_value,
        )

        return {
            "domain_name": domain_name,
            "niche": niche,
            "availability": availability,
            "marketplace_score": marketplace_score,
            "buyer_leads": leads,
            "estimated_value": estimated_value,
            "commission": commission,
            "broker_score": broker_score,
            "broker_grade": self._assign_broker_grade(broker_score),
            "data_source": leads.get("source", "buyer_discovery"),
            "note": "Buyer leads sourced from live discovery module.",
        }

    async def _check_domain_availability(self, domain_name: str) -> dict[str, Any]:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                resp = await client.head(f"http://{domain_name}")
                resolved = resp.status_code < 400
                return {
                    "resolves": resolved,
                    "status_code": resp.status_code,
                    "likely_registered": True,
                    "note": "Domain resolves — likely registered and parked or in use.",
                }
        except httpx.ConnectError:
            return {
                "resolves": False,
                "status_code": None,
                "likely_registered": False,
                "note": "Domain does not resolve — may be available for registration.",
            }
        except Exception as exc:
            return {
                "resolves": None,
                "status_code": None,
                "likely_registered": None,
                "note": f"Could not check domain availability: {exc}",
            }

    def _estimate_marketplace_score(self, domain_name: str, niche: str) -> float:
        tld = domain_name.split(".")[-1] if "." in domain_name else ""
        name_part = domain_name.replace(f".{tld}", "") if tld else domain_name

        tld_score = TLD_SCORES.get(tld, 30)

        length = len(name_part)
        if length <= 4:
            length_score = 100
        elif length <= 8:
            length_score = 80
        elif length <= 12:
            length_score = 60
        else:
            length_score = 30

        word_count = len(re.split(r"[-_]", name_part))
        word_score = max(0, 100 - (word_count - 1) * 25)

        has_numbers = any(c.isdigit() for c in name_part)
        numbers_penalty = -15 if has_numbers else 0

        is_premium_tld = tld in ("com", "ai", "io")
        premium_bonus = 10 if is_premium_tld else 0

        raw = (tld_score * 0.3 + length_score * 0.3 + word_score * 0.3) + numbers_penalty + premium_bonus
        return round(max(0.0, min(100.0, raw)), 2)

    def _estimate_value(self, domain_name: str, niche: str) -> int:
        tld = domain_name.split(".")[-1] if "." in domain_name else "com"
        name_part = domain_name.replace(f".{tld}", "")
        length = len(name_part)
        hyphens = name_part.count("-")

        base_value = 500 if tld == "com" else 100
        length_bonus = max(0, 1000 - length * 50)
        hyphen_penalty = max(0, hyphens * 100)
        multiplier = NICHE_MULTIPLIERS.get(niche, 1.0)

        value = (base_value + length_bonus - hyphen_penalty) * multiplier
        return max(50, int(value))

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
