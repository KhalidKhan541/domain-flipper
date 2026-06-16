import asyncio
import logging
import mimetypes
from datetime import datetime, timezone
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders
from pathlib import Path

from src.config import settings
from src.notifiers import BaseNotifier
from src.utils import setup_logger


REPORT_DIR = Path("data/reports")


def _build_html_table(domains: list[dict]) -> str:
    rows_html = ""
    for d in domains[:20]:
        rows_html += (
            "<tr>"
            f"<td style='padding:8px;border:1px solid #ddd;'>{d.get('domain', '')}</td>"
            f"<td style='padding:8px;border:1px solid #ddd;'>${d.get('price', 0)}</td>"
            f"<td style='padding:8px;border:1px solid #ddd;'>{d.get('dr', 'N/A')}</td>"
            f"<td style='padding:8px;border:1px solid #ddd;'>{d.get('rd', 'N/A')}</td>"
            f"<td style='padding:8px;border:1px solid #ddd;'>{d.get('age', 'N/A')}</td>"
            f"<td style='padding:8px;border:1px solid #ddd;'>{d.get('category', 'Uncategorized')}</td>"
            f"<td style='padding:8px;border:1px solid #ddd;'>{d.get('final_score', 0)}</td>"
            f"<td style='padding:8px;border:1px solid #ddd;'>{d.get('grade', 'N/A')}</td>"
            "</tr>"
        )

    return (
        "<html>"
        "<body style='font-family:Arial,sans-serif;padding:20px;'>"
        "<h2 style='color:#333;'>Daily Domain Report</h2>"
        "<table style='border-collapse:collapse;width:100%;max-width:900px;'>"
        "<thead>"
        "<tr style='background-color:#4CAF50;color:white;'>"
        "<th style='padding:10px;text-align:left;border:1px solid #ddd;'>Domain</th>"
        "<th style='padding:10px;text-align:left;border:1px solid #ddd;'>Price</th>"
        "<th style='padding:10px;text-align:left;border:1px solid #ddd;'>DR</th>"
        "<th style='padding:10px;text-align:left;border:1px solid #ddd;'>RD</th>"
        "<th style='padding:10px;text-align:left;border:1px solid #ddd;'>Age</th>"
        "<th style='padding:10px;text-align:left;border:1px solid #ddd;'>Category</th>"
        "<th style='padding:10px;text-align:left;border:1px solid #ddd;'>Score</th>"
        "<th style='padding:10px;text-align:left;border:1px solid #ddd;'>Grade</th>"
        "</tr>"
        "</thead>"
        "<tbody>"
        f"{rows_html}"
        "</tbody>"
        "</table>"
        "</body>"
        "</html>"
    )


def _attach_file(msg: MIMEMultipart, filepath: Path, logger: logging.Logger) -> None:
    if not filepath.is_file():
        return

    try:
        with open(filepath, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)

        ctype, _ = mimetypes.guess_type(str(filepath))
        if ctype:
            part.set_type(ctype)

        part.add_header(
            "Content-Disposition",
            f'attachment; filename="{filepath.name}"',
        )
        msg.attach(part)
        logger.info(f"Attached report file: {filepath.name}")
    except OSError as e:
        logger.warning(f"Failed to attach {filepath.name}: {e}")


class EmailNotifier(BaseNotifier):
    def __init__(self):
        self.logger = setup_logger("EmailNotifier")
        self.smtp_host = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.smtp_user = settings.smtp_user
        self.smtp_pass = settings.smtp_pass
        self.email_from = settings.email_from
        self.email_to = settings.email_to
        self.enabled = bool(
            self.smtp_host and self.smtp_user and self.smtp_pass and self.email_to
        )

    async def send_report(self, report_text: str, domains: list[dict]) -> bool:
        if not self.enabled:
            self.logger.warning("Email notifier is disabled")
            return False

        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        subject = f"Daily Domain Report - {date_str}"

        html_body = _build_html_table(domains)
        text_body = f"Daily Domain Report - {date_str}\n\nFound {len(domains)} domains."

        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = self.email_from
        msg["To"] = self.email_to

        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(text_body, "plain", "utf-8"))
        alt.attach(MIMEText(html_body, "html", "utf-8"))
        msg.attach(alt)

        if REPORT_DIR.is_dir():
            for fpath in sorted(REPORT_DIR.iterdir()):
                if fpath.is_file() and not fpath.name.startswith("."):
                    _attach_file(msg, fpath, self.logger)

        return await self._send(msg)

    async def send_alert(self, message: str) -> bool:
        if not self.enabled:
            self.logger.warning("Email notifier is disabled")
            return False

        msg = MIMEText(message, "plain", "utf-8")
        msg["Subject"] = "Domain Flipper Alert"
        msg["From"] = self.email_from
        msg["To"] = self.email_to

        return await self._send(msg)

    async def _send(self, msg) -> bool:
        try:
            import aiosmtplib

            await aiosmtplib.send(
                msg,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_user,
                password=self.smtp_pass,
                use_tls=self.smtp_port == 465,
                start_tls=self.smtp_port == 587,
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

        if self.smtp_port == 465:
            with smtplib.SMTP_SSL(
                self.smtp_host, self.smtp_port, timeout=30,
                context=ssl.create_default_context(),
            ) as server:
                if self.smtp_user and self.smtp_pass:
                    server.login(self.smtp_user, self.smtp_pass)
                server.send_message(msg)
        else:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as server:
                if self.smtp_port == 587:
                    server.starttls(context=ssl.create_default_context())
                if self.smtp_user and self.smtp_pass:
                    server.login(self.smtp_user, self.smtp_pass)
                server.send_message(msg)
