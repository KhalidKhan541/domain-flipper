from __future__ import annotations

from typing import Any
from src.utils import setup_logger


class TemplateGenerator:
    """Generates cold outreach email/DM templates for domain brokering."""

    def __init__(self) -> None:
        self.logger = setup_logger("TemplateGenerator")

    def buyer_outreach(
        self,
        domain: str,
        buyer_company: str,
        buyer_name: str,
        estimated_value: int,
        niche: str,
    ) -> dict[str, str]:
        subject = f"Domain opportunity: {domain}"

        body = (
            f"Hi {buyer_name},\n\n"
            f"I came across {domain} and immediately thought of {buyer_company}. "
            f"As a business in the {niche} space, this domain could be a strong asset "
            f"for your brand — it is concise, memorable, and directly relevant to your industry.\n\n"
            f"Based on our analysis, this domain has an estimated market value of "
            f"${estimated_value:,}, with strong commercial potential and buyer demand "
            f"in the {niche} sector.\n\n"
            f"Would you be open to a brief conversation about this opportunity? "
            f"I would be happy to share more details.\n\n"
            f"Best regards,\n"
            f"Domain Broker"
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
            f"Best regards,\n"
            f"Domain Broker"
        )

        return {"subject": subject, "body": body}

    def follow_up(
        self,
        previous_subject: str,
        domain: str,
        buyer_company: str,
        attempt: int = 1,
    ) -> dict[str, str]:
        subject = f"Re: {previous_subject}"

        if attempt == 1:
            opening = (
                f"I wanted to follow up on my previous email regarding {domain}. "
                f"I believe this could be a strong asset for {buyer_company}."
            )
        elif attempt == 2:
            opening = (
                f"I am circling back on {domain}. We have seen growing interest, "
                f"and I wanted to make sure {buyer_company} had a chance to evaluate it."
            )
        elif attempt == 3:
            opening = (
                f"I do not want you to miss out on {domain}. Several parties have "
                f"expressed interest recently, and I would recommend acting soon."
            )
        else:
            opening = (
                f"This is my final follow-up on {domain}. Please let me know "
                f"if you are interested or if I should close this opportunity."
            )

        body = (
            f"Hi there,\n\n{opening}\n\n"
            f"Please let me know your thoughts.\n\n"
            f"Best regards,\n"
            f"Domain Broker"
        )

        return {"subject": subject, "body": body}

    def linkedin_message(
        self,
        domain: str,
        buyer_company: str,
        buyer_name: str,
    ) -> str:
        return (
            f"Hi {buyer_name}, I noticed {domain} is available and thought it "
            f"could be a great fit for {buyer_company}. "
            f"Open to a quick chat about it?"
        )
