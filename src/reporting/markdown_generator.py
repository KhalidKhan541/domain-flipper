from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import settings
from src.utils import setup_logger


class MarkdownReportGenerator:
    def __init__(self) -> None:
        self.logger: logging.Logger = setup_logger("MarkdownReport")

    async def generate(self, domains: list[dict[str, Any]], date: str | None = None) -> str:
        date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        lines: list[str] = []
        total = len(domains)

        lines.append(f"# Daily Broker Report - {date}")
        lines.append("")

        lines.append("## Summary")
        lines.append("")
        lines.append(f"- **Total broker opportunities:** {total}")
        lines.append(f"- **Report date:** {date}")
        lines.append("")

        broker_grades: dict[str, int] = {}
        total_est_value = 0
        total_commission = 0
        for d in domains:
            g = d.get("broker_grade", "Cold")
            broker_grades[g] = broker_grades.get(g, 0) + 1
            total_est_value += d.get("estimated_value", 0) or 0
            commission = d.get("commission", {}).get("amount", 0) or 0
            total_commission += commission

        order = ["Hot Lead", "Warm", "Lukewarm", "Cold"]
        lines.append("### Broker Grades")
        lines.append("")
        for grade in order:
            count = broker_grades.get(grade, 0)
            bar = "█" * min(count, 20)
            lines.append(f"- **{grade}:** {count} {bar}")
        lines.append("")
        lines.append(f"- **Total estimated value:** ${total_est_value:,}")
        lines.append(f"- **Total potential commission:** ${total_commission:,}")
        lines.append("")

        lines.append("## Top 20 Broker Opportunities")
        lines.append("")
        lines.append("| # | Domain | Est. Value | Commission | Buyer Leads | Broker Score | Grade | Seller |")
        lines.append("|---|--------|------------|------------|-------------|--------------|-------|--------|")
        for i, d in enumerate(domains[:20], 1):
            name = d.get("domain_name", "unknown")
            est = d.get("estimated_value", 0) or 0
            comm = d.get("commission", {}).get("amount", 0) or 0
            leads = d.get("buyer_leads", {}).get("total_leads", 0) or 0
            bscore = d.get("broker_score", 0) or 0
            bgrade = d.get("broker_grade", "Cold") or "Cold"
            seller = d.get("owner_contact", {}).get("registrant_name", "N/A") or "N/A"
            lines.append(f"| {i} | {name} | ${est:,} | ${comm:,} | {leads} | {bscore} | {bgrade} | {seller} |")
        lines.append("")

        lines.append("## Domain Details")
        lines.append("")
        for i, d in enumerate(domains[:20], 1):
            name = d.get("domain_name", "unknown")
            lines.append(f"### {i}. {name}")
            lines.append("")

            marketplace = d.get("marketplace", {})
            if marketplace.get("is_listed"):
                lines.append(f"**Listed on:** {', '.join(marketplace.get('listings', []))}")
                lines.append(f"**Min price:** ${marketplace.get('min_price', 0):,}")
            else:
                lines.append("**Not currently listed on marketplaces**")
            lines.append("")

            buyer_leads = d.get("buyer_leads", {})
            leads_list = buyer_leads.get("leads", [])
            if leads_list:
                lines.append("**Potential buyers:**")
                for lead in leads_list[:5]:
                    lines.append(f"- {lead.get('company', 'Unknown')} ({lead.get('type', 'unknown')}) — {lead.get('reason', '')}")
            lines.append("")

            owner_contact = d.get("owner_contact", {})
            seller_name = owner_contact.get("registrant_name")
            seller_email = owner_contact.get("registrant_email")
            if seller_name or seller_email:
                lines.append("**Seller:**")
                if seller_name:
                    lines.append(f"- Name: {seller_name}")
                if seller_email:
                    lines.append(f"- Email: {seller_email}")
                lines.append("")

            lines.append("**Broker metrics:**")
            est = d.get("estimated_value", 0) or 0
            comm = d.get("commission", {}).get("amount", 0) or 0
            bscore = d.get("broker_score", 0) or 0
            bgrade = d.get("broker_grade", "Cold") or "Cold"
            lines.append(f"- Estimated value: ${est:,}")
            lines.append(f"- Broker commission: ${comm:,} (15%)")
            lines.append(f"- Broker score: {bscore}/100 — **{bgrade}**")

            fields = []
            if d.get("price"):
                fields.append(f"**Price:** ${d['price']}")
            if d.get("registrar"):
                fields.append(f"**Registrar:** {d['registrar']}")
            if d.get("tld"):
                fields.append(f"**TLD:** {d['tld']}")
            if d.get("source"):
                fields.append(f"**Source:** {d['source']}")
            if d.get("dr") is not None:
                fields.append(f"**DR:** {d['dr']}")
            if fields:
                lines.append(" | ".join(fields))
            lines.append("")

        lines.append("---")
        lines.append(f"*Generated by Domain Broker Bot on {date}*")

        return "\n".join(lines).strip()

    async def save(self, content: str, filename: str | None = None) -> Path:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        name = filename or f"broker_report_{date}.md"
        report_dir = Path("data/reports")
        report_dir.mkdir(parents=True, exist_ok=True)
        path = report_dir / name
        path.write_text(content, encoding="utf-8")
        self.logger.info("Markdown broker report saved to %s", path)
        return path
