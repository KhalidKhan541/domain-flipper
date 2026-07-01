"""Agent 8: Email Buyers — contacts people looking to buy domains, offers them matching expiring domains."""

from __future__ import annotations

import asyncio
import json
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from src.config import settings
from src.utils import setup_logger

logger = logging.getLogger(__name__)

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


def _match_domains_to_needs(buyer_needs: list[str], available_domains: list[dict]) -> list[dict]:
    """Match buyer needs to available expiring domains."""
    matched = []

    for domain in available_domains:
        domain_categories = domain.get("categories", [])
        domain_name = domain.get("domain_name", "")

        # Check if domain matches any buyer need
        for need in buyer_needs:
            if need in domain_categories:
                matched.append(domain)
                break

    # Sort by estimated value (higher = better match)
    matched.sort(key=lambda x: x.get("estimated_value", 0), reverse=True)

    return matched[:5]


def _send_email(to_email: str, subject: str, body: str) -> bool:
    if not settings.smtp_host or not settings.smtp_user or not settings.smtp_pass:
        logger.warning("SMTP not configured — skipping email to %s", to_email)
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = settings.smtp_user
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30)
        try:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(settings.smtp_user, settings.smtp_pass)
            server.sendmail(settings.smtp_user, [to_email], msg.as_string())
        finally:
            server.quit()
        return True
    except smtplib.SMTPAuthenticationError as e:
        logger.error("SMTP auth failed for %s: %s (check App Password)", to_email, e)
        return False
    except smtplib.SMTPException as e:
        logger.error("SMTP error sending to %s: %s", to_email, e)
        return False
    except Exception as e:
        logger.error("Unexpected error sending email to %s: %s", to_email, e)
        return False


async def run(buyer_leads: list[dict], available_domains: list[dict], dry_run: bool = False) -> dict:
    """Contact buyers who are looking for domains, offer them matching expiring domains."""
    logger = setup_logger("BuyerOutreach")
    sent, skipped, failed = [], [], []

    for lead in buyer_leads:
        author = lead.get("author", "")
        source = lead.get("source", "")
        title = lead.get("title", "")
        buyer_needs = lead.get("buyer_needs", [])
        mentioned_domains = lead.get("mentioned_domains", [])
        suggested_domains = lead.get("suggested_domains", [])

        # Find matching domains based on buyer needs
        matching_domains = _match_domains_to_needs(buyer_needs, available_domains)

        # If no category match, try TLD match
        if not matching_domains and mentioned_domains:
            for md in mentioned_domains:
                tld = md.split(".")[-1] if "." in md else ""
                for domain in available_domains:
                    if domain.get("tld") == tld and domain not in matching_domains:
                        matching_domains.append(domain)
                        if len(matching_domains) >= 3:
                            break

        # If still no match, use suggested domains from buyer needs
        if not matching_domains and suggested_domains:
            for sd in suggested_domains:
                for domain in available_domains:
                    if domain.get("domain_name") == sd and domain not in matching_domains:
                        matching_domains.append(domain)
                        if len(matching_domains) >= 3:
                            break

        if not matching_domains:
            skipped.append({"author": author, "reason": "no_matching_domains", "needs": buyer_needs})
            continue

        # Build personalized message
        domain_list = ", ".join([d["domain_name"] for d in matching_domains[:3]])
        estimated_values = [d.get("estimated_value", 0) for d in matching_domains[:3]]
        avg_value = sum(estimated_values) / len(estimated_values) if estimated_values else 0

        # Create personalized line based on buyer needs
        if buyer_needs:
            need_str = " and ".join(buyer_needs[:2])
            personalized = f"Based on your interest in {need_str}, I have domains like {domain_list} that would be perfect for your project."
        else:
            personalized = f"I have domains like {domain_list} that might interest you."

        # Add value proposition
        personalized += f" These are premium domains with estimated values of ${avg_value:.0f}+."

        subject = f"Premium Domains for Your {buyer_needs[0].title() if buyer_needs else 'Project'}"
        body = BUYER_TEMPLATE.format(
            author=author,
            source=source,
            personalized_line=personalized,
        )

        # Save for manual outreach (Reddit/HN users don't have public emails)
        sent.append({
            "author": author,
            "source": source,
            "title": title,
            "platform_url": lead.get("url", ""),
            "buyer_needs": buyer_needs,
            "matching_domains": [
                {
                    "domain": d["domain_name"],
                    "estimated_value": d.get("estimated_value", 0),
                    "categories": d.get("categories", []),
                    "registration_cost": d.get("price", 10),
                }
                for d in matching_domains[:3]
            ],
            "suggested_domains": [d["domain_name"] for d in matching_domains[:3]],
            "message": body,
            "status": "pending_manual_outreach",
            "profit_potential": avg_value * 0.7,  # 70% profit after registration cost
        })

    # Save outreach plan
    plan_path = Path("data/buyer_outreach_plan.json")
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    with open(plan_path, "w") as f:
        json.dump(sent, f, indent=2)

    # Log summary
    total_profit = sum(s.get("profit_potential", 0) for s in sent)
    logger.info("Buyer outreach: %d leads prepared, %d skipped", len(sent), len(skipped))
    logger.info("Estimated total profit potential: $%.0f", total_profit)

    return {"prepared": sent, "skipped": skipped}
