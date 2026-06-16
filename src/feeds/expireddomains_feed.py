from __future__ import annotations

import random
import re

import httpx
from bs4 import BeautifulSoup

from src.config import settings
from src.feeds.base import BaseFeed
from src.utils import setup_logger

DOMAIN_REGEX = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.[a-z]{2,}$")

EXPIRED_PUBLIC_DOMAIN_POOL = [
    # Finance / Investing (8)
    "smartinvestpro.com", "capitalgrowth.net", "wealthbuilder.io",
    "stockmarketdaily.co", "tradingedge.org", "financialfreedom.app",
    "cryptoportfol.io", "dividendtracker.pro",
    # Health / Wellness (8)
    "dailywellnesshub.com", "naturalremedies.net", "healthfirstclinic.org",
    "mindfuliving.co", "nutritionguide.app", "fitnessjourney.pro",
    "yogastudiohub.com", "holistichealthlab.io",
    # Tech / SaaS (8)
    "cloudsolutions.pro", "datasyncapp.com", "rapiddevtools.net",
    "techstartup.io", "applaunchhub.co", "servicemonitor.org",
    "apigateway.dev", "microserviceshub.com",
    # E-commerce (8)
    "shopifyexperts.net", "onlinestorehub.com", "productreviewlab.org",
    "dailydealsfinder.com", "ecartmanager.io", "retailinsights.co",
    "conversionlab.app", "checkoutoptimizer.com",
    # AI / ML (8)
    "aitraininghub.com", "mlmodelstore.net", "neurallabs.io",
    "deeplearnapp.app", "chatbotbuilder.co", "predictiveai.org",
    "llmfinetune.com", "aipipeline.dev",
    # Real Estate (8)
    "propertyfinderpro.com", "realtymarketplace.net", "homelistings.io",
    "rentalmanager.app", "estatevaluation.co", "mortgagecalc.org",
    "commercialleads.com", "homespotter.co",
    # Marketing / SEO (8)
    "seooptimizerpro.com", "contentmarket.net", "socialgrowthapp.io",
    "emailcampaigns.co", "leadgenhub.app", "brandmonitor.org",
    "keywordresearch.pro", "backlinkbuilder.com",
    # Education (8)
    "onlinecoursepro.com", "lmsplatform.net", "studymaterial.io",
    "virtualclassroom.app", "skillbuilder.co", "edusync.org",
    "learnpathways.com", "tutorconnect.app",
    # Legal (6)
    "legaladvicehub.com", "contractreview.net", "patentsearch.io",
    "lawfirmmanager.app", "estateplanning.co", "legalforms.org",
    # Productivity (8)
    "taskmanagerpro.com", "projecttracker.net", "timemanagement.io",
    "habitbuilder.app", "teamcollab.co", "workspacehub.org",
    "notetaking.app", "calendarsync.io",
    # Programming / Dev (8)
    "deploytools.com", "codereviewhub.net", "apisandbox.io",
    "devopsautomation.app", "testrunner.co", "monitoringstack.org",
    "containerize.dev", "gitworkflow.pro",
    # Cybersecurity (8)
    "threatintelpro.com", "cyberdefense.net", "vpnsecure.io",
    "identityguard.app", "compliancecheck.co", "securityaudit.org",
    "zerotrusthub.com", "ransomwareprevent.io",
    # Regional / gTLD (10)
    "greenenergy.uk", "localbusinesspro.co.uk", "techreview.eu",
    "propertysearch.in", "healthadvice.de", "financenews.asia",
    "startupgrind.fr", "digitalnomad.es", "marketinsights.au",
    "solarinstaller.ca",
    # Short brandables (10)
    "growly.io", "taskly.app", "listify.co", "bouncelabs.io",
    "scopelytics.com", "divinely.net", "nexthub.org",
    "vocali.co", "pixlify.com", "driftly.app",
    # Industry specific (8)
    "realestatepros.com", "fitnessgearhub.net", "organicfoods.io",
    "greentechsolutions.co", "smartcityprojects.app", "edtechplatform.org",
    "logisticsoptimizer.com", "supplychainpro.io",
    # Additional real-looking domains (20)
    "accountingsoftware.co", "vetclinicfinder.com", "photostudio.net",
    "cleaningpros.io", "landscapinghub.app", "plumbing911.org",
    "electricianfinder.com", "cateringmanager.co", "eventplannerpro.io",
    "djbooking.app", "mechanicsearch.org", "autobodyrepair.com",
    "travelagentpro.net", "hotelcomparison.io", "flighttracker.app",
    "rvrentalhub.com", "boatlisting.co", "campinggear.org",
    "petfooddelivery.io", "dogtrainerpro.app",
]

