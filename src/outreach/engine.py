from __future__ import annotations

import asyncio
from typing import Any, Optional
from src.config import settings
from src.utils import setup_logger
from src.outreach.owner_extractor import OwnerExtractor
from src.outreach.buyer_enricher import BuyerEnricher
from src.outreach.template_generator import TemplateGenerator
from src.outreach.commission_agreement import CommissionAgreementGenerator
from src.outreach.tracker import OutreachTracker
from src.outreach.email_sender import EmailSender


class OutboundEngine:
    """Orchestrates the full outbound pipeline for domain brokering.

    For each domain:
    1. Extract owner (seller) contact info
    2. Enrich buyer leads with LinkedIn + email
    3. Generate outreach templates for buyers
    4. Generate outreach templates for seller
    5. Save all leads to tracker
    6. Generate commission agreement
    """

    def __init__(self, db_path: str = "data/domains.db"):
        self.logger = setup_logger("OutboundEngine")
        self.owner_extractor = OwnerExtractor()
        self.buyer_enricher = BuyerEnricher()
        self.template_gen = TemplateGenerator()
        self.commission_gen = CommissionAgreementGenerator()
        self.email_sender = EmailSender()
        self.tracker = OutreachTracker(db_path)

    async def initialize(self):
        await self.tracker.init_db()

    async def process_domains(self, domains: list[dict], max_count: int = 20) -> list[dict]:
        """Run full outbound pipeline on analyzed domains. Returns enriched domains."""
        top = sorted(domains, key=lambda d: d.get("broker_score", 0), reverse=True)[:max_count]
        await asyncio.gather(*(self._process_one(d) for d in top))
        return top

    async def _process_one(self, domain: dict) -> None:
        domain_name: str = domain.get("domain_name", "") or domain.get("domain", "")
        niche: str = domain.get("niche", "general")
        estimated_value: int = domain.get("estimated_value", 0) or 0
        leads: list[dict] = domain.get("buyer_leads", {}).get("leads", [])

        self.logger.info("Processing domain: %s (niche=%s, value=$%d)", domain_name, niche, estimated_value)

        owner = await self._extract_owner(domain_name)
        if owner:
            domain["owner_contact"] = owner

        enriched = await self._enrich_buyers(leads, domain_name, niche)
        if enriched:
            domain["enriched_buyers"] = enriched

        await self._generate_seller_outreach(domain_name, owner, estimated_value, domain)
        await self._generate_buyer_outreach(domain_name, niche, estimated_value, enriched)

        if owner and enriched:
            await self._generate_agreement(domain_name, owner, enriched, estimated_value, domain)

        await self._send_seller_email(domain_name, owner, domain)
        await self._send_buyer_emails(domain_name, enriched)

        self.logger.info("Finished processing domain: %s", domain_name)

    async def _send_seller_email(self, domain_name: str, owner: dict | None, domain: dict) -> None:
        if not owner or owner.get("status") != "found":
            return
        seller_email = owner.get("registrant_email", "")
        template = domain.get("seller_template")
        if not seller_email or not template:
            return
        success = await self.email_sender.send_outreach(
            to_email=seller_email,
            lead_type="seller",
            domain=domain_name,
            subject=template.get("subject", ""),
            body=template.get("body", ""),
        )
        lead_id = domain.get("seller_lead_id")
        if success and lead_id:
            await self.tracker.update_status(lead_id, status="sent")
            self.logger.info("Seller email sent for %s", domain_name)

    async def _send_buyer_emails(self, domain_name: str, enriched: list[dict]) -> None:
        for buyer in enriched:
            email = buyer.get("contact_email", "")
            template = buyer.get("template")
            lead_id = buyer.get("lead_id")
            if not email or not template or not lead_id:
                continue
            success = await self.email_sender.send_outreach(
                to_email=email,
                lead_type="buyer",
                domain=domain_name,
                subject=template.get("subject", ""),
                body=template.get("body", ""),
            )
            if success:
                await self.tracker.update_status(lead_id, status="sent")
                self.logger.info("Buyer email sent for %s -> %s", domain_name, email)

    async def _extract_owner(self, domain_name: str) -> dict | None:
        try:
            owner = await self.owner_extractor.extract(domain_name)
            self.logger.info("Owner for %s: status=%s, name=%s", domain_name, owner.get("status"), owner.get("registrant_name"))
            return owner
        except Exception as exc:
            self.logger.error("Owner extraction failed for %s: %s", domain_name, exc)
            return None

    async def _enrich_buyers(self, leads: list[dict], domain_name: str, niche: str) -> list[dict]:
        if not leads:
            return []
        try:
            enriched = await self.buyer_enricher.enrich(leads, domain_name, niche)
            self.logger.info("Enriched %d buyer leads for %s", len(enriched), domain_name)
            return enriched
        except Exception as exc:
            self.logger.error("Buyer enrichment failed for %s: %s", domain_name, exc)
            return []

    async def _generate_seller_outreach(self, domain_name: str, owner: dict | None, estimated_value: int, domain: dict) -> None:
        if not owner or owner.get("status") != "found":
            self.logger.info("Skipping seller outreach for %s — no owner contact", domain_name)
            return

        seller_name: str = owner.get("registrant_name") or owner.get("registrant_org") or "Domain Owner"
        seller_org: str = owner.get("registrant_org") or owner.get("registrant_name") or "Unknown"
        seller_email: str = owner.get("registrant_email", "")

        try:
            template = self.template_gen.seller_outreach(domain_name, seller_name, estimated_value)
        except Exception as exc:
            self.logger.error("Seller template generation failed for %s: %s", domain_name, exc)
            return

        try:
            lead_id = await self.tracker.add_lead(
                domain_name=domain_name,
                lead_type="seller",
                company=seller_org,
                contact_name=seller_name,
                contact_title="",
                contact_email=seller_email,
                template_subject=template.get("subject", ""),
                template_body=template.get("body", ""),
            )
            domain["seller_lead_id"] = lead_id
            domain["seller_template"] = template
            self.logger.info("Saved seller lead for %s (id=%d)", domain_name, lead_id)
        except Exception as exc:
            self.logger.error("Failed to save seller lead for %s: %s", domain_name, exc)

    async def _generate_buyer_outreach(self, domain_name: str, niche: str, estimated_value: int, enriched: list[dict]) -> None:
        for buyer in enriched:
            buyer_company: str = buyer.get("company", "Unknown")
            buyer_name: str = buyer.get("contact_name") or buyer_company

            try:
                template = self.template_gen.buyer_outreach(domain_name, buyer_company, buyer_name, estimated_value, niche)
                buyer["template"] = template
            except Exception as exc:
                self.logger.error("Buyer template gen failed for %s / %s: %s", domain_name, buyer_company, exc)
                template = None

            try:
                lead_id = await self.tracker.add_lead(
                    domain_name=domain_name,
                    lead_type="buyer",
                    company=buyer_company,
                    contact_name=buyer_name,
                    contact_title=buyer.get("contact_title", ""),
                    contact_email=buyer.get("contact_email", ""),
                    contact_linkedin=buyer.get("contact_linkedin", ""),
                    template_subject=template.get("subject", "") if template else "",
                    template_body=template.get("body", "") if template else "",
                )
                buyer["lead_id"] = lead_id
            except Exception as exc:
                self.logger.error("Failed to save buyer lead for %s / %s: %s", domain_name, buyer_company, exc)

    async def _generate_agreement(self, domain_name: str, owner: dict, enriched: list[dict], estimated_value: int, domain: dict) -> None:
        first = enriched[0]
        buyer_name: str = first.get("contact_name") or first.get("company", "Buyer")
        buyer_company: str = first.get("company", "Buyer Company")
        seller_name: str = owner.get("registrant_name") or owner.get("registrant_org") or "Seller"
        seller_company: str = owner.get("registrant_org") or seller_name

        commission_rate: float = 0.10
        commission_amount: int = int(estimated_value * commission_rate)

        try:
            html = await self.commission_gen.generate(
                domain=domain_name,
                buyer_name=buyer_name,
                buyer_company=buyer_company,
                seller_name=seller_name,
                seller_company=seller_company,
                commission_amount=commission_amount,
                commission_rate=commission_rate,
                estimated_value=estimated_value,
            )
            path = await self.commission_gen.save(html, domain_name)

            await self.tracker.save_agreement(
                domain_name=domain_name,
                buyer_name=buyer_name,
                buyer_company=buyer_company,
                seller_name=seller_name,
                seller_company=seller_company,
                commission_amount=commission_amount,
                commission_rate=commission_rate,
                estimated_value=estimated_value,
                agreement_path=str(path),
            )

            domain["agreement_path"] = str(path)
            self.logger.info("Commission agreement saved for %s at %s", domain_name, path)
        except Exception as exc:
            self.logger.error("Failed to generate commission agreement for %s: %s", domain_name, exc)

    async def shutdown(self):
        await self.tracker.close()
