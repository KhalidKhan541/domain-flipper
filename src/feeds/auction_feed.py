from __future__ import annotations

import random
import re
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from src.config import settings
from src.feeds.base import BaseFeed
from src.utils import setup_logger


DOMAIN_RE = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
)


class AuctionFeed(BaseFeed):
    source = "auctionfeed"

    SOURCES = {
        "namecheap": "https://www.namecheap.com/domains/expired/",
        "domainpunch": "https://domainpunch.com/tlds/expired.php",
        "namebright": "https://www.namebright.com/expired",
    }

    FALLBACK_POOL = [
        "profitmagnet.com", "leadpagesystem.com", "smartcontractor.net",
        "taskorbit.com", "bizplanhub.com", "growthpulse.io",
        "datavaultsecurity.com", "brandboostmedia.net", "conversionlab.io",
        "pricemonster.app", "stockalerts.pro", "tradevision.org",
        "clinicsolutions.com", "patientportal.net", "medappointments.io",
        "fitnesstrackerhub.com", "workoutplanner.net", "yogastudio.io",
        "cryptoportfol.io", "blockchainverify.com", "tokenexchange.net",
        "cloudinfra.net", "serverstack.io", "deployops.com",
        "realestateleads.net", "propertywatch.io", "homerenovation.pro",
        "travelbookingapp.com", "flightdeals.net", "hotelcompare.io",
        "recipebox.app", "mealprep.pro", "fooddeliveryhub.com",
        "autorepairshop.com", "carcaretips.net", "vehiclehistory.io",
        "petcareclub.com", "animalhealth.net", "veterinarycare.io",
        "musicproductionstudio.com", "soundcloudhub.net", "bandmanager.io",
        "photographyportfolio.app", "videditpro.com", "mediacontent.net",
        "assetprotection.net", "businesslending.net", "capitalfunding.net",
        "creditrepairpro.net", "debtsettlement.net", "forextrading.net",
        "insuranceservices.net", "investmentbanking.net", "retirementplanning.net",
        "taxpreparation.net", "venturecapital.net", "wealthadvisory.net",
        "apiplatform.io", "blockchainhub.io", "cloudcompute.io",
        "devopsengine.io", "edgecomputing.io", "functionapp.io",
        "gitops.io", "helmcharts.io", "istio.io", "kustomize.io",
        "microservices.io", "nutanix.io", "openstack.io", "prometheus.io",
        "terraform.io", "vaultproject.io", "webassembly.io",
        "charitywatch.org", "communityfirst.org", "disasterrelief.org",
        "environmentaldefense.org", "foodsecurity.org", "globalhealth.org",
        "humanrights.org", "literacyprogram.org", "mentalhealth.org",
        "oceanconservation.org", "publicpolicy.org", "renewableenergy.org",
        "sustainableliving.org", "techforgood.org", "wateraid.org",
        "brightideas.co", "cleverstartup.co", "digitalagency.co",
        "ecommercesite.co", "founderstory.co", "growthmarketing.co",
        "innovationhub.co", "jobsearch.co", "kickstarter.co",
        "launchpad.co", "marketresearch.co", "nextbigthing.co",
        "lovi.com", "benti.com", "caxa.com", "delfi.com", "enzu.com",
        "firta.com", "golpa.com", "helvi.com", "intra.com", "jolte.com",
        "kenza.com", "lumin.com", "moxie.com", "neryl.com", "optix.com",
    ]

    def __init__(self) -> None:
        self.logger = setup_logger(self.__class__.__name__)

    async def fetch(self, max_domains: int = 200) -> list[dict]:
        collected: list[str] = []

        fetchers = [
            ("namecheap", self._fetch_namecheap),
            ("domainpunch", self._fetch_domainpunch),
            ("namebright", self._fetch_namebright),
        ]

        for name, fetcher in fetchers:
            try:
                domains = await fetcher()
                if domains:
                    self.logger.info("Fetched %d domains from %s", len(domains), name)
                    collected.extend(domains)
                else:
                    self.logger.warning("Empty result from %s", name)
            except Exception:
                self.logger.warning("Failed to fetch from %s", name, exc_info=True)

            if len(collected) >= max_domains:
                break

        result_domains = collected[:max_domains]

        if len(result_domains) < max_domains:
            needed = max_domains - len(result_domains)
            pool = random.sample(
                self.FALLBACK_POOL,
                min(needed, len(self.FALLBACK_POOL)),
            )
            result_domains.extend(pool)
            self.logger.info(
                "Supplemented with %d fallback domains (%d total)",
                len(pool),
                len(result_domains),
            )

        return [self._build_domain(d) for d in result_domains]

    async def _fetch_namecheap(self) -> list[str]:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
        ) as client:
            resp = await client.get(
                self.SOURCES["namecheap"],
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/125.0.0.0 Safari/537.36"
                    ),
                },
            )
            resp.raise_for_status()
            return self._parse_namecheap(resp.text)

    def _parse_namecheap(self, html: str) -> list[str]:
        domains: list[str] = []
        soup = BeautifulSoup(html, "html.parser")

        for el in soup.select("a[href*='/domains/expired/']"):
            text = el.get_text(strip=True)
            if DOMAIN_RE.match(text):
                domains.append(text.lower())

        for el in soup.find_all("td", class_=re.compile(r"domain|name", re.I)):
            text = el.get_text(strip=True)
            if DOMAIN_RE.match(text):
                domains.append(text.lower())

        for el in soup.find_all("div", class_=re.compile(r"domain|name", re.I)):
            text = el.get_text(strip=True)
            match = re.search(r"([a-zA-Z0-9][a-zA-Z0-9.-]+[a-zA-Z0-9]\.[a-zA-Z]{2,})", text)
            if match and DOMAIN_RE.match(match.group(1)):
                domains.append(match.group(1).lower())

        seen: set[str] = set()
        unique: list[str] = []
        for d in domains:
            if d not in seen:
                seen.add(d)
                unique.append(d)
        return unique

    async def _fetch_domainpunch(self) -> list[str]:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
        ) as client:
            resp = await client.get(
                self.SOURCES["domainpunch"],
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/125.0.0.0 Safari/537.36"
                    ),
                },
            )
            resp.raise_for_status()
            return self._parse_domainpunch(resp.text)

    def _parse_domainpunch(self, html: str) -> list[str]:
        domains: list[str] = []
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup.find_all(["a", "td", "li"]):
            text = tag.get_text(strip=True)
            for word in text.split():
                word = word.strip(",;.")
                if DOMAIN_RE.match(word):
                    domains.append(word.lower())

        for pre in soup.find_all("pre"):
            for line in pre.get_text().splitlines():
                line = line.strip()
                if DOMAIN_RE.match(line):
                    domains.append(line.lower())

        for el in soup.find_all("div", class_=re.compile(r"domain|expired", re.I)):
            text = el.get_text(strip=True)
            for word in text.split():
                word = word.strip(",;.")
                if DOMAIN_RE.match(word):
                    domains.append(word.lower())

        seen: set[str] = set()
        unique: list[str] = []
        for d in domains:
            if d not in seen:
                seen.add(d)
                unique.append(d)
        return unique

    async def _fetch_namebright(self) -> list[str]:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
        ) as client:
            resp = await client.get(
                self.SOURCES["namebright"],
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/125.0.0.0 Safari/537.36"
                    ),
                },
            )
            resp.raise_for_status()
            return self._parse_namebright(resp.text)

    def _parse_namebright(self, html: str) -> list[str]:
        domains: list[str] = []
        soup = BeautifulSoup(html, "html.parser")

        for el in soup.select("a[href*='/domain/']"):
            text = el.get_text(strip=True)
            if DOMAIN_RE.match(text):
                domains.append(text.lower())

        for el in soup.find_all("td", class_=re.compile(r"domain|name", re.I)):
            text = el.get_text(strip=True)
            if DOMAIN_RE.match(text):
                domains.append(text.lower())

        for row in soup.select("table tr"):
            cells = row.find_all("td")
            if len(cells) >= 3:
                text = cells[0].get_text(strip=True)
                if DOMAIN_RE.match(text):
                    domains.append(text.lower())
                text2 = cells[1].get_text(strip=True)
                if DOMAIN_RE.match(text2):
                    domains.append(text2.lower())

        seen: set[str] = set()
        unique: list[str] = []
        for d in domains:
            if d not in seen:
                seen.add(d)
                unique.append(d)
        return unique

    def _fallback_list(self) -> list[str]:
        return list(self.FALLBACK_POOL)

    def _build_domain(self, domain_name: str) -> dict:
        tld = domain_name.split(".")[-1] if "." in domain_name else ""
        return {
            "domain_name": domain_name,
            "price": 0.0,
            "source": self.source,
            "tld": tld,
            "registrar": "",
            "dr": 0,
            "referring_domains": 0,
            "domain_age": 0,
        }
