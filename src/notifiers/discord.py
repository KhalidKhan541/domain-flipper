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
                "value": f"Found {count} domains, Top {top_count} listed below",
                "inline": False,
            }
        ]

        for domain in domains[:10]:
            name = domain.get("domain", "Unknown")
            price = domain.get("price", 0)
            score = domain.get("final_score", 0)
            grade = domain.get("grade", "N/A")
            fields.append(
                {
                    "name": name,
                    "value": f"Price: ${price} | Score: {score} | Grade: {grade}",
                    "inline": True,
                }
            )

        embed = {
            "title": "Daily Domain Report",
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
