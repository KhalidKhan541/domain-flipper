"""
Domain Flipper — Autonomous Expired Domain Discovery Agent
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
from src.collectors import COLLECTORS
from src.analyzers import HistoryAnalyzer, SEOAnalyzer, CommercialAnalyzer, ScoringEngine
from src.notifiers import TelegramNotifier, DiscordNotifier, EmailNotifier
from src.reporting import MarkdownReportGenerator, CSVReportGenerator, JSONReportGenerator


class DomainFlipper:
    def __init__(self) -> None:
        self.logger: logging.Logger = setup_logger("DomainFlipper")
        self.db: Database = Database(settings.database_path)
        self.history_analyzer = HistoryAnalyzer()
        self.seo_analyzer = SEOAnalyzer()
        self.commercial_analyzer = CommercialAnalyzer()
        self.scoring_engine = ScoringEngine()
        self.notifiers: list[Any] = []
        self.reporters: list[Any] = []

    async def initialize(self) -> None:
        """Initialise database, notifiers and reporters."""
        await self.db.init_db()

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

    # ── Collection ──────────────────────────────────────────────────────

    async def collect_all(self) -> list[dict[str, Any]]:
        """Run all collectors in parallel."""
        all_domains: list[dict[str, Any]] = []
        tasks = []

        for collector_cls in COLLECTORS:
            collector = collector_cls(settings)
            tasks.append(self._safe_collect(collector))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            raw = COLLECTORS[i]
            source = raw.source if hasattr(raw, "source") else "unknown"
            if isinstance(result, Exception):
                self.logger.error("Collector %s failed: %s", source, result)
                await self.db.log_scrape(source, 0, "error", str(result))
            else:
                all_domains.extend(result)
                await self.db.log_scrape(source, len(result), "success")
                self.logger.info("Collected %d domains from %s", len(result), source)

        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for d in all_domains:
            name = d.get("domain_name", "")
            if name not in seen:
                seen.add(name)
                unique.append(d)

        self.logger.info("Total unique domains collected: %d", len(unique))
        return unique

    async def _safe_collect(self, collector: Any) -> list[dict[str, Any]]:
        try:
            return await collector.collect()
        except Exception:
            raise

    # ── Analysis ────────────────────────────────────────────────────────

    async def analyze_all(self, domains: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Run all analyzers on collected domains."""
        self.logger.info("Analyzing %d domains…", len(domains))

        semaphore = asyncio.Semaphore(10)

        async def analyze_one(domain: dict[str, Any]) -> dict[str, Any] | None:
            async with semaphore:
                try:
                    name = domain["domain_name"]

                    history_task = self.history_analyzer.analyze(name)
                    seo_task = self.seo_analyzer.analyze(name)
                    commercial_task = self.commercial_analyzer.analyze(name)

                    history, seo, commercial = await asyncio.gather(
                        history_task, seo_task, commercial_task, return_exceptions=True
                    )

                    if isinstance(history, Exception):
                        self.logger.warning("History analysis failed for %s: %s", name, history)
                        history = {"cleanliness_score": 50, "trust_score": 50}
                    if isinstance(seo, Exception):
                        self.logger.warning("SEO analysis failed for %s: %s", name, seo)
                        seo = {
                            "dr": domain.get("dr", 0),
                            "referring_domains": domain.get("referring_domains", 0),
                            "domain_age": domain.get("domain_age", 0),
                            "seo_score": 0,
                        }
                    if isinstance(commercial, Exception):
                        self.logger.warning("Commercial analysis failed for %s: %s", name, commercial)
                        commercial = {"category": "general", "commercial_score": 50}

                    domain["dr"] = max(domain.get("dr", 0), seo.get("dr", 0))
                    domain["referring_domains"] = max(
                        domain.get("referring_domains", 0), seo.get("referring_domains", 0)
                    )
                    domain["domain_age"] = max(domain.get("domain_age", 0), seo.get("domain_age", 0))
                    domain["seo_score"] = seo.get("seo_score", 0)
                    domain["cleanliness_score"] = history.get("cleanliness_score", 50)
                    domain["trust_score"] = history.get("trust_score", 50)
                    domain["category"] = commercial.get("category", "general")
                    domain["commercial_score"] = commercial.get("commercial_score", 50)

                    result = self.scoring_engine.calculate(
                        domain=name,
                        price=domain.get("price", 0),
                        seo_score=domain["seo_score"],
                        commercial_score=domain["commercial_score"],
                        trust_score=domain["trust_score"],
                        cleanliness_score=domain["cleanliness_score"],
                    )

                    domain["final_score"] = result["final_score"]
                    domain["opportunity_grade"] = result["opportunity_grade"]
                    domain["reason"] = result.get("reason", "")

                    await self.db.save_domain(domain)

                    return domain

                except Exception as e:
                    self.logger.error("Failed to analyze %s: %s", domain.get("domain_name"), e)
                    return None

        tasks = [analyze_one(d) for d in domains]
        results = await asyncio.gather(*tasks)

        analyzed: list[dict[str, Any]] = [r for r in results if r is not None]
        analyzed.sort(key=lambda x: x.get("final_score", 0), reverse=True)

        self.logger.info("Analyzed %d domains successfully", len(analyzed))
        return analyzed

    # ── Reporting ───────────────────────────────────────────────────────

    async def generate_reports(self, domains: list[dict[str, Any]]) -> None:
        """Generate all report formats."""
        for reporter in self.reporters:
            try:
                content = await reporter.generate(domains)
                path = await reporter.save(content)
                self.logger.info("Report saved: %s", path)
            except Exception as e:
                self.logger.error("Report generation failed: %s", e)

    # ── Notifications ───────────────────────────────────────────────────

    async def send_notifications(self, domains: list[dict[str, Any]]) -> None:
        """Send reports via all enabled notifiers."""
        if not self.notifiers:
            self.logger.info("No notifiers enabled, skipping notifications")
            return

        report_lines = [
            f"Daily Domain Report - {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            f"Found {len(domains)} domains",
            "",
            "Top Domains:",
        ]
        for i, d in enumerate(domains[:10], 1):
            report_lines.append(
                f"{i}. {d['domain_name']} — ${d.get('price', 0)} — "
                f"Score: {d.get('final_score', 0)} — Grade: {d.get('opportunity_grade', 'N/A')}"
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

    # ── Main run ────────────────────────────────────────────────────────

    async def run(self) -> None:
        """Main execution flow."""
        start = datetime.now(timezone.utc)
        self.logger.info("=" * 50)
        self.logger.info("Domain Flipper run started at %s", start)
        self.logger.info("=" * 50)

        try:
            self.logger.info("Step 1/4: Collecting domains…")
            domains = await self.collect_all()

            if not domains:
                self.logger.warning("No domains collected, aborting")
                await self.send_notifications([])
                return

            self.logger.info("Step 2/4: Analyzing domains…")
            analyzed = await self.analyze_all(domains)

            if not analyzed:
                self.logger.warning("No domains passed analysis")
                await self.send_notifications([])
                return

            self.logger.info("Step 3/4: Generating reports…")
            await self.generate_reports(analyzed)

            self.logger.info("Step 4/4: Sending notifications…")
            await self.send_notifications(analyzed)

            elapsed = (datetime.now(timezone.utc) - start).total_seconds()
            self.logger.info("Run completed in %.1fs", elapsed)
            self.logger.info(
                "Results: %d domains analyzed, top grade: %s",
                len(analyzed),
                analyzed[0]["opportunity_grade"] if analyzed else "N/A",
            )

        except Exception as e:
            self.logger.error("Run failed: %s", e, exc_info=True)
        finally:
            await self.db.close()


async def main() -> None:
    flipper = DomainFlipper()
    await flipper.initialize()
    await flipper.run()


if __name__ == "__main__":
    asyncio.run(main())