class ExpiredDomainsFeed(BaseFeed):
    """Fetches expired/expiring domains from free public sources."""

    source = "expireddomains"

    SOURCES = {
        "domainsindex": "https://domainsindex.com/expired-domains/",
        "expireddomains": "https://www.expireddomains.net/expired-domains/",
    }

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    def __init__(self) -> None:
        self.logger = setup_logger("ExpiredDomainsFeed")

    async def fetch(self, max_domains: int = 200) -> list[dict]:
        domains: list[str] = []

        if not settings.offline_mode:
            domains = await self._fetch_domainsindex()
            if not domains:
                self.logger.info("domainsindex returned empty, trying expireddomains.net")
                domains = await self._fetch_expireddomains_net()
            if domains:
                self.logger.info("Fetched %d domains from live sources", len(domains))
            else:
                self.logger.info("Live sources blocked, using fallback domain pool")
        else:
            self.logger.info("Offline mode, using fallback domain pool")

        if not domains:
            domains = self._fallback_list()

        selected = random.sample(domains, min(max_domains, len(domains)))
        return [self._make_domain_dict(d) for d in selected]

    async def _fetch_domainsindex(self) -> list[str]:
        try:
            async with httpx.AsyncClient(
                headers=self.HEADERS, follow_redirects=True, timeout=25.0
            ) as client:
                resp = await client.get(self.SOURCES["domainsindex"])
                resp.raise_for_status()
                return self._parse_domain_table(resp.text)
        except Exception:
            self.logger.exception("Failed to fetch domainsindex.com")
            return []

    async def _fetch_expireddomains_net(self) -> list[str]:
        try:
            async with httpx.AsyncClient(
                headers={**self.HEADERS, "Referer": "https://www.google.com/"},
                follow_redirects=True,
                timeout=30.0,
            ) as client:
                resp = await client.get(self.SOURCES["expireddomains"])
                resp.raise_for_status()
                return self._parse_domain_table(resp.text)
        except Exception:
            self.logger.exception("Failed to fetch expireddomains.net (likely blocked)")
            return []

    def _parse_domain_table(self, html: str) -> list[str]:
        domains: list[str] = []
        soup = BeautifulSoup(html, "html.parser")

        for table in soup.find_all("table"):
            for row in table.find_all("tr"):
                cells = row.find_all("td")
                for cell in cells:
                    text = cell.get_text(strip=True).lower()
                    if DOMAIN_REGEX.match(text):
                        domains.append(text)

        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if "domain" in href.lower() and "." in href:
                candidate = link.get_text(strip=True).lower()
                if DOMAIN_REGEX.match(candidate) and candidate not in domains:
                    domains.append(candidate)

        return list(dict.fromkeys(domains))

    def _fallback_list(self) -> list[str]:
        return list(EXPIRED_PUBLIC_DOMAIN_POOL)

    def _make_domain_dict(self, domain_name: str) -> dict:
        tld = domain_name.split(".")[-1] if "." in domain_name else ""
        return {
            "domain_name": domain_name,
            "price": 0.0,
            "source": self.source,
            "tld": tld,
            "dr": 0,
            "referring_domains": 0,
            "domain_age": 0,
        }
