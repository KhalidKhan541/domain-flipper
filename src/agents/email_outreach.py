"""Subagent 6: Sends outreach emails to domain sellers."""

from __future__ import annotations

import asyncio
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

from src.config import settings
from src.utils import setup_logger

SELLER_TEMPLATE = """\
Hi {contact_name},

I came across {domain} and I'm interested in acquiring it on behalf of my client.

My client is actively looking for premium domains in the {niche} space, and {domain} would be a great fit for their portfolio.

Would you be open to discussing a sale? We can work through Escrow.com for a safe, verified transaction.

Looking forward to hearing from you.

Best regards,
Khalid Khan
Domain Broker
Email: {email_from}
"""

SELLER_TEMPLATE_NO_NAME = """\
Hello,

I noticed that {domain} might be available for sale. I have a client who is actively looking to acquire premium domains in the {niche} space.

Would you be open to discussing a potential sale? We can use Escrow.com for a secure transaction.

Please let me know if you're interested.

Best regards,
Khalid Khan
Domain Broker
Email: {email_from}
"""


def _build_message(to_email: str, subject: str, body: str) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["From"] = settings.smtp_user
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    return msg


def _send_email(to_email: str, subject: str, body: str) -> bool:
    """Send email via SMTP (synchronous)."""
    if not settings.smtp_host or not settings.smtp_user or not settings.smtp_pass:
        return False

    try:
        msg = _build_message(to_email, subject, body)
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
        try:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(settings.smtp_user, settings.smtp_pass)
            server.sendmail(settings.smtp_user, [to_email], msg.as_string())
        finally:
            server.quit()
        return True
    except Exception:
        return False


def _generate_subject(domain: str, contact_name: str) -> str:
    """Generate a personalized email subject."""
    subjects = [
        f"Premium Domain Inquiry: {domain}",
        f"Domain Acquisition - {domain}",
        f"Interested in {domain}",
        f"Quick Question About {domain}",
        f"{domain} - Purchase Inquiry",
    ]
    # Use domain name to pick a consistent subject
    idx = hash(domain) % len(subjects)
    return subjects[idx]


def _generate_body(domain: str, contact_name: str, niche: str) -> str:
    """Generate personalized email body."""
    if contact_name and contact_name.lower() not in ("", "none", "redacted", "privacy protect"):
        return SELLER_TEMPLATE.format(
            contact_name=contact_name,
            domain=domain,
            niche=niche or "tech",
            email_from=settings.smtp_user,
        )
    return SELLER_TEMPLATE_NO_NAME.format(
        domain=domain,
        niche=niche or "tech",
        email_from=settings.smtp_user,
    )


async def run(domains: list[dict], dry_run: bool = False) -> list[dict]:
    """Send outreach emails to sellers of the given domains."""
    logger = setup_logger("EmailOutreach")
    sent = []
    skipped = []
    failed = []

    # Track which emails we've already sent to (avoid duplicates)
    sent_emails: set[str] = set()

    for domain_info in domains:
        domain = domain_info.get("domain_name", "")
        emails = domain_info.get("seller_emails", [])
        contact_name = domain_info.get("registrant_name", "")
        niche = domain_info.get("category", domain_info.get("niche", "tech"))
        estimated_value = domain_info.get("estimated_value", 0)

        if not emails:
            skipped.append({"domain": domain, "reason": "no_email"})
            continue

        # Only email domains worth > $100
        if estimated_value < 100:
            skipped.append({"domain": domain, "reason": f"low_value_${estimated_value}"})
            continue

        for email in emails:
            if not email or "@" not in email:
                continue
            if email in sent_emails:
                continue

            subject = _generate_subject(domain, contact_name)
            body = _generate_body(domain, contact_name, niche)

            if dry_run:
                logger.info("[DRY RUN] Would send to %s: %s", email, subject)
                sent.append({"domain": domain, "email": email, "dry_run": True})
                sent_emails.add(email)
                continue

            try:
                success = await asyncio.get_event_loop().run_in_executor(
                    None, _send_email, email, subject, body
                )
                if success:
                    logger.info("Email sent to %s for %s", email, domain)
                    sent.append({"domain": domain, "email": email, "success": True})
                    sent_emails.add(email)
                else:
                    logger.warning("Email failed to %s for %s", email, domain)
                    failed.append({"domain": domain, "email": email})
            except Exception as e:
                logger.error("Error sending to %s: %s", email, e)
                failed.append({"domain": domain, "email": email, "error": str(e)})

    # Save outreach log
    log_path = Path("data/outreach_log.json")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_entry = {
        "sent": len(sent),
        "skipped": len(skipped),
        "failed": len(failed),
        "domains": sent,
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(log_entry) + "\n")

    logger.info("Outreach complete: %d sent, %d skipped, %d failed", len(sent), len(skipped), len(failed))
    return {"sent": sent, "skipped": skipped, "failed": failed}
