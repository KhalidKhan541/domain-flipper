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
            "price",
            "dr",
            "referring_domains",
            "domain_age",
            "category",
            "final_score",
            "opportunity_grade",
            "trust_score",
            "seo_score",
            "commercial_score",
            "cleanliness_score",
            "reason",
            "source",
            "registrar",
            "tld",
        ]

        writer.writerow(columns)

        for rank, domain in enumerate(domains, 1):
            writer.writerow([
                rank,
                domain.get("domain_name", ""),
                domain.get("price", ""),
                domain.get("dr", ""),
                domain.get("referring_domains", ""),
                domain.get("domain_age", ""),
                domain.get("category", ""),
                domain.get("final_score", ""),
                domain.get("opportunity_grade", ""),
                domain.get("trust_score", ""),
                domain.get("seo_score", ""),
                domain.get("commercial_score", ""),
                domain.get("cleanliness_score", ""),
                domain.get("reason", ""),
                domain.get("source", ""),
                domain.get("registrar", ""),
                domain.get("tld", ""),
            ])

        return output.getvalue()

    async def save(self, content: str, filename: str | None = None) -> Path:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        name = filename or f"report_{date}.csv"
        report_dir = Path("data/reports")
        report_dir.mkdir(parents=True, exist_ok=True)
        path = report_dir / name
        path.write_text(content, encoding="utf-8")
        self.logger.info("CSV report saved to %s", path)
        return path
