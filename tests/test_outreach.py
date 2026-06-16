import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.outreach.owner_extractor import OwnerExtractor, MOCK_OWNER_DATA
from src.outreach.buyer_enricher import BuyerEnricher, MOCK_CONTACTS
from src.outreach.template_generator import TemplateGenerator
from src.outreach.commission_agreement import CommissionAgreementGenerator
from src.outreach.tracker import OutreachTracker
from src.outreach.email_sender import EmailSender


@pytest.mark.asyncio
class TestOwnerExtractor:
    async def test_extract_returns_all_required_fields(self):
        with patch("src.outreach.owner_extractor.settings") as mock_settings:
            mock_settings.offline_mode = True
            extractor = OwnerExtractor()
            result = await extractor.extract("google.com")
            assert result["domain"] == "google.com"
            assert result["registrant_name"] == "Google LLC"
            assert result["registrant_org"] == "Google LLC"
            assert result["registrant_email"] == "domsreg@google.com"
            assert result["registrar"] == "MarkMonitor, Inc."
            assert result["status"] == "found"

    async def test_offline_mode_returns_mock_data_for_known_domain(self):
        with patch("src.outreach.owner_extractor.settings") as mock_settings:
            mock_settings.offline_mode = True
            extractor = OwnerExtractor()
            result = await extractor.extract("stripe.com")
            assert result["registrant_name"] == "Stripe, Inc."
            assert result["registrant_email"] == "domains@stripe.com"

    async def test_offline_mode_falls_back_to_default_mock_for_unknown_domain(self):
        with patch("src.outreach.owner_extractor.settings") as mock_settings:
            mock_settings.offline_mode = True
            extractor = OwnerExtractor()
            result = await extractor.extract("nonexistent.xyz")
            assert result["domain"] == "nonexistent.xyz"
            assert result["registrant_name"] is not None
            assert result["status"] == "found"

    async def test_extract_unknown_tld_returns_not_found(self):
        with patch("src.outreach.owner_extractor.settings") as mock_settings:
            mock_settings.offline_mode = False
            extractor = OwnerExtractor()
            result = await extractor.extract("example.unknown")
            assert result["domain"] == "example.unknown"
            assert result["status"] == "not_found"
            assert result["registrant_name"] is None


@pytest.mark.asyncio
class TestBuyerEnricher:
    async def test_enrich_returns_all_required_fields_with_mock_contacts(self):
        with patch("src.outreach.buyer_enricher.settings") as mock_settings:
            mock_settings.offline_mode = True
            enricher = BuyerEnricher()
            leads = [{"company": "OpenAI"}]
            result = await enricher.enrich(leads, "example.com", "ai")
            assert len(result) == 1
            item = result[0]
            assert item["company"] == "OpenAI"
            assert item["contact_name"] == "Sam Altman"
            assert item["contact_title"] == "CEO"
            assert item["contact_email"] == "sam@openai.com"
            assert item["contact_linkedin"] == "https://linkedin.com/in/samaltman"
            assert item["confidence"] == "high"

    async def test_enrich_handles_empty_leads_list(self):
        with patch("src.outreach.buyer_enricher.settings") as mock_settings:
            mock_settings.offline_mode = True
            enricher = BuyerEnricher()
            result = await enricher.enrich([], "example.com", "ai")
            assert result == []

    async def test_known_company_gets_correct_mock_contact(self):
        with patch("src.outreach.buyer_enricher.settings") as mock_settings:
            mock_settings.offline_mode = True
            enricher = BuyerEnricher()
            leads = [{"company": "Cloudflare"}]
            result = await enricher.enrich(leads, "example.com", "cybersecurity")
            item = result[0]
            assert item["contact_name"] == "Matthew Prince"
            assert item["contact_email"] == "matthew@cloudflare.com"

    async def test_unknown_company_gets_generated_contact(self):
        with patch("src.outreach.buyer_enricher.settings") as mock_settings:
            mock_settings.offline_mode = True
            enricher = BuyerEnricher()
            leads = [{"company": "TotallyFakeCompany Inc."}]
            result = await enricher.enrich(leads, "example.com", "ai")
            item = result[0]
            assert item["contact_name"] == "TotallyFakeCompany Inc. Team"
            assert item["contact_title"] == "Director"
            assert item["confidence"] == "generated"
            assert "hello" in item["contact_email"]

    async def test_enrich_preserves_lead_fields(self):
        with patch("src.outreach.buyer_enricher.settings") as mock_settings:
            mock_settings.offline_mode = True
            enricher = BuyerEnricher()
            leads = [{"company": "OpenAI", "extra_field": "value"}]
            result = await enricher.enrich(leads, "example.com", "ai")
            assert result[0]["extra_field"] == "value"


