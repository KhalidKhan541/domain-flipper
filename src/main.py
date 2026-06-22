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
from src.trading import WalletManager, DomainVerifier, EscrowManager, DomainTransfer, CashoutManager


class DomainBroker:
    def __init__(self) -> None:
        self.logger: logging.Logger = setup_logger("DomainBroker")
        self.db: Database = Database(settings.database_path)
        self.coordinator = BrokerCoordinator(db=self.db)
        self.outbound = OutboundEngine(db_path=str(settings.database_path))
        self.broker_model = BrokerModel()
        self.notifiers: list[Any] = []
        self.reporters: list[Any] = []

        # Trading modules
        self.wallet = WalletManager()
        self.verifier = DomainVerifier()
        self.escrow = EscrowManager()
        self.transfer = DomainTransfer()
        self.cashout = CashoutManager()

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
            seller = d.get("owner_contact", {}).get("registrant_name", "N/A") or "N/A"
            report_lines.append(
                f"{i}. {d['domain_name']} — Est: ${est_value} — "
                f"Commission: ${commission} — Leads: {leads} — Grade: {broker_grade} — Seller: {seller}"
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

    # ------------------------------------------------------------------
    # Safe Trading Pipeline (No Bank Account)
    # ------------------------------------------------------------------

    async def setup_wallet(self) -> dict:
        """
        Step 1: Create crypto wallet for receiving payments.
        No bank account needed.
        """
        wallet = self.wallet.get_primary_wallet()
        if not wallet:
            wallet = self.wallet.create_wallet(
                wallet_type=settings.wallet_type,
                chain=settings.wallet_chain,
                notes="Primary wallet for domain trading",
            )
            self.logger.info(
                "Created %s wallet on %s: %s",
                wallet.wallet_type,
                wallet.chain,
                wallet.address[:10] + "...",
            )
        return self.wallet.get_status()

    async def find_domain(self, niche: str = "ai") -> dict:
        """
        Step 2: Find a domain to flip.
        Uses the existing domain discovery pipeline.
        """
        domains = await self.collect_all()
        if not domains:
            return {"error": "No domains found"}

        analyzed = await self.analyze_all(domains)
        if not analyzed:
            return {"error": "No domains passed analysis"}

        # Return top domain
        best = analyzed[0]
        return {
            "domain": best["domain_name"],
            "price": best.get("price"),
            "score": best.get("final_score"),
            "grade": best.get("opportunity_grade"),
            "estimated_value": best.get("estimated_value"),
            "commission": best.get("commission_amount"),
        }

    async def verify_domain(self, domain: str) -> dict:
        """
        Step 3: Verify domain ownership.
        Confirms the seller actually owns the domain.
        """
        result = await self.verifier.verify_ownership(domain)
        return {
            "domain": domain,
            "verified": result.verified,
            "confidence": result.confidence,
            "registrar": result.registrar,
            "registrant": result.registrant_name,
            "registration_date": result.registration_date,
            "expiration_date": result.expiration_date,
            "risk_flags": result.risk_flags,
            "method": result.verification_method,
        }

    async def create_escrow_deal(
        self,
        domain: str,
        buyer_address: str,
        seller_address: str,
        amount_usdc: float,
    ) -> dict:
        """
        Step 4: Create escrow deal.
        Buyer deposits USDC, seller transfers domain.
        """
        deal = await self.escrow.create_escrow(
            domain=domain,
            buyer_address=buyer_address,
            seller_address=seller_address,
            amount_usdc=amount_usdc,
            chain=settings.escrow_chain,
        )
        wallet = self.wallet.get_primary_wallet()
        return {
            "escrow_id": deal.escrow_id[:8],
            "domain": domain,
            "amount_usdc": amount_usdc,
            "status": deal.status,
            "deposit_address": wallet.address if wallet else "N/A",
            "instructions": (
                f"Buyer: Send {amount_usdc} USDC to escrow contract.\n"
                f"Then seller transfers domain.\n"
                f"Escrow releases funds after buyer confirms receipt."
            ),
        }

    async def transfer_domain(
        self,
        domain: str,
        from_registrar: str,
        to_registrar: str,
    ) -> dict:
        """
        Step 5/6: Transfer domain from seller to buyer.
        """
        record = await self.transfer.initiate_transfer(
            domain=domain,
            from_registrar=from_registrar,
            to_registrar=to_registrar,
            from_account="seller",
            to_account="buyer",
        )

        guide = self.transfer.get_transfer_guide(domain, from_registrar)

        return {
            "transfer_id": record.transfer_id[:8],
            "domain": domain,
            "status": record.status,
            "transfer_guide": guide,
            "next_steps": [
                "1. Seller unlocks domain at registrar",
                "2. Seller gets EPP/authorization code",
                "3. Seller shares code with buyer",
                "4. Buyer initiates transfer at their registrar",
                "5. Wait 5-7 business days for completion",
            ],
        }

    async def cashout_profits(self, amount_usdc: float) -> dict:
        """
        Step 8: Convert USDC to local currency via P2P.
        No bank account needed for P2P trades.
        """
        order = await self.cashout.create_cashout_order(
            amount_usdc=amount_usdc,
            method=settings.cashout_method,
            currency=settings.cashout_currency,
            payment_method=settings.cashout_payment_method,
        )

        rate = await self.cashout.get_p2p_rate(
            method=settings.cashout_method,
            currency=settings.cashout_currency,
        )

        guide = self.cashout.get_cashout_guide()

        return {
            "order_id": order.order_id[:8],
            "amount_usdc": amount_usdc,
            "method": settings.cashout_method,
            "currency": settings.cashout_currency,
            "rate": rate,
            "guide": guide.get(settings.cashout_method, {}),
            "next_steps": [
                f"1. Go to {settings.cashout_method.replace('_', ' ').title()}",
                f"2. Create sell order for {amount_usdc} USDC",
                f"3. Set payment method: {settings.cashout_payment_method}",
                "4. Wait for buyer",
                "5. Confirm payment received",
                "6. Release USDC to buyer",
            ],
        }

    async def run_safe_trading_pipeline(self, domain: str, price_usd: float) -> dict:
        """
        Run the complete safe trading workflow:
        1. Setup wallet
        2. Verify domain ownership
        3. Create escrow deal
        4. Guide domain transfer
        5. Confirm and release
        6. Cashout profits
        """
        self.logger.info("=" * 50)
        self.logger.info("SAFE TRADING PIPELINE: %s", domain)
        self.logger.info("=" * 50)

        results = {}

        # Step 1: Wallet
        self.logger.info("Step 1: Setting up wallet...")
        wallet_status = await self.setup_wallet()
        results["wallet"] = wallet_status

        # Step 2: Verify
        self.logger.info("Step 2: Verifying domain ownership...")
        verification = await self.verify_domain(domain)
        results["verification"] = verification

        if not verification.get("verified"):
            self.logger.warning(
                "Domain verification failed (confidence: %.2f). Proceed with caution.",
                verification.get("confidence", 0),
            )

        # Step 3: Escrow
        self.logger.info("Step 3: Creating escrow deal...")
        wallet = self.wallet.get_primary_wallet()
        escrow_deal = await self.create_escrow_deal(
            domain=domain,
            buyer_address="BUYER_ADDRESS_HERE",
            seller_address=wallet.address if wallet else "SELLER_ADDRESS_HERE",
            amount_usdc=price_usd,
        )
        results["escrow"] = escrow_deal

        # Step 4: Transfer guide
        self.logger.info("Step 4: Domain transfer guide...")
        transfer_guide = await self.transfer_domain(
            domain=domain,
            from_registrar=verification.get("registrar", "unknown"),
            to_registrar=settings.preferred_registrar,
        )
        results["transfer"] = transfer_guide

        self.logger.info("Safe trading pipeline completed for %s", domain)
        return results

    async def get_trading_status(self) -> dict:
        """Get status of all trading components."""
        return {
            "wallet": self.wallet.get_status(),
            "escrow": self.escrow.get_status(),
            "transfers": self.transfer.get_status(),
            "cashout": self.cashout.get_status(),
            "active_escrows": len(self.escrow.list_active_deals()),
            "active_transfers": len(self.transfer.list_active_transfers()),
            "active_cashouts": len(self.cashout.list_active_orders()),
        }


async def main() -> None:
    broker = DomainBroker()
    await broker.initialize()
    await broker.run()


if __name__ == "__main__":
    asyncio.run(main())
