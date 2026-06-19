from __future__ import annotations

from typing import Any, Optional

from src.config import settings
from src.utils import setup_logger


class ScoringEngine:
    RESALE_DEMAND_MAP: dict[str, float] = {
        "low": 30.0,
        "medium": 65.0,
        "high": 90.0,
    }

    GRADE_THRESHOLDS: list[tuple[float, float, str]] = [
        (85.0, 100.0, "A+"),
        (70.0, 84.99, "A"),
        (55.0, 69.99, "B"),
        (40.0, 54.99, "C"),
    ]

    def __init__(self, config: Optional[Any] = None) -> None:
        self.config = config or settings
        self.logger = setup_logger("ScoringEngine")

    def calculate(
        self,
        domain: str,
        price: float,
        seo_score: float,
        commercial_score: float,
        trust_score: float,
        cleanliness_score: float,
        dr: float = 0.0,
        referring_domains: int = 0,
    ) -> dict:
        # Handle None values
        price = price if price is not None else 0.0
        seo_score = seo_score if seo_score is not None else 0.0
        commercial_score = commercial_score if commercial_score is not None else 0.0
        trust_score = trust_score if trust_score is not None else 0.0
        cleanliness_score = cleanliness_score if cleanliness_score is not None else 0.0
        self.logger.info(
            "Calculating final score for domain=%s price=%.2f seo=%.1f commercial=%.1f "
            "trust=%.1f cleanliness=%.1f dr=%.0f ref_domains=%d",
            domain, price, seo_score, commercial_score, trust_score,
            cleanliness_score, dr, referring_domains,
        )

        rejection = self._check_rejection_filters(
            cleanliness_score, trust_score, seo_score, price
        )
        if rejection is not None:
            self.logger.info("Domain rejected: %s", rejection["reason"])
            return rejection

        price_efficiency = self._price_efficiency(price)
        final_score = self._final_score(
            seo_score, commercial_score, trust_score, price_efficiency
        )
        opportunity_grade = self._assign_grade(final_score)
        reason = self._generate_reason(
            dr, commercial_score, cleanliness_score,
            referring_domains, price_efficiency,
        )

        result = {
            "final_score": round(final_score, 2),
            "opportunity_grade": opportunity_grade,
            "price_efficiency": round(price_efficiency, 1),
            "reason": reason,
        }

        self.logger.info("Scoring result: %s", result)
        return result

    def _check_rejection_filters(
        self,
        cleanliness_score: float,
        trust_score: float,
        seo_score: float,
        price: float,
    ) -> Optional[dict]:
        if cleanliness_score < 30:
            reason = f"Unclean history (score: {cleanliness_score})"
            self.logger.warning("Rejection: %s", reason)
            return self._rejection_result(reason)

        if trust_score < 20:
            self.logger.warning("Rejection: Low trust score")
            return self._rejection_result("Low trust score")

        if seo_score < 10:
            self.logger.warning("Rejection: Insufficient SEO metrics")
            return self._rejection_result("Insufficient SEO metrics")

        if price > self.config.exceptional_max and seo_score < 70:
            self.logger.warning("Rejection: Overpriced for SEO value")
            return self._rejection_result("Overpriced for SEO value")

        return None

    def _rejection_result(self, reason: str) -> dict:
        return {
            "final_score": 0.0,
            "opportunity_grade": "Avoid",
            "price_efficiency": 0.0,
            "reason": reason,
        }

    def _price_efficiency(self, price: float) -> float:
        pref_min = float(self.config.preferred_min)
        pref_max = float(self.config.preferred_max)
        max_bid = float(self.config.max_bid)
        exc_max = float(self.config.exceptional_max)

        if price <= 0:
            return 50.0

        if price <= pref_min:
            return 100.0

        if price <= pref_max:
            ratio = (price - pref_min) / (pref_max - pref_min) if pref_max > pref_min else 1.0
            efficiency = 100.0 - ratio * 50.0
            return max(0.0, min(100.0, efficiency))

        if price <= max_bid:
            ratio = (price - pref_max) / (max_bid - pref_max) if max_bid > pref_max else 1.0
            efficiency = 50.0 - ratio * 40.0
            return max(0.0, min(100.0, efficiency))

        decay = max(0.0, 10.0 - (price - max_bid) / exc_max * 10.0) if exc_max > 0 else 0.0
        return max(0.0, min(100.0, decay))

    def _final_score(
        self,
        seo_score: float,
        commercial_score: float,
        trust_score: float,
        price_efficiency: float,
    ) -> float:
        score = (
            0.40 * seo_score
            + 0.30 * commercial_score
            + 0.20 * trust_score
            + 0.10 * price_efficiency
        )
        return max(0.0, min(100.0, score))

    def _assign_grade(self, score: float) -> str:
        for lower, upper, grade in self.GRADE_THRESHOLDS:
            if lower <= score <= upper:
                return grade
        return "Avoid"

    def _generate_reason(
        self,
        dr: float,
        commercial_score: float,
        cleanliness_score: float,
        referring_domains: int,
        price_efficiency: float,
    ) -> str:
        category = "general"
        parts: list[str] = [f"DR {dr:.0f}, {category} niche"]

        if cleanliness_score > 70:
            parts.append("Clean history")

        if referring_domains > 100:
            parts.append("Strong backlinks")

        if commercial_score > 70:
            parts.append("Good brandability")

        if price_efficiency > 70:
            parts.append("Undervalued")

        return ", ".join(parts)