@pytest.mark.asyncio
class TestTemplateGenerator:
    async def test_buyer_outreach_returns_subject_and_body(self):
        gen = TemplateGenerator()
        result = gen.buyer_outreach(
            domain="example.com",
            buyer_company="TestCorp",
            buyer_name="John",
            estimated_value=5000,
            niche="saas",
        )
        assert "subject" in result
        assert "body" in result
        assert "example.com" in result["body"]
        assert "John" in result["body"]
        assert "TestCorp" in result["body"]
        assert "$5,000" in result["body"]
        assert "saas" in result["body"]

    async def test_seller_outreach_returns_subject_and_body(self):
        gen = TemplateGenerator()
        result = gen.seller_outreach(
            domain="example.com",
            seller_name="Jane",
            estimated_value=10000,
        )
        assert "subject" in result
        assert "body" in result
        assert "example.com" in result["body"]
        assert "Jane" in result["body"]
        assert "$10,000" in result["body"]

    async def test_follow_up_returns_different_body_for_different_attempts(self):
        gen = TemplateGenerator()
        r1 = gen.follow_up("Re: Domain opportunity", "example.com", "TestCorp", attempt=1)
        r2 = gen.follow_up("Re: Domain opportunity", "example.com", "TestCorp", attempt=2)
        r3 = gen.follow_up("Re: Domain opportunity", "example.com", "TestCorp", attempt=3)
        r4 = gen.follow_up("Re: Domain opportunity", "example.com", "TestCorp", attempt=4)
        assert r1["body"] != r2["body"]
        assert r2["body"] != r3["body"]
        assert r3["body"] != r4["body"]
        assert "follow up" in r1["body"].lower()
        assert "circling back" in r2["body"].lower()
        assert "miss out" in r3["body"].lower()
        assert "final follow-up" in r4["body"].lower()

    async def test_linkedin_message_returns_short_string(self):
        gen = TemplateGenerator()
        result = gen.linkedin_message(
            domain="example.com",
            buyer_company="TestCorp",
            buyer_name="John",
        )
        assert isinstance(result, str)
        assert "example.com" in result
        assert "TestCorp" in result
        assert "John" in result
        assert len(result) < 300


@pytest.mark.asyncio
class TestCommissionAgreementGenerator:
    async def test_generate_returns_html_with_domain_name(self):
        gen = CommissionAgreementGenerator()
        html = await gen.generate(
            domain="example.com",
            buyer_name="John Buyer",
            buyer_company="BuyerCorp",
            seller_name="Jane Seller",
            seller_company="SellerCorp",
            commission_amount=1500,
            commission_rate=0.15,
            estimated_value=10000,
        )
        assert "<!DOCTYPE html>" in html
        assert "example.com" in html
        assert "John Buyer" in html
        assert "BuyerCorp" in html
        assert "Jane Seller" in html
        assert "SellerCorp" in html
        assert "$1,500" in html
        assert "$10,000" in html
        assert "15%" in html or "0%" in html
        assert "Domain Flipper Brokerage" in html

    async def test_save_writes_file_and_cleans_up(self):
        gen = CommissionAgreementGenerator()
        html = await gen.generate(
            domain="testagreement.com",
            buyer_name="Buyer",
            buyer_company="BCorp",
            seller_name="Seller",
            seller_company="SCorp",
            commission_amount=750,
            commission_rate=0.10,
            estimated_value=7500,
        )
        filepath = await gen.save(html, "testagreement.com")
        assert filepath.exists()
        content = filepath.read_text(encoding="utf-8")
        assert "testagreement.com" in content
        filepath.unlink()
        parent = filepath.parent
        if parent.exists() and not any(parent.iterdir()):
            parent.rmdir()


