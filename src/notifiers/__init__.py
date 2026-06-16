from abc import ABC, abstractmethod


class BaseNotifier(ABC):
    @abstractmethod
    async def send_report(self, report_text: str, domains: list[dict]) -> bool:
        pass

    @abstractmethod
    async def send_alert(self, message: str) -> bool:
        pass


from src.notifiers.telegram import TelegramNotifier
from src.notifiers.discord import DiscordNotifier
from src.notifiers.email import EmailNotifier

__all__ = ["BaseNotifier", "TelegramNotifier", "DiscordNotifier", "EmailNotifier"]

NOTIFIERS = [TelegramNotifier, DiscordNotifier, EmailNotifier]
