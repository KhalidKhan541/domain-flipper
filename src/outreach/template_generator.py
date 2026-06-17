from __future__ import annotations

from typing import Any
from src.utils import setup_logger

SENDER_INFO = {
    "name": "Khalid Khan",
    "email": "khalid.khan46571@gmail.com",
    "phone": "03019883536",
}


class TemplateGenerator:
    """Generates cold outreach email/DM templates for domain brokering."""

    def __init__(self) -> None:
        self.logger = setup_logger("TemplateGenerator")

    def buyer_outreach(
        self,
        domain: str,
        company_name: str,
        contact_name: str,
        estimated_value: int,
        niche: str = "general",
    ) -> dict[str, str]:
        first_name = contact_name.split()[0] if contact_name else "there"

        subject = f"Premium {domain} — Perfect Fit for {company_name}"

        body = (
            f"Hello {first_name},\n\n"
            f"I hope you're doing well.\n\n"
            f"I noticed that your company operates in the {niche} space, and I wanted to "
            f"reach out because I currently own the domain **{domain}**, which I believe "
            f"could be a strong fit for your brand.\n\n"
            f"The domain is short, memorable, and highly relevant to your business. It could "
            f"help strengthen your online presence, improve brand recognition, and provide a "
            f"premium digital asset for future growth.\n\n"
            f"If this is something your team might be interested in, I'd be happy to discuss "
            f"details and pricing.\n\n"
            f"Thank you for your time, and I look forward to hearing from you.\n\n"
            f"Best regards,\n\n"
            f"{SENDER_INFO['name']}\n"
            f"Email: {SENDER_INFO['email']}\n"
            f"Contact: {SENDER_INFO['phone']}"
        )

        return {"subject": subject, "body": body}

    def seller_outreach(
        self,
        domain: str,
        seller_name: str,
        estimated_value: int,
    ) -> dict[str, str]:
        subject = f"Interested in purchasing {domain}"

        body = (
            f"Hi {seller_name},\n\n"
            f"I am reaching out as a domain broker representing a qualified buyer "
            f"who is interested in acquiring {domain}. We have assessed the domain "
            f"and estimate its current market value at approximately ${estimated_value:,}.\n\n"
            f"I would love to discuss this further and see if there is mutual interest "
            f"in moving forward with a potential transaction.\n\n"
            f"Please let me know if you would be open to a quick call or email exchange.\n\n"
            f"Best regards,\n\n"
            f"{SENDER_INFO['name']}\n"
            f"Email: {SENDER_INFO['email']}\n"
            f"Contact: {SENDER_INFO['phone']}"
        )

        return {"subject": subject, "body": body}

    def follow_up(
        self,
        previous_subject: str,
        domain: str,
        buyer_company: str,
        contact_name: str = "",
        attempt: int = 1,
    ) -> dict[str, str]:
        first_name = contact_name.split()[0] if contact_name else "there"
        subject = f"Re: Premium {domain} — Quick Follow-Up"

        if attempt == 1:
            opening = (
                f"I hope this message finds you well.\n\n"
                f"I'm following up on my previous email regarding **{domain}**. "
                f"I understand you're busy, so I'll keep this brief.\n\n"
                f"I have a few other interested parties, but I wanted to give you first "
                f"refusal given your work in the {buyer_company} space. The domain is "
                f"still available at this time.\n\n"
                f"If you'd like to discuss how {domain} could benefit {buyer_company}, "
                f"I'm happy to connect at your convenience."
            )
        elif attempt == 2:
            opening = (
                f"I am circling back on **{domain}**. We have seen growing interest, "
                f"and I wanted to make sure {buyer_company} had a chance to evaluate it "
                f"before it becomes unavailable."
            )
        else:
            opening = (
                f"This is my final follow-up on **{domain}**. Several parties have "
                f"expressed interest recently, and I would recommend acting soon "
                f"if you'd like to secure this domain for {buyer_company}."
            )

        body = (
            f"Hello {first_name},\n\n"
            f"{opening}\n\n"
            f"Thank you for your time.\n\n"
            f"Best regards,\n\n"
            f"{SENDER_INFO['name']}\n"
            f"Email: {SENDER_INFO['email']}\n"
            f"Contact: {SENDER_INFO['phone']}"
        )

        return {"subject": subject, "body": body}

    def linkedin_message(
        self,
        domain: str,
        buyer_company: str,
        buyer_name: str,
    ) -> str:
        first_name = buyer_name.split()[0] if buyer_name else "there"
        return (
            f"Hi {first_name}, I noticed {domain} is available and thought it "
            f"could be a great fit for {buyer_company}. "
            f"Open to a quick chat about it?"
        )

    def broker_owner_outreach(
        self,
        domain: str,
        owner_name: str = "",
        asking_price: int = 0,
    ) -> dict[str, str]:
        """Reach out to domain owner to broker their domain."""
        first_name = owner_name.split()[0] if owner_name else "there"

        subject = f"I have a buyer for {domain}"

        body = (
            f"Hello {first_name},\n\n"
            f"I hope you're doing well.\n\n"
            f"I'm a domain broker, and I noticed your domain **{domain}** is listed "
            f"for sale. I have a qualified buyer who is actively looking for a domain "
            f"in this space, and I believe we could close a deal quickly.\n\n"
            f"I work on a commission basis (15%), so there are no upfront costs to you. "
            f"If you're interested, I'd love to discuss your asking price and connect "
            f"you with the buyer.\n\n"
            f"Thank you for your time.\n\n"
            f"Best regards,\n\n"
            f"{SENDER_INFO['name']}\n"
            f"Email: {SENDER_INFO['email']}\n"
            f"Contact: {SENDER_INFO['phone']}"
        )

        return {"subject": subject, "body": body}

    def broker_buyer_outreach(
        self,
        domain: str,
        buyer_name: str,
        buyer_source: str = "",
        asking_price: int = 0,
    ) -> dict[str, str]:
        """Reach out to buyer with a domain match."""
        first_name = buyer_name.split()[0] if buyer_name else "there"

        subject = f"Found the perfect domain for you: {domain}"

        body = (
            f"Hello {first_name},\n\n"
            f"I hope you're doing well.\n\n"
            f"I came across your post looking for a domain in this space, and I wanted "
            f"to let you know that **{domain}** is available. I'm a domain broker, and "
            f"I can help facilitate the transaction.\n\n"
            f"The asking price is ${asking_price:,}, and I can negotiate on your behalf "
            f"to get you the best deal. There are no buyer fees — I work on commission "
            f"from the seller.\n\n"
            f"If you're interested, I'd be happy to share more details.\n\n"
            f"Thank you for your time.\n\n"
            f"Best regards,\n\n"
            f"{SENDER_INFO['name']}\n"
            f"Email: {SENDER_INFO['email']}\n"
            f"Contact: {SENDER_INFO['phone']}"
        )

        return {"subject": subject, "body": body}
