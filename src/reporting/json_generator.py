from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import settings
from src.utils import setup_logger


class JSONReportGenerator:
    def __init__(self) -> None:
        self.logger: logging.Logger = setup_logger("JSONReport")

    async def generate(self, domains: list[dict[str, Any]]) -> str:
        scores = [d.get("final_score", 0) or 0 for d in domains if d.get("final_score") is not None]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        grade_counts: dict[str, int] = {}
        for d in domains:
            g = d.get("opportunity_grade", "N/A")
            grade_counts[g] = grade_counts.get(g, 0) + 1

        top_domains: list[dict[str, Any]] = []
        for d in domains:
            entry = {
                "domain_name": d.get("domain_name"),
                "price": d.get("price"),
                "dr": d.get("dr"),
                "referring_domains": d.get("referring_domains"),
                "domain_age": d.get("domain_age"),
                "category": d.get("category"),
                "final_score": d.get("final_score"),
                "opportunity_grade": d.get("opportunity_grade"),
                "trust_score": d.get("trust_score"),
                "seo_score": d.get("seo_score"),
                "commercial_score": d.get("commercial_score"),
                "cleanliness_score": d.get("cleanliness_score"),
                "reason": d.get("reason"),
                "source": d.get("source"),
                "registrar": d.get("registrar"),
                "tld": d.get("tld"),
                "auction_end_date": d.get("auction_end_date"),
            }
            top_domains.append(entry)

        report = {
            "report_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "total_domains": len(domains),
            "budget": {
                "max_bid": settings.max_bid,
                "preferred_max": settings.preferred_max,
            },
            "summary": {
                "avg_score": round(avg_score, 2),
                "grade_counts": grade_counts,
            },
            "top_domains": top_domains,
        }

        return json.dumps(report, indent=2, ensure_ascii=False)

    async def save(self, content: str, filename: str | None = None) -> Path:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        name = filename or f"report_{date}.json"
        report_dir = Path("data/reports")
        report_dir.mkdir(parents=True, exist_ok=True)
        path = report_dir / name
        path.write_text(content, encoding="utf-8")
        self.logger.info("JSON report saved to %s", path)
        return path
