from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from src.utils import setup_logger


class CommissionAgreementGenerator:
    """Generates commission agreement documents for domain brokerage deals."""

    def __init__(self) -> None:
        self.logger = setup_logger("CommissionAgreement")

    async def generate(
        self,
        domain: str,
        buyer_name: str,
        buyer_company: str,
        seller_name: str,
        seller_company: str,
        commission_amount: int,
        commission_rate: float,
        estimated_value: int,
    ) -> str:
        today = datetime.now(timezone.utc).strftime("%B %d, %Y")

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  body {{ font-family: 'Times New Roman', serif; margin: 40px; line-height: 1.6; }}
  h1 {{ text-align: center; font-size: 22pt; margin-bottom: 5px; }}
  .date {{ text-align: center; font-size: 11pt; margin-bottom: 30px; }}
  h2 {{ font-size: 14pt; margin-top: 25px; margin-bottom: 10px; }}
  p {{ font-size: 11pt; }}
  .signatures {{ margin-top: 50px; }}
  .signature-line {{ border-top: 1px solid #000; width: 250px; margin-top: 40px; margin-bottom: 5px; }}
  .signature-label {{ font-size: 10pt; }}
</style>
</head>
<body>

<h1>Domain Broker Commission Agreement</h1>
<p class="date">{today}</p>

<p>This Commission Agreement (the "Agreement") is entered into by and between the following parties:</p>

<h2>Parties</h2>
<p><strong>Broker:</strong> Domain Flipper Brokerage<br>
<strong>Buyer:</strong> {buyer_name} ({buyer_company})<br>
<strong>Seller:</strong> {seller_name} ({seller_company})</p>

<h2>Domain</h2>
<p><strong>{domain}</strong></p>

<h2>Commission</h2>
<p>The Buyer and Seller agree that upon the successful sale of the domain, the Broker shall receive a commission of <strong>{commission_rate:.0%}</strong> of the final sale price, estimated at <strong>${commission_amount:,}</strong> based on an estimated domain value of <strong>${estimated_value:,}</strong>.</p>

<h2>Terms</h2>
<p>The commission shall be payable to the Broker upon the successful completion of the domain sale. "Successful sale" is defined as the transfer of domain ownership from Seller to Buyer in exchange for monetary consideration.</p>

<h2>Duration</h2>
<p>This Agreement grants the Broker exclusive rights to facilitate the sale of {domain} for a period of <strong>90 days</strong> from the date of this Agreement. During this period, the Seller agrees not to engage another broker or directly negotiate the sale of the domain without the Broker's involvement.</p>

<h2>Signatures</h2>
<div class="signatures">
  <div class="signature-line"></div>
  <p class="signature-label">{buyer_name} — Buyer ({buyer_company})</p>
  <div class="signature-line"></div>
  <p class="signature-label">{seller_name} — Seller ({seller_company})</p>
  <div class="signature-line"></div>
  <p class="signature-label">Broker — Domain Flipper Brokerage</p>
</div>

</body>
</html>"""

        return html

    async def save(self, content: str, domain: str) -> Path:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        dir_path = Path("data") / "agreements"
        dir_path.mkdir(parents=True, exist_ok=True)
        file_path = dir_path / f"{domain}_commission_agreement_{today}.html"
        file_path.write_text(content, encoding="utf-8")
        self.logger.info("Saved commission agreement to %s", file_path)
        return file_path
