"""
Domain Broker — Autonomous Domain Brokering Agent
Run: python -m src.main
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from src.config import settings
from src.utils import setup_logger
from src.database import Database
from src.coordinators.broker import BrokerCoordinator
from src.notifiers import TelegramNotifier, DiscordNotifier, EmailNotifier
from src.outreach.engine import OutboundEngine
from src.outreach.broker_model import BrokerModel
from src.reporting import MarkdownReportGenerator, CSVReportGenerator, JSONReportGenerator


class DomainBroker:
    def __init__(self) -> None:
        self.logger: logging.Logger = setup_logger("DomainBroker")
        self.db: Database = Database(settings.database_path)
        self.coordinator = BrokerCoordinator(db=self.db)
        self.outbound = OutboundEngine(db_path=str(settings.database_path))
        self.broker_model = BrokerModel()
        self.notifiers: list[Any] = []
        self.reporters: list[Any] = []

    async def initialize(self) -> None:
        await self.db.init_db()

        # Initialize outbound engine
        await self.outbound.initialize()

        tg = TelegramNotifier()
        dc = DiscordNotifier()
        em = EmailNotifier()
        for n in (tg, dc, em):
            if n.enabled:
                self.notifiers.append(n)

        self.reporters = [
            MarkdownReportGenerator(),
            CSVReportGenerator(),
            JSONReportGenerator(),
        ]

    async def collect_all(self) -> list[dict[str, Any]]:
        coordinator = BrokerCoordinator(db=self.db)
        domains = await coordinator.discover(max_domains=200)
        self.logger.info("Total domains collected: %d", len(domains))
        return domains

    async def analyze_all(self, domains: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return await self.coordinator.analyze_all(domains)

    async def generate_reports(self, domains: list[dict[str, Any]]) -> None:
        for reporter in self.reporters:
            try:
                content = await reporter.generate(domains)
                path = await reporter.save(content)
                self.logger.info("Report saved: %s", path)
            except Exception as e:
                self.logger.error("Report generation failed: %s", e)

    async def run_outbound(self, domains: list[dict]) -> list[dict]:
        return await self.outbound.process_domains(domains, max_count=settings.max_outbound_per_run)

    async def run_broker_pipeline(self) -> list[dict[str, Any]]:
        """Run zero-cost broker model across multiple niches."""
        niches = ["ai", "saas", "finance", "health", "ecommerce", "education", "security"]
        all_deals: list[dict[str, Any]] = []

        for niche in niches:
            try:
                result = await self.broker_model.run_broker_pipeline(niche)
                all_deals.extend(result.get("deals", []))
                self.logger.info(
                    "Broker pipeline for %s: %d buyers, %d sellers, %d deals",
                    niche,
                    result.get("buyers_found", 0),
                    result.get("sellers_found", 0),
                    result.get("deals_matched", 0),
                )
            except Exception as exc:
                self.logger.error("Broker pipeline failed for %s: %s", niche, exc)

        return all_deals

    async def send_notifications(self, domains: list[dict[str, Any]], broker_deals: list[dict[str, Any]] = None) -> None:
        if not self.notifiers:
            self.logger.info("No notifiers enabled, skipping notifications")
            return

        broker_deals = broker_deals or []

        report_lines = [
            f"Daily Broker Report - {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            f"Found {len(domains)} domain opportunities + {len(broker_deals)} broker deals",
            "",
            "Top Domain Opportunities:",
        ]
        for i, d in enumerate(domains[:10], 1):
            broker_grade = d.get("broker_grade", "N/A")
            est_value = d.get("estimated_value", 0)
            commission = d.get("commission", {}).get("amount", 0)
            leads = d.get("buyer_leads", {}).get("total_leads", 0)
            report_lines.append(
                f"{i}. {d['domain_name']} — Est: ${est_value} — "
                f"Commission: ${commission} — Leads: {leads} — Grade: {broker_grade}"
            )

        if broker_deals:
            report_lines.extend(["", "Zero-Cost Broker Deals:"])
            for i, deal in enumerate(broker_deals[:5], 1):
                report_lines.append(
                    f"{i}. {deal['domain']} — Price: ${deal['asking_price']} — "
                    f"Your Commission: ${deal['estimated_commission']}"
                )

        report_text = "\n".join(report_lines)

        for notifier in self.notifiers:
            try:
                success = await notifier.send_report(report_text, domains[:20])
                if success:
                    self.logger.info("Notification sent via %s", notifier.__class__.__name__)
            except Exception as e:
                self.logger.error(
                    "Notification failed for %s: %s", notifier.__class__.__name__, e
                )

    async def run(self) -> None:
        start = datetime.now(timezone.utc)
        self.logger.info("=" * 50)
        self.logger.info("Domain Broker run started at %s", start)
        self.logger.info("=" * 50)

        try:
            self.logger.info("Step 1/5: Collecting domains…")
            domains = await self.collect_all()

            if not domains:
                self.logger.warning("No domains collected, aborting")
                await self.send_notifications([])
                return

            self.logger.info("Step 2/5: Broker-analyzing domains…")
            analyzed = await self.analyze_all(domains)

            if not analyzed:
                self.logger.warning("No domains passed analysis")
                await self.send_notifications([])
                return

            self.logger.info("Step 3/5: Running outbound pipeline (online mode)…")
            original_offline = settings.offline_mode
            settings.offline_mode = False
            try:
                outbound_results = await self.run_outbound(analyzed)
            finally:
                settings.offline_mode = original_offline

            self.logger.info("Step 4/6: Running zero-cost broker pipeline…")
            broker_deals = await self.run_broker_pipeline()
            self.logger.info("Broker pipeline found %d deal opportunities", len(broker_deals))

            self.logger.info("Step 5/6: Generating reports…")
            await self.generate_reports(analyzed)

            self.logger.info("Step 6/6: Sending notifications…")
            await self.send_notifications(analyzed, broker_deals)

            elapsed = (datetime.now(timezone.utc) - start).total_seconds()
            self.logger.info("Run completed in %.1fs", elapsed)
            self.logger.info(
                "Results: %d domains analyzed, %d outreach attempts, %d broker deals, top broker grade: %s",
                len(analyzed),
                len(outbound_results),
                len(broker_deals),
                analyzed[0]["broker_grade"] if analyzed else "N/A",
            )

        except Exception as e:
            self.logger.error("Run failed: %s", e, exc_info=True)
        finally:
            await self.db.close()


async def main() -> None:
    broker = DomainBroker()
    await broker.initialize()
    await broker.run()


if __name__ == "__main__":
    asyncio.run(main())
