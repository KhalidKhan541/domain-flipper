from __future__ import annotations

import logging
import smtplib
import socket
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from src.config import settings
from src.utils.logger import setup_logger
from src.outreach.template_generator import TemplateGenerator


class EmailSender:
    """Sends outreach emails directly via Gmail SMTP."""

    def __init__(self) -> None:
        self.logger = setup_logger("EmailSender")
        self.enabled = bool(
            settings.smtp_host and settings.smtp_user and settings.smtp_pass
        )
        self._dns_cache: dict[str, bool] = {}
        self.template_gen = TemplateGenerator()

    def _domain_exists(self, domain: str) -> bool:
        """Check if a domain has DNS A/AAAA records (avoids bounces from fake domains)."""
        domain = domain.lower().strip()
        if domain in self._dns_cache:
            return self._dns_cache[domain]
        exists = True
        try:
            socket.getaddrinfo(domain, 25, socket.AF_INET)
        except (socket.gaierror, OSError):
            try:
                socket.getaddrinfo(domain, 25, socket.AF_INET6)
            except (socket.gaierror, OSError):
                exists = False
        self._dns_cache[domain] = exists
        if not exists:
            self.logger.warning("Domain does not resolve: %s", domain)
        return exists

    def _validate_email(self, email: str) -> bool:
        """Validate that the email's domain resolves to an IP."""
        if "@" not in email:
            self.logger.warning("Invalid email (no @): %s", email)
            return False
        domain = email.rsplit("@", 1)[1]
        return self._domain_exists(domain)

    def _build_message(
        self,
        to_email: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
    ) -> MIMEMultipart:
        """Build a MIME message supporting both plain text and HTML bodies."""
        msg = MIMEMultipart("alternative")
        msg["From"] = settings.smtp_user
        msg["To"] = to_email
        msg["Subject"] = subject
        if cc:
            msg["Cc"] = cc

        if body.strip().startswith("<"):
            msg.attach(MIMEText(body, "html"))
        else:
            msg.attach(MIMEText(body, "plain"))

        return msg

    def _send_via_smtp(self, msg: MIMEMultipart, recipients: list[str]) -> None:
        """Connect to Gmail SMTP and send the message."""
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
        try:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(settings.smtp_user, settings.smtp_pass)
            server.sendmail(settings.smtp_user, recipients, msg.as_string())
        finally:
            server.quit()

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
    ) -> bool:
        if not self.enabled:
            self.logger.warning("EmailSender is disabled")
            return False

        try:
            msg = self._build_message(to_email, subject, body, cc)
            recipients = [to_email]
            if cc:
                recipients.extend([addr.strip() for addr in cc.split(",")])

            self._send_via_smtp(msg, recipients)
            self.logger.info("Email sent successfully via SMTP to %s", to_email)
            return True
        except smtplib.SMTPException as e:
            self.logger.error("SMTP error sending to %s: %s", to_email, e)
            return False
        except Exception as e:
            self.logger.error("Unexpected error sending email to %s: %s", to_email, e)
            return False

    async def send_outreach(
        self,
        to_email: str,
        lead_type: str,
        domain: str,
        subject: str,
        body: str,
    ) -> bool:
        if not self.enabled:
            self.logger.warning("EmailSender is disabled")
            return False

        if not self._validate_email(to_email):
            self.logger.warning(
                "Skipping %s outreach for %s — invalid email domain: %s",
                lead_type, domain, to_email,
            )
            return False

        self.logger.info(
            "Sending %s outreach for %s to %s", lead_type, domain, to_email
        )
        success = await self.send_email(to_email=to_email, subject=subject, body=body)
        if success:
            self.logger.info(
                "Outreach sent successfully: %s - %s (%s)", domain, lead_type, to_email
            )
        else:
            self.logger.warning(
                "Outreach failed: %s - %s (%s)", domain, lead_type, to_email
            )
        return success

    async def send_buyer_outreach(
        self,
        to_email: str,
        domain: str,
        company_name: str,
        contact_name: str,
        estimated_value: int,
        niche: str = "general",
    ) -> bool:
        """Send personalized cold outreach email to potential domain buyer."""
        if not self.enabled:
            self.logger.warning("EmailSender is disabled")
            return False

        if not self._validate_email(to_email):
            self.logger.warning("Skipping buyer outreach — invalid email domain: %s", to_email)
            return False

        template = self.template_gen.buyer_outreach(
            domain=domain,
            company_name=company_name,
            contact_name=contact_name,
            estimated_value=estimated_value,
            niche=niche,
        )
        subject = template["subject"]
        body = template["body"]

        self.logger.info("Sending buyer outreach for %s to %s (%s)", domain, to_email, company_name)
        success = await self.send_email(to_email=to_email, subject=subject, body=body)
        if success:
            self.logger.info("Buyer outreach sent: %s -> %s", domain, to_email)
        else:
            self.logger.warning("Buyer outreach failed: %s -> %s", domain, to_email)
        return success

    async def send_followup(
        self,
        to_email: str,
        domain: str,
        contact_name: str,
    ) -> bool:
        """Send follow-up email for a domain opportunity."""
        if not self.enabled:
            self.logger.warning("EmailSender is disabled")
            return False

        if not self._validate_email(to_email):
            self.logger.warning("Skipping followup — invalid email domain: %s", to_email)
            return False

        subject = f"Following up: {domain}"
        body = (
            f"Hi {contact_name},\n\n"
            f"I wanted to follow up on my previous email about {domain}.\n\n"
            f"This premium domain is still available and could be a great fit for your business. "
            f"Would you be open to a quick chat about it?\n\n"
            f"Best regards,\n"
            f"{settings.smtp_user}"
        )

        self.logger.info("Sending followup for %s to %s", domain, to_email)
        success = await self.send_email(to_email=to_email, subject=subject, body=body)
        if success:
            self.logger.info("Followup sent: %s -> %s", domain, to_email)
        else:
            self.logger.warning("Followup failed: %s -> %s", domain, to_email)
        return success
