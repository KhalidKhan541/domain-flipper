"""Agent 8: Email Buyers — contacts people looking to buy domains, offers them domains."""

from __future__ import annotations

import asyncio
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from src.config import settings
from src.utils import setup_logger

BUYER_TEMPLATE = """\
Hi {author},

I saw your post on {source} about looking for a domain. I'm a domain broker and I have access to premium domains that match what you're looking for.

{personalized_line}

I can help you acquire the perfect domain at a competitive price. We use Escrow.com for secure transactions.

Would you like me to send you some options?

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


async def run(buyer_leads: list[dict], available_domains: list[dict], dry_run: bool = False) -> dict:
    """Contact buyers who are looking for domains, offer them available domains."""
    logger = setup_logger("BuyerOutreach")
    sent, skipped, failed = [], [], []
    sent_emails: set[str] = set()

    # Build domain suggestions map
    domain_suggestions: dict[str, list[str]] = {}
    for d in available_domains:
        name = d.get("domain_name", "")
        tld = d.get("tld", "")
        # Index by TLD for matching
        if tld not in domain_suggestions:
            domain_suggestions[tld] = []
        domain_suggestions[tld].append(name)

    for lead in buyer_leads:
        author = lead.get("author", "")
        source = lead.get("source", "")
        title = lead.get("title", "")
        mentioned = lead.get("mentioned_domains", [])

        # Try to find matching domains
        matching_domains = []
        for md in mentioned:
            tld = md.split(".")[-1] if "." in md else ""
            if tld in domain_suggestions:
                matching_domains.extend(domain_suggestions[tld][:3])

        if not matching_domains:
            # Suggest from general pool
            for tld_domains in domain_suggestions.values():
                matching_domains.extend(tld_domains[:2])
                if len(matching_domains) >= 3:
                    break

        if not matching_domains:
            skipped.append({"author": author, "reason": "no_matching_domains"})
            continue

        personalized = f"I have domains like {', '.join(matching_domains[:3])} that might interest you."

        subject = f"Premium Domains for Your Project"
        body = BUYER_TEMPLATE.format(
            author=author,
            source=source,
            personalized_line=personalized,
        )

        # Note: Reddit/HN users don't have public emails
        # We'd need to DM them on the platform
        # For now, log the outreach
        if dry_run:
            logger.info("[DRY RUN] Would DM buyer: %s on %s", author, source)
            sent.append({"author": author, "source": source, "domains": matching_domains[:3], "dry_run": True})
            continue

        # Save for manual outreach
        sent.append({
            "author": author,
            "source": source,
            "title": title,
            "platform_url": lead.get("url", ""),
            "suggested_domains": matching_domains[:3],
            "message": body,
            "status": "pending_manual_outreach",
        })

    # Save outreach plan
    plan_path = Path("data/buyer_outreach_plan.json")
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    with open(plan_path, "w") as f:
        json.dump(sent, f, indent=2)

    logger.info("Buyer outreach: %d leads prepared, %d skipped", len(sent), len(skipped))
    return {"prepared": sent, "skipped": skipped}