@pytest.mark.asyncio
class TestOutreachTracker:
    async def _make_tracker(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db_path = tmp.name
        tmp.close()
        tracker = OutreachTracker(db_path=db_path)
        await tracker.init_db()
        return tracker, db_path

    async def test_add_lead_returns_id(self):
        tracker, db_path = await self._make_tracker()
        try:
            lead_id = await tracker.add_lead(
                domain_name="example.com",
                lead_type="buyer",
                company="TestCorp",
                contact_name="John",
                contact_email="john@test.com",
            )
            assert isinstance(lead_id, int)
            assert lead_id > 0
        finally:
            await tracker.close()
            os.unlink(db_path)

    async def test_update_status_updates_status(self):
        tracker, db_path = await self._make_tracker()
        try:
            lead_id = await tracker.add_lead(
                domain_name="example.com",
                lead_type="buyer",
                company="TestCorp",
            )
            await tracker.update_status(lead_id, status="sent")
            pending = await tracker.get_pending()
            assert any(l["id"] == lead_id and l["status"] == "sent" for l in pending)
        finally:
            await tracker.close()
            os.unlink(db_path)

    async def test_get_pending_returns_pending_leads(self):
        tracker, db_path = await self._make_tracker()
        try:
            await tracker.add_lead(domain_name="pending.com", lead_type="buyer", company="PCorp")
            await tracker.add_lead(domain_name="sent.com", lead_type="buyer", company="SCorp")
            await tracker.add_lead(domain_name="done.com", lead_type="seller", company="DCorp")
            leads = await tracker.get_all()
            for l in leads:
                if l["domain_name"] == "sent.com":
                    await tracker.update_status(l["id"], status="sent")
                elif l["domain_name"] == "done.com":
                    await tracker.update_status(l["id"], status="replied")
            pending = await tracker.get_pending()
            statuses = [l["status"] for l in pending]
            assert all(s in ("pending", "sent") for s in statuses)
        finally:
            await tracker.close()
            os.unlink(db_path)

    async def test_get_by_domain_returns_filtered_leads(self):
        tracker, db_path = await self._make_tracker()
        try:
            await tracker.add_lead(domain_name="filter.com", lead_type="buyer", company="FCorp")
            await tracker.add_lead(domain_name="other.com", lead_type="seller", company="OCorp")
            results = await tracker.get_by_domain("filter.com")
            assert len(results) == 1
            assert results[0]["domain_name"] == "filter.com"
        finally:
            await tracker.close()
            os.unlink(db_path)

    async def test_get_all_returns_all_leads(self):
        tracker, db_path = await self._make_tracker()
        try:
            await tracker.add_lead(domain_name="a.com", lead_type="buyer", company="ACorp")
            await tracker.add_lead(domain_name="b.com", lead_type="seller", company="BCorp")
            results = await tracker.get_all()
            assert len(results) >= 2
        finally:
            await tracker.close()
            os.unlink(db_path)

    async def test_add_lead_with_minimal_fields(self):
        tracker, db_path = await self._make_tracker()
        try:
            lead_id = await tracker.add_lead(
                domain_name="minimal.com",
                lead_type="buyer",
                company="MinimalCorp",
            )
            assert isinstance(lead_id, int)
            results = await tracker.get_by_domain("minimal.com")
            assert len(results) == 1
            assert results[0]["status"] == "pending"
        finally:
            await tracker.close()
            os.unlink(db_path)

    async def test_update_status_with_timestamps(self):
        tracker, db_path = await self._make_tracker()
        try:
            lead_id = await tracker.add_lead(
                domain_name="timestamp.com",
                lead_type="buyer",
                company="TSCorp",
            )
            await tracker.update_status(
                lead_id,
                status="sent",
                message_sent="2025-01-01T00:00:00",
                notes="First outreach",
            )
            results = await tracker.get_by_domain("timestamp.com")
            assert results[0]["message_sent"] == "2025-01-01T00:00:00"
            assert results[0]["notes"] == "First outreach"
            assert results[0]["status"] == "sent"
        finally:
            await tracker.close()
            os.unlink(db_path)


@pytest.mark.asyncio
class TestEmailSender:
    async def test_send_email_disabled_returns_false_when_smtp_not_configured(self):
        with patch("src.outreach.email_sender.settings") as mock_settings:
            mock_settings.smtp_host = None
            mock_settings.smtp_user = None
            mock_settings.smtp_pass = None
            mock_settings.email_from = None
            sender = EmailSender()
            result = await sender.send_email(
                to_email="test@example.com",
                subject="Test",
                body="Test body",
            )
            assert result is False

    async def test_send_outreach_disabled_returns_false(self):
        with patch("src.outreach.email_sender.settings") as mock_settings:
            mock_settings.smtp_host = None
            mock_settings.smtp_user = None
            mock_settings.smtp_pass = None
            mock_settings.email_from = None
            sender = EmailSender()
            result = await sender.send_outreach(
                to_email="test@example.com",
                lead_type="buyer",
                domain="example.com",
                subject="Test",
                body="Test body",
            )
            assert result is False

    async def test_email_sender_init_returns_instance(self):
        sender = EmailSender()
        assert sender is not None
        assert hasattr(sender, "send_email")
        assert hasattr(sender, "send_outreach")
