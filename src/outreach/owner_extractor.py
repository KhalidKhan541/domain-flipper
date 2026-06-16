from __future__ import annotations

from typing import Any

import httpx

from src.config import settings
from src.utils import setup_logger

MOCK_OWNER_DATA: dict[str, dict[str, str]] = {
    "google.com": {
        "registrant_name": "Google LLC",
        "registrant_org": "Google LLC",
        "registrant_email": "domsreg@google.com",
        "registrar": "MarkMonitor, Inc.",
    },
    "openai.com": {
        "registrant_name": "OpenAI OpCo, LLC",
        "registrant_org": "OpenAI OpCo, LLC",
        "registrant_email": "domain-admin@openai.com",
        "registrar": "MarkMonitor, Inc.",
    },
    "stripe.com": {
        "registrant_name": "Stripe, Inc.",
        "registrant_org": "Stripe, Inc.",
        "registrant_email": "domains@stripe.com",
        "registrar": "MarkMonitor, Inc.",
    },
    "cloudflare.com": {
        "registrant_name": "Cloudflare, Inc.",
        "registrant_org": "Cloudflare, Inc.",
        "registrant_email": "domains@cloudflare.com",
        "registrar": "MarkMonitor, Inc.",
    },
    "anthropic.com": {
        "registrant_name": "Anthropic PBC",
        "registrant_org": "Anthropic PBC",
        "registrant_email": "domains@anthropic.com",
        "registrar": "NameCheap, Inc.",
    },
    "perplexity.ai": {
        "registrant_name": "Perplexity AI, Inc.",
        "registrant_org": "Perplexity AI, Inc.",
        "registrant_email": "domains@perplexity.ai",
        "registrar": "NameCheap, Inc.",
    },
    "notion.so": {
        "registrant_name": "Notion Labs, Inc.",
        "registrant_org": "Notion Labs, Inc.",
        "registrant_email": "domains@makenotion.com",
        "registrar": "NameCheap, Inc.",
    },
    "vercel.com": {
        "registrant_name": "Vercel Inc.",
        "registrant_org": "Vercel Inc.",
        "registrant_email": "domains@vercel.com",
        "registrar": "NameCheap, Inc.",
    },
    "linear.app": {
        "registrant_name": "Linear Orbit, Inc.",
        "registrant_org": "Linear Orbit, Inc.",
        "registrant_email": "domains@linear.app",
        "registrar": "NameCheap, Inc.",
    },
    "supabase.com": {
        "registrant_name": "Supabase, Inc.",
        "registrant_org": "Supabase, Inc.",
        "registrant_email": "domains@supabase.com",
        "registrar": "NameCheap, Inc.",
    },
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


class OwnerExtractor:
    RDAP_BASE = {
        "com": "https://rdap.verisign.com/com/v1/domain/",
        "net": "https://rdap.verisign.com/net/v1/domain/",
        "org": "https://rdap.pir.org/rdap/domain/",
        "io": "https://rdap.nic.io/domain/",
        "co": "https://rdap.nic.co/domain/",
        "app": "https://rdap.nic.google/domain/",
        "dev": "https://rdap.nic.dev/domain/",
        "ai": "https://rdap.nic.ai/domain/",
        "tv": "https://rdap.nic.tv/domain/",
        "me": "https://rdap.nic.me/domain/",
        "info": "https://rdap.afilias.net/rdap/domain/",
        "biz": "https://rdap.nic.biz/domain/",
        "pro": "https://rdap.afilias.net/rdap/domain/",
        "uk": "https://rdap.nominet.uk/domain/",
        "in": "https://rdap.registry.in/domain/",
        "tech": "https://rdap.nic.tech/domain/",
    }

    def __init__(self) -> None:
        self.logger = setup_logger("OwnerExtractor")

    async def extract(self, domain: str) -> dict[str, Any]:
        domain = domain.lower().strip()

        if settings.offline_mode:
            self.logger.info("Offline mode — returning mock owner data for %s", domain)
            mock = MOCK_OWNER_DATA.get(domain, MOCK_OWNER_DATA.get("google.com"))
            return {
                "domain": domain,
                "registrant_name": mock["registrant_name"],
                "registrant_org": mock["registrant_org"],
                "registrant_email": mock["registrant_email"],
                "registrar": mock["registrar"],
                "status": "found",
            }

        tld = domain.rsplit(".", 1)[-1] if "." in domain else ""
        base = self.RDAP_BASE.get(tld)
        if base is None:
            self.logger.debug("No RDAP base for .%s — cannot extract owner", tld)
            return {
                "domain": domain,
                "registrant_name": None,
                "registrant_org": None,
                "registrant_email": None,
                "registrar": None,
                "status": "not_found",
            }

        url = f"{base}{domain}"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                resp = await client.get(url, follow_redirects=True)
        except httpx.TimeoutException:
            self.logger.warning("RDAP timeout for %s", domain)
            return self._error_result(domain, "timeout")
        except httpx.HTTPError as exc:
            self.logger.warning("RDAP HTTP error for %s: %s", domain, exc)
            return self._error_result(domain, "http_error")
        except OSError as exc:
            self.logger.warning("RDAP connection error for %s: %s", domain, exc)
            return self._error_result(domain, "connection_error")

        if resp.status_code == 404:
            self.logger.info("Domain %s not found in RDAP", domain)
            return self._error_result(domain, "not_found")

        if resp.status_code != 200:
            self.logger.warning("RDAP unexpected status %d for %s", resp.status_code, domain)
            return self._error_result(domain, "unexpected_status")

        try:
            data = resp.json()
        except Exception as exc:
            self.logger.warning("Failed to parse RDAP JSON for %s: %s", domain, exc)
            return self._error_result(domain, "parse_error")

        return self._parse_rdap_response(domain, data)

    def _parse_rdap_response(self, domain: str, data: dict[str, Any]) -> dict[str, Any]:
        entities = data.get("entities", [])

        registrant_name: str | None = None
        registrant_org: str | None = None
        registrant_email: str | None = None
        registrar: str | None = None

        for entity in entities:
            roles = entity.get("roles", [])
            is_registrant = "registrant" in roles
            is_registrar = "registrar" in roles

            if is_registrar:
                vcard = self._find_vcard(entity)
                if vcard:
                    name = self._vcard_get(vcard, "fn")
                    if name:
                        registrar = name

            if is_registrant:
                vcard = self._find_vcard(entity)
                if vcard:
                    name = self._vcard_get(vcard, "fn")
                    org = self._vcard_get(vcard, "org")
                    email = self._vcard_get(vcard, "email")

                    if name:
                        registrant_name = name
                    if org:
                        registrant_org = org
                    if email:
                        registrant_email = email

        if registrant_name is None and registrant_email is None:
            for entity in entities:
                if "registrant" in entity.get("roles", []):
                    continue
                vcard = self._find_vcard(entity)
                if vcard is None:
                    continue
                name = self._vcard_get(vcard, "fn")
                org = self._vcard_get(vcard, "org")
                email = self._vcard_get(vcard, "email")
                if name:
                    registrant_name = name
                if org:
                    registrant_email = org
                if email:
                    registrant_email = email
                if name or email:
                    break

        status = "found" if (registrant_name or registrant_email or registrar) else "not_found"

        return {
            "domain": domain,
            "registrant_name": registrant_name,
            "registrant_org": registrant_org,
            "registrant_email": registrant_email,
            "registrar": registrar,
            "status": status,
        }

    def _find_vcard(self, entity: dict[str, Any]) -> list[list[Any]] | None:
        vcard_array = entity.get("vcardArray")
        if vcard_array is not None and isinstance(vcard_array, list) and len(vcard_array) >= 2:
            return vcard_array[1]
        return None

    def _vcard_get(self, vcard: list[list[Any]], field: str) -> str | None:
        for entry in vcard:
            if not isinstance(entry, list) or len(entry) < 4:
                continue
            if entry[0] == field and entry[3]:
                value = entry[3]
                if isinstance(value, str):
                    return value.strip()
                if isinstance(value, list):
                    for v in value:
                        if isinstance(v, dict):
                            for k in ("uri", "email", "text", "value"):
                                val = v.get(k)
                                if val:
                                    return str(val).strip()
                        elif isinstance(v, str):
                            return v.strip()
                if isinstance(value, dict):
                    for k in ("uri", "email", "text", "value"):
                        val = value.get(k)
                        if val:
                            return str(val).strip()
                return str(value).strip()
        return None

    def _error_result(self, domain: str, reason: str) -> dict[str, Any]:
        return {
            "domain": domain,
            "registrant_name": None,
            "registrant_org": None,
            "registrant_email": None,
            "registrar": None,
            "status": "error",
            "error_reason": reason,
        }
