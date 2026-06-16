from __future__ import annotations

import asyncio
import logging
from email.mime.text import MIMEText
from typing import Optional

from src.config import settings
from src.utils.logger import setup_logger


class EmailSender:
    """Sends outreach emails via SMTP. Falls back to aiosmtplib, then smtplib."""

    def __init__(self) -> None:
        self.logger = setup_logger("EmailSender")
        self.enabled = bool(
            settings.smtp_host and settings.smtp_user and settings.smtp_pass
        )

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
    ) -> bool:
        if not self.enabled:
            self.logger.warning("EmailSender is disabled")
            return False

        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = settings.email_from
        msg["To"] = to_email
        if cc:
            msg["Cc"] = cc

        return await self._send(msg)

    async def send_outreach(
        self,
        to_email: str,
        lead_type: str,
        domain: str,
        subject: str,
        body: str,
    ) -> bool:
        if not self.enabled:
            self.logger.warning("EmailSender is disabled")
            return False

        self.logger.info(
            "Sending %s outreach for %s to %s", lead_type, domain, to_email
        )
        success = await self.send_email(to_email=to_email, subject=subject, body=body)
        if success:
            self.logger.info(
                "Outreach sent successfully: %s - %s (%s)", domain, lead_type, to_email
            )
        else:
            self.logger.warning(
                "Outreach failed: %s - %s (%s)", domain, lead_type, to_email
            )
        return success

    async def _send(self, msg) -> bool:
        try:
            import aiosmtplib

            await aiosmtplib.send(
                msg,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_user,
                password=settings.smtp_pass,
                use_tls=settings.smtp_port == 465,
                start_tls=settings.smtp_port == 587,
            )
            self.logger.info("Email sent successfully via aiosmtplib")
            return True

        except ImportError:
            self.logger.info("aiosmtplib not available, falling back to smtplib")
            return await self._send_sync_fallback(msg)

        except Exception as e:
            self.logger.error(f"aiosmtplib error: {e}")
            return await self._send_sync_fallback(msg)

    async def _send_sync_fallback(self, msg) -> bool:
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, self._smtp_send, msg)
            self.logger.info("Email sent successfully via smtplib")
            return True
        except ConnectionError as e:
            self.logger.error(f"SMTP connection/auth error: {e}")
            return False
        except Exception as e:
            self.logger.error(f"smtplib error: {e}")
            return False

    def _smtp_send(self, msg) -> None:
        import smtplib
        import ssl

        if settings.smtp_port == 465:
            with smtplib.SMTP_SSL(
                settings.smtp_host, settings.smtp_port, timeout=30,
                context=ssl.create_default_context(),
            ) as server:
                if settings.smtp_user and settings.smtp_pass:
                    server.login(settings.smtp_user, settings.smtp_pass)
                server.send_message(msg)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
                if settings.smtp_port == 587:
                    server.starttls(context=ssl.create_default_context())
                if settings.smtp_user and settings.smtp_pass:
                    server.login(settings.smtp_user, settings.smtp_pass)
                server.send_message(msg)
