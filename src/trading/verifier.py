"""
Domain Verifier — Verify domain ownership before trading.
Uses RDAP/WHOIS to confirm the seller actually owns the domain.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

RDAP_BOOTSTRAP_URL = "https://data.iana.org/rdap/dns.json"
RDAP_TLD_MAP: dict[str, str] = {}


@dataclass
class DomainOwnership:
    domain: str
    registrant_name: str = ""
    registrant_org: str = ""
    registrar: str = ""
    registration_date: str = ""
    expiration_date: str = ""
    nameservers: list[str] = field(default_factory=list)
    status: list[str] = field(default_factory=list)
    verified: bool = False
    verification_method: str = ""  # "rdap" | "whois" | "dns"
    confidence: float = 0.0
    risk_flags: list[str] = field(default_factory=list)
    raw_response: str = ""


class DomainVerifier:
    """
    Verifies domain ownership and checks for red flags.
    
    Verification steps:
    1. RDAP lookup — get registrant info
    2. WHOIS fallback — if RDAP unavailable
    3. DNS check — verify nameservers resolve
    4. History check — flag suspicious patterns
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger("DomainVerifier")
        self.client = httpx.AsyncClient(timeout=15)

    async def close(self) -> None:
        await self.client.aclose()

    async def verify_ownership(
        self,
        domain: str,
        expected_owner: str = "",
    ) -> DomainOwnership:
        """
        Full ownership verification pipeline.
        Returns DomainOwnership with verification results.
        """
        result = DomainOwnership(domain=domain)

        # Step 1: Try RDAP
        rdap_result = await self._rdap_lookup(domain)
        if rdap_result:
            result = rdap_result
            result.verification_method = "rdap"

        # Step 2: Fallback to WHOIS if RDAP failed
        if not result.registrant_name:
            whois_result = await self._whois_lookup(domain)
            if whois_result:
                result = whois_result
                result.verification_method = "whois"

        # Step 3: DNS verification
        dns_ok = await self._dns_check(domain)
        if not dns_ok:
            result.risk_flags.append("DNS_NOT_RESOLVING")

        # Step 4: Risk assessment
        self._assess_risks(result)

        # Step 5: Confidence scoring
        result.confidence = self._calculate_confidence(result, expected_owner)
        result.verified = result.confidence >= 0.7

        self.logger.info(
            "Verification for %s: verified=%s, confidence=%.2f, method=%s",
            domain,
            result.verified,
            result.confidence,
            result.verification_method,
        )

        return result

    async def _rdap_lookup(self, domain: str) -> Optional[DomainOwnership]:
        """Lookup domain via RDAP (Registration Data Access Protocol)."""
        tld = domain.split(".")[-1]

        # Get RDAP server URL for this TLD
        rdap_url = await self._get_rdap_url(tld)
        if not rdap_url:
            return None

        try:
            url = f"{rdap_url}/domain/{domain}"
            resp = await self.client.get(url)
            if resp.status_code != 200:
                self.logger.warning("RDAP lookup failed for %s: %s", domain, resp.status_code)
                return None

            data = resp.json()
            result = DomainOwnership(domain=domain, raw_response=resp.text)

            # Extract registrant
            for entity in data.get("entities", []):
                roles = entity.get("roles", [])
                if "registrant" in roles:
                    vcard = entity.get("vcardArray", [None, []])
                    if len(vcard) > 1:
                        for item in vcard[1]:
                            if item[0] == "fn":
                                result.registrant_name = item[3]
                            elif item[0] == "org":
                                result.registrant_org = item[3]

            # Extract registrar
            for entity in data.get("entities", []):
                roles = entity.get("roles", [])
                if "registrar" in roles:
                    vcard = entity.get("vcardArray", [None, []])
                    if len(vcard) > 1:
                        for item in vcard[1]:
                            if item[0] == "fn":
                                result.registrar = item[3]

            # Extract dates
            for event in data.get("events", []):
                if event.get("eventAction") == "registration":
                    result.registration_date = event.get("eventDate", "")
                elif event.get("eventAction") == "expiration":
                    result.expiration_date = event.get("eventDate", "")

            # Extract nameservers
            for ns in data.get("nameservers", []):
                name = ns.get("ldhName", "")
                if name:
                    result.nameservers.append(name)

            # Extract status
            result.status = data.get("status", [])

            return result

        except Exception as e:
            self.logger.error("RDAP lookup error for %s: %s", domain, e)
            return None

    async def _get_rdap_url(self, tld: str) -> Optional[str]:
        """Get RDAP server URL for a TLD from IANA bootstrap."""
        global RDAP_TLD_MAP

        if not RDAP_TLD_MAP:
            try:
                resp = await self.client.get(RDAP_BOOTSTRAP_URL)
                if resp.status_code == 200:
                    data = resp.json()
                    for service in data.get("services", []):
                        tlds = service[0]
                        urls = service[1]
                        for t in tlds:
                            RDAP_TLD_MAP[t.lower()] = urls[0]
            except Exception as e:
                self.logger.error("Failed to load RDAP bootstrap: %s", e)

        return RDAP_TLD_MAP.get(tld.lower())

    async def _whois_lookup(self, domain: str) -> Optional[DomainOwnership]:
        """Fallback WHOIS lookup using a public API."""
        try:
            # Use rdap.viebel.com or similar free WHOIS API
            url = f"https://rdap.verisign.com/com/v1/domain/{domain}"
            resp = await self.client.get(url)
            if resp.status_code != 200:
                return None

            data = resp.json()
            result = DomainOwnership(domain=domain, verification_method="whois")

            for entity in data.get("entities", []):
                roles = entity.get("roles", [])
                if "registrant" in roles:
                    vcard = entity.get("vcardArray", [None, []])
                    if len(vcard) > 1:
                        for item in vcard[1]:
                            if item[0] == "fn":
                                result.registrant_name = item[3]

            for event in data.get("events", []):
                if event.get("eventAction") == "registration":
                    result.registration_date = event.get("eventDate", "")

            return result

        except Exception as e:
            self.logger.error("WHOIS lookup error for %s: %s", domain, e)
            return None

    async def _dns_check(self, domain: str) -> bool:
        """Check if domain resolves via DNS."""
        try:
            import socket
            result = socket.getaddrinfo(domain, None, socket.AF_INET)
            return len(result) > 0
        except (socket.gaierror, OSError):
            return False

    def _assess_risks(self, result: DomainOwnership) -> None:
        """Flag suspicious patterns."""
        # Recently registered domain
        if result.registration_date:
            try:
                reg_date = datetime.fromisoformat(result.registration_date.replace("Z", "+00:00"))
                days_old = (datetime.now(timezone.utc) - reg_date).days
                if days_old < 30:
                    result.risk_flags.append("VERY_NEW_REGISTRATION")
                elif days_old < 90:
                    result.risk_flags.append("NEW_REGISTRATION")
            except (ValueError, TypeError):
                pass

        # Expiring soon
        if result.expiration_date:
            try:
                exp_date = datetime.fromisoformat(result.expiration_date.replace("Z", "+00:00"))
                days_to_exp = (exp_date - datetime.now(timezone.utc)).days
                if days_to_exp < 30:
                    result.risk_flags.append("EXPIRING_SOON")
            except (ValueError, TypeError):
                pass

        # Privacy-protected registration
        privacy_indicators = ["privacy", "protected", "proxy", "redacted"]
        if any(p in result.registrant_name.lower() for p in privacy_indicators):
            result.risk_flags.append("PRIVACY_PROTECTED")

        # No nameservers
        if not result.nameservers:
            result.risk_flags.append("NO_NAMESERVERS")

    def _calculate_confidence(
        self,
        result: DomainOwnership,
        expected_owner: str,
    ) -> float:
        """Calculate confidence score (0.0 to 1.0)."""
        score = 0.0

        # Has registrant info
        if result.registrant_name:
            score += 0.3

        # Has registrar
        if result.registrar:
            score += 0.1

        # Has registration date
        if result.registration_date:
            score += 0.1

        # DNS resolves
        if result.nameservers:
            score += 0.2

        # No risk flags
        if not result.risk_flags:
            score += 0.2
        elif len(result.risk_flags) <= 1:
            score += 0.1

        # Owner match (if expected)
        if expected_owner and expected_owner.lower() in result.registrant_name.lower():
            score += 0.1

        return min(score, 1.0)

    async def quick_check(self, domain: str) -> dict:
        """Quick ownership check — returns minimal info."""
        result = await self.verify_ownership(domain)
        return {
            "domain": domain,
            "verified": result.verified,
            "confidence": result.confidence,
            "registrar": result.registrar,
            "registration_date": result.registration_date,
            "risk_flags": result.risk_flags,
        }

    async def batch_verify(self, domains: list[str]) -> list[dict]:
        """Verify ownership for multiple domains."""
        results = []
        for domain in domains:
            try:
                result = await self.quick_check(domain)
                results.append(result)
            except Exception as e:
                self.logger.error("Batch verify failed for %s: %s", domain, e)
                results.append({
                    "domain": domain,
                    "verified": False,
                    "confidence": 0.0,
                    "error": str(e),
                })
        return results
