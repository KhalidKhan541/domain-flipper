import logging
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class N8nClient:
    def __init__(self, base_url: str = "http://localhost:5678") -> None:
        self.base_url = base_url.rstrip("/")
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> "N8nClient":
        await self._get_session()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def call_webhook(
        self, workflow_path: str, data: dict, timeout: int = 30
    ) -> dict:
        url = f"{self.base_url}/webhook/{workflow_path}"
        logger.info("POST %s", url)
        try:
            session = await self._get_session()
            async with session.post(
                url, json=data, timeout=aiohttp.ClientTimeout(total=timeout)
            ) as resp:
                resp.raise_for_status()
                return await resp.json()
        except Exception as exc:
            logger.error("Webhook call failed: %s", exc)
            return {"error": str(exc)}

    async def crawly_seo(self, url: str) -> dict:
        return await self.call_webhook("crawly-seo", {"url": url})

    async def safe_browsing_check(self, url: str, api_key: str) -> dict:
        return await self.call_webhook(
            "safe-browsing", {"url": url, "api_key": api_key}
        )

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_pass: str,
    ) -> dict:
        return await self.call_webhook(
            "send-email",
            {
                "to": to,
                "subject": subject,
                "body": body,
                "smtp_host": smtp_host,
                "smtp_port": smtp_port,
                "smtp_user": smtp_user,
                "smtp_pass": smtp_pass,
            },
        )
