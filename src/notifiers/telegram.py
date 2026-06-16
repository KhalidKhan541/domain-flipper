import asyncio

import httpx

from src.config import settings
from src.notifiers import BaseNotifier
from src.utils import setup_logger


def _escape_markdown(text: str) -> str:
    chars = [
        "_", "*", "[", "]", "(", ")", "~", "`",
        ">", "#", "+", "-", "=", "|", "{", "}", ".", "!", "\\",
    ]
    for ch in chars:
        text = text.replace(ch, "\\" + ch)
    return text


def _format_domain(domain: dict) -> str:
    name = _escape_markdown(str(domain.get("domain", "Unknown")))
    price = _escape_markdown(str(domain.get("price", "0")))
    dr = _escape_markdown(str(domain.get("dr", "N/A")))
    rd = _escape_markdown(str(domain.get("rd", "N/A")))
    score = _escape_markdown(str(domain.get("final_score", "0")))
    grade = _escape_markdown(str(domain.get("grade", "N/A")))
    category = _escape_markdown(str(domain.get("category", "Uncategorized")))

    return (
        f"*{name}*\n"
        f"Price: ${price} | DR: {dr} | RD: {rd}\n"
        f"Score: {score} | Grade: {grade}\n"
        f"Category: {category}"
    )


class TelegramNotifier(BaseNotifier):
    def __init__(self):
        self.logger = setup_logger("TelegramNotifier")
        self.bot_token = settings.telegram_bot_token
        self.chat_id = settings.telegram_chat_id
        self.enabled = bool(self.bot_token and self.chat_id)

    async def send_report(self, report_text: str, domains: list[dict]) -> bool:
        if not self.enabled:
            self.logger.warning("Telegram notifier is disabled")
            return False

        lines = ["*Daily Domain Report*\n"]
        for domain in domains:
            lines.append(_format_domain(domain))
            lines.append("")

        full_message = "\n".join(lines)
        return await self._send_chunks(full_message)

    async def send_alert(self, message: str) -> bool:
        if not self.enabled:
            self.logger.warning("Telegram notifier is disabled")
            return False

        return await self._send_message(message)

    async def _send_chunks(self, message: str) -> bool:
        max_len = 4096
        success = True
        for i in range(0, len(message), max_len):
            chunk = message[i : i + max_len]
            if not await self._send_message(chunk):
                success = False
        return success

    async def _send_message(self, text: str) -> bool:
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "MarkdownV2",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(3):
                try:
                    response = await client.post(url, json=payload)

                    if response.status_code == 429:
                        retry_after = response.json().get("parameters", {}).get("retry_after", 5)
                        self.logger.warning(
                            f"Rate limited, retrying in {retry_after}s (attempt {attempt + 1})"
                        )
                        await asyncio.sleep(retry_after)
                        continue

                    response.raise_for_status()
                    return True

                except httpx.TimeoutException:
                    self.logger.error(f"Telegram request timed out (attempt {attempt + 1})")
                except httpx.HTTPStatusError as e:
                    self.logger.error(
                        f"Telegram HTTP error: {e.response.status_code} {e.response.text}"
                    )
                    return False
                except httpx.RequestError as e:
                    self.logger.error(f"Telegram request error: {e}")

                if attempt < 2:
                    await asyncio.sleep(2**attempt)

        self.logger.error("Telegram message failed after all retries")
        return False
