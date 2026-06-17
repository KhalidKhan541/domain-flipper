from datetime import datetime, timezone

import httpx

from src.config import settings
from src.notifiers import BaseNotifier
from src.utils import setup_logger


class DiscordNotifier(BaseNotifier):
    def __init__(self):
        self.logger = setup_logger("DiscordNotifier")
        self.webhook_url = settings.discord_webhook_url
        self.enabled = bool(self.webhook_url)

    async def send_report(self, report_text: str, domains: list[dict]) -> bool:
        if not self.enabled:
            self.logger.warning("Discord notifier is disabled")
            return False

        count = len(domains)
        top_count = min(10, count)

        fields = [
            {
                "name": "Summary",
                "value": f"Found {count} broker opportunities, Top {top_count} listed below",
                "inline": False,
            }
        ]

        for domain in domains[:10]:
            name = domain.get("domain_name", "Unknown")
            est = domain.get("estimated_value", 0)
            comm = domain.get("commission", {}).get("amount", 0)
            bgrade = domain.get("broker_grade", "Cold")
            leads = domain.get("buyer_leads", {}).get("total_leads", 0)
            fields.append(
                {
                    "name": name,
                    "value": f"Est: ${est} | Comm: ${comm} | Leads: {leads} | Grade: {bgrade}",
                    "inline": True,
                }
            )

        embed = {
            "title": "Daily Broker Report",
            "color": 0x00FF00,
            "fields": fields,
            "footer": {"text": "Domain Flipper Bot"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        payload = {"embeds": [embed]}

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(self.webhook_url, json=payload)

                if response.status_code >= 400:
                    self.logger.error(
                        f"Discord webhook returned {response.status_code}: {response.text[:500]}"
                    )
                    return False

                response.raise_for_status()
                return True

            except httpx.TimeoutException:
                self.logger.error("Discord webhook request timed out")
                return False
            except httpx.RequestError as e:
                self.logger.error(f"Discord webhook request error: {e}")
                return False
            except httpx.HTTPStatusError as e:
                self.logger.error(
                    f"Discord webhook HTTP error: {e.response.status_code} {e.response.text[:500]}"
                )
                return False

    async def send_alert(self, message: str) -> bool:
        if not self.enabled:
            self.logger.warning("Discord notifier is disabled")
            return False

        payload = {"content": message}

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(self.webhook_url, json=payload)

                if response.status_code >= 400:
                    self.logger.error(
                        f"Discord webhook returned {response.status_code}: {response.text[:500]}"
                    )
                    return False

                response.raise_for_status()
                return True

            except httpx.TimeoutException:
                self.logger.error("Discord webhook request timed out")
                return False
            except httpx.RequestError as e:
                self.logger.error(f"Discord webhook request error: {e}")
                return False
            except httpx.HTTPStatusError as e:
                self.logger.error(
                    f"Discord webhook HTTP error: {e.response.status_code} {e.response.text[:500]}"
                )
                return False

    async def send_buyer_leads(self, domain: str, leads: list[dict], estimated_value: int) -> bool:
        if not self.enabled:
            self.logger.warning("Discord notifier is disabled")
            return False

        has_hot_leads = any(lead.get("score", 0) >= 80 for lead in leads)
        embed_color = 0x00FF00 if has_hot_leads else 0xFF9900

        fields = []
        for lead in leads[:5]:
            company = lead.get("company", "Unknown")
            contact_name = lead.get("contact_name", "Unknown")
            title = lead.get("title", "")
            email = lead.get("email", "")
            score = lead.get("score", 0)
            source = lead.get("source", "Unknown")

            masked_email = self._mask_email(email)

            contact_display = f"{contact_name}" + (f" ({title})" if title else "")
            score_label = "Hot" if score >= 80 else "Warm" if score >= 50 else "Cold"

            fields.append(
                {
                    "name": company,
                    "value": (
                        f"**Contact:** {contact_display}\n"
                        f"**Email:** {masked_email}\n"
                        f"**Score:** {score}/100 ({score_label})\n"
                        f"**Source:** {source}"
                    ),
                    "inline": True,
                }
            )

        if not fields:
            fields.append(
                {
                    "name": "No Leads",
                    "value": "No buyer leads found for this domain.",
                    "inline": False,
                }
            )

        embed = {
            "title": f"🎯 Buyer Leads Found: {domain}",
            "color": embed_color,
            "fields": fields,
            "footer": {
                "text": f"Estimated Value: ${estimated_value:,} | Total Leads: {len(leads)}"
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        payload = {"embeds": [embed]}

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(self.webhook_url, json=payload)

                if response.status_code >= 400:
                    self.logger.error(
                        f"Discord webhook returned {response.status_code}: {response.text[:500]}"
                    )
                    return False

                response.raise_for_status()
                return True

            except httpx.TimeoutException:
                self.logger.error("Discord webhook request timed out")
                return False
            except httpx.RequestError as e:
                self.logger.error(f"Discord webhook request error: {e}")
                return False
            except httpx.HTTPStatusError as e:
                self.logger.error(
                    f"Discord webhook HTTP error: {e.response.status_code} {e.response.text[:500]}"
                )
                return False

    async def send_pipeline_summary(self, stats: dict) -> bool:
        if not self.enabled:
            self.logger.warning("Discord notifier is disabled")
            return False

        domains_discovered = stats.get("domains_discovered", 0)
        total_leads = stats.get("total_leads", 0)
        emails_sent = stats.get("emails_sent", 0)
        top_opportunity = stats.get("top_opportunity", "N/A")

        fields = [
            {
                "name": "Domains Discovered",
                "value": str(domains_discovered),
                "inline": True,
            },
            {
                "name": "Total Buyer Leads",
                "value": str(total_leads),
                "inline": True,
            },
            {
                "name": "Emails Sent",
                "value": str(emails_sent),
                "inline": True,
            },
            {
                "name": "Top Opportunity of the Day",
                "value": str(top_opportunity),
                "inline": False,
            },
        ]

        embed = {
            "title": "📊 Daily Pipeline Summary",
            "color": 0x3498DB,
            "fields": fields,
            "footer": {"text": "Domain Flipper Bot"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        payload = {"embeds": [embed]}

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(self.webhook_url, json=payload)

                if response.status_code >= 400:
                    self.logger.error(
                        f"Discord webhook returned {response.status_code}: {response.text[:500]}"
                    )
                    return False

                response.raise_for_status()
                return True

            except httpx.TimeoutException:
                self.logger.error("Discord webhook request timed out")
                return False
            except httpx.RequestError as e:
                self.logger.error(f"Discord webhook request error: {e}")
                return False
            except httpx.HTTPStatusError as e:
                self.logger.error(
                    f"Discord webhook HTTP error: {e.response.status_code} {e.response.text[:500]}"
                )
                return False

    def _mask_email(self, email: str) -> str:
        if not email or "@" not in email:
            return "N/A"

        local, domain_part = email.split("@", 1)
        if len(local) <= 2:
            masked_local = local[0] + "***"
        else:
            masked_local = local[0] + "***" + local[-1]

        return f"{masked_local}@{domain_part}"
