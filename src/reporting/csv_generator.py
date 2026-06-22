from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.utils import setup_logger


class CSVReportGenerator:
    def __init__(self) -> None:
        self.logger: logging.Logger = setup_logger("CSVReport")

    async def generate(self, domains: list[dict[str, Any]]) -> str:
        output = io.StringIO()
        writer = csv.writer(output)

        columns = [
            "rank",
            "domain_name",
            "estimated_value",
            "commission",
            "buyer_leads_count",
            "broker_score",
            "broker_grade",
            "marketplace_listed",
            "marketplace_count",
            "niche",
            "seller_name",
            "seller_email",
            "dr",
            "referring_domains",
            "domain_age",
            "final_score",
            "opportunity_grade",
            "source",
            "tld",
        ]

        writer.writerow(columns)

        for rank, domain in enumerate(domains, 1):
            marketplace = domain.get("marketplace", {})
            owner_contact = domain.get("owner_contact", {})
            writer.writerow([
                rank,
                domain.get("domain_name", ""),
                domain.get("estimated_value", ""),
                domain.get("commission", {}).get("amount", ""),
                domain.get("buyer_leads", {}).get("total_leads", ""),
                domain.get("broker_score", ""),
                domain.get("broker_grade", ""),
                "Yes" if marketplace.get("is_listed") else "No",
                len(marketplace.get("listings", [])),
                domain.get("category", ""),
                owner_contact.get("registrant_name", ""),
                owner_contact.get("registrant_email", ""),
                domain.get("dr", ""),
                domain.get("referring_domains", ""),
                domain.get("domain_age", ""),
                domain.get("final_score", ""),
                domain.get("opportunity_grade", ""),
                domain.get("source", ""),
                domain.get("tld", ""),
            ])

        return output.getvalue()

    async def save(self, content: str, filename: str | None = None) -> Path:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        name = filename or f"broker_report_{date}.csv"
        report_dir = Path("data/reports")
        report_dir.mkdir(parents=True, exist_ok=True)
        path = report_dir / name
        path.write_text(content, encoding="utf-8")
        self.logger.info("CSV broker report saved to %s", path)
        return path
