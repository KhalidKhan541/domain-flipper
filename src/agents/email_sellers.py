"""Agent 7: Email Sellers — contacts domain owners, offers to broker their domain."""

from __future__ import annotations

import asyncio
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from src.config import settings
from src.utils import setup_logger

SELLER_BROKER_TEMPLATE = """\
Hi {contact_name},

I noticed that {domain} is listed for sale / may be available. I specialize in connecting premium domain sellers with serious buyers.

I have clients actively looking for domains in the {niche} space, and I believe {domain} would be a great fit for them.

Would you be open to me brokering a deal on your behalf? I work on a commission basis — you only pay when the deal closes.

We can use Escrow.com for a secure, verified transaction.

Looking forward to hearing from you.

Best regards,
Khalid Khan
Domain Broker
khalid.khan46571@gmail.com
"""

SELLER_BROKER_NO_NAME = """\
Hello,

I came across {domain} and noticed it might be available for sale. I'm a domain broker who connects sellers with serious buyers.

I have clients actively looking for domains in the {niche} space. Would you be open to me brokering a deal on your behalf? I work on commission — you only pay when the deal closes.

We can use Escrow.com for a secure transaction.

Please let me know if you're interested.

Best regards,
Khalid Khan
Domain Broker
khalid.khan46571@gmail.com
"""


def _send_email(to_email: str, subject: str, body: str) -> bool:
    if not settings.smtp_host or not settings.smtp_user or not settings.smtp_pass:
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = settings.smtp_user
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

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


async def run(domains: list[dict], dry_run: bool = False) -> dict:
    """Contact domain sellers, offer to broker their domain."""
    logger = setup_logger("SellerOutreach")
    sent, skipped, failed = [], [], []
    sent_emails: set[str] = set()

    for d in domains:
        domain = d.get("domain_name", "")
        emails = d.get("seller_emails", [])
        name = d.get("registrant_name", "")
        niche = d.get("category", "tech")
        price = d.get("price", 0)

        if not emails:
            skipped.append({"domain": domain, "reason": "no_email"})
            continue

        for email in emails:
            if not email or "@" not in email or email in sent_emails:
                continue

            subject = f"Domain Broker Inquiry: {domain}"
            if name and name.lower() not in ("", "none", "redacted"):
                body = SELLER_BROKER_TEMPLATE.format(contact_name=name, domain=domain, niche=niche)
            else:
                body = SELLER_BROKER_NO_NAME.format(domain=domain, niche=niche)

            if dry_run:
                logger.info("[DRY RUN] Would email seller: %s for %s", email, domain)
                sent.append({"domain": domain, "email": email, "dry_run": True})
                sent_emails.add(email)
                continue

            try:
                success = await asyncio.get_event_loop().run_in_executor(
                    None, _send_email, email, subject, body
                )
                if success:
                    logger.info("Seller outreach sent: %s -> %s", domain, email)
                    sent.append({"domain": domain, "email": email, "success": True})
                    sent_emails.add(email)
                else:
                    failed.append({"domain": domain, "email": email})
            except Exception as e:
                logger.error("Error emailing seller: %s", e)
                failed.append({"domain": domain, "email": email, "error": str(e)})

    # Save log
    log_path = Path("data/outreach_log.json")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a") as f:
        f.write(json.dumps({"type": "seller_outreach", "sent": len(sent), "skipped": len(skipped), "failed": len(failed)}) + "\n")

    logger.info("Seller outreach: %d sent, %d skipped, %d failed", len(sent), len(skipped), len(failed))
    return {"sent": sent, "skipped": skipped, "failed": failed}
