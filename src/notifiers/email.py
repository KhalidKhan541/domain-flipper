import logging
import mimetypes
import smtplib
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
        commission = d.get("commission", {}).get("amount", 0)
        buyer_leads = d.get("buyer_leads", {}).get("total_leads", 0)
        seller_name = d.get("owner_contact", {}).get("registrant_name", "N/A")
        rows_html += (
            "<tr>"
            f"<td style='padding:8px;border:1px solid #ddd;'>{d.get('domain_name', '')}</td>"
            f"<td style='padding:8px;border:1px solid #ddd;'>${d.get('estimated_value', 0):,}</td>"
            f"<td style='padding:8px;border:1px solid #ddd;'>${commission}</td>"
            f"<td style='padding:8px;border:1px solid #ddd;'>{buyer_leads}</td>"
            f"<td style='padding:8px;border:1px solid #ddd;'>{d.get('broker_score', 0)}</td>"
            f"<td style='padding:8px;border:1px solid #ddd;'>{d.get('broker_grade', 'Cold')}</td>"
            f"<td style='padding:8px;border:1px solid #ddd;'>{d.get('category', 'Uncategorized')}</td>"
            f"<td style='padding:8px;border:1px solid #ddd;'>{seller_name}</td>"
            "</tr>"
        )

    return (
        "<html>"
        "<body style='font-family:Arial,sans-serif;padding:20px;'>"
        "<h2 style='color:#333;'>Daily Broker Report</h2>"
        "<table style='border-collapse:collapse;width:100%;max-width:900px;'>"
        "<thead>"
        "<tr style='background-color:#4CAF50;color:white;'>"
        "<th style='padding:10px;text-align:left;border:1px solid #ddd;'>Domain</th>"
        "<th style='padding:10px;text-align:left;border:1px solid #ddd;'>Est. Value</th>"
        "<th style='padding:10px;text-align:left;border:1px solid #ddd;'>Commission</th>"
        "<th style='padding:10px;text-align:left;border:1px solid #ddd;'>Buyer Leads</th>"
        "<th style='padding:10px;text-align:left;border:1px solid #ddd;'>Broker Score</th>"
        "<th style='padding:10px;text-align:left;border:1px solid #ddd;'>Grade</th>"
        "<th style='padding:10px;text-align:left;border:1px solid #ddd;'>Niche</th>"
        "<th style='padding:10px;text-align:left;border:1px solid #ddd;'>Seller</th>"
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

    def _send_via_smtp(self, to: str, subject: str, body: str, html: bool = False) -> None:
        msg = MIMEMultipart("alternative")
        msg["From"] = self.email_from or self.smtp_user
        msg["To"] = to
        msg["Subject"] = subject

        subtype = "html" if html else "plain"
        msg.attach(MIMEText(body, subtype, "utf-8"))

        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(self.smtp_user, self.smtp_pass)
            server.sendmail(self.smtp_user, to, msg.as_string())

    async def send_report(self, report_text: str, domains: list[dict]) -> bool:
        if not self.enabled:
            self.logger.warning("Email notifier is disabled")
            return False

        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        subject = f"Daily Broker Report - {date_str}"

        html_body = _build_html_table(domains)

        try:
            self._send_via_smtp(to=self.email_to, subject=subject, body=html_body, html=True)
            self.logger.info("Daily broker report sent via Gmail SMTP")
            return True
        except Exception as e:
            self.logger.error("Failed to send report: %s", e)
            return False

    async def send_alert(self, message: str) -> bool:
        if not self.enabled:
            self.logger.warning("Email notifier is disabled")
            return False

        try:
            self._send_via_smtp(to=self.email_to, subject="Domain Broker Alert", body=message)
            self.logger.info("Alert sent via Gmail SMTP")
            return True
        except Exception as e:
            self.logger.error("Failed to send alert: %s", e)
            return False
