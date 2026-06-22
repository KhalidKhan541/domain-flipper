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
        broker_grades: dict[str, int] = {}
        total_est_value = 0
        total_commission = 0
        for d in domains:
            g = d.get("broker_grade", "Cold")
            broker_grades[g] = broker_grades.get(g, 0) + 1
            total_est_value += d.get("estimated_value", 0) or 0
            commission = d.get("commission", {}).get("amount", 0) or 0
            total_commission += commission

        top_domains: list[dict[str, Any]] = []
        for d in domains:
            owner_contact = d.get("owner_contact", {})
            entry = {
                "domain_name": d.get("domain_name"),
                "estimated_value": d.get("estimated_value"),
                "commission": d.get("commission"),
                "broker_score": d.get("broker_score"),
                "broker_grade": d.get("broker_grade"),
                "marketplace": d.get("marketplace"),
                "buyer_leads": {
                    "total": d.get("buyer_leads", {}).get("total_leads", 0),
                    "companies": [
                        {"name": l.get("company"), "type": l.get("type")}
                        for l in (d.get("buyer_leads", {}).get("leads", []) or [])[:5]
                    ],
                },
                "seller": {
                    "name": owner_contact.get("registrant_name"),
                    "email": owner_contact.get("registrant_email"),
                    "org": owner_contact.get("registrant_org"),
                },
                "category": d.get("category"),
                "dr": d.get("dr"),
                "referring_domains": d.get("referring_domains"),
                "domain_age": d.get("domain_age"),
                "final_score": d.get("final_score"),
                "opportunity_grade": d.get("opportunity_grade"),
                "source": d.get("source"),
                "tld": d.get("tld"),
            }
            top_domains.append(entry)

        report = {
            "report_type": "broker",
            "report_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "total_opportunities": len(domains),
            "summary": {
                "total_estimated_value": total_est_value,
                "total_potential_commission": total_commission,
                "broker_grade_counts": broker_grades,
            },
            "opportunities": top_domains,
        }

        return json.dumps(report, indent=2, ensure_ascii=False)

    async def save(self, content: str, filename: str | None = None) -> Path:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        name = filename or f"broker_report_{date}.json"
        report_dir = Path("data/reports")
        report_dir.mkdir(parents=True, exist_ok=True)
        path = report_dir / name
        path.write_text(content, encoding="utf-8")
        self.logger.info("JSON broker report saved to %s", path)
        return path
