from __future__ import annotations

import asyncio
import socket
import time
from typing import Optional

import httpx

from src.config import settings
from src.utils import setup_logger


class RDAPChecker:
    """Checks domain availability via RDAP bootstrap + DNS fallback."""

    RDAP_BOOTSTRAP = "https://data.iana.org/rdap/dns.json"
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

    CACHE: dict[str, tuple[bool, float]] = {}
    CACHE_TTL = 300

    def __init__(self) -> None:
        self.logger = setup_logger("RDAPChecker")

    async def check(self, domain: str) -> dict:
        domain = domain.lower().strip()
        now = time.time()

        cached = self.CACHE.get(domain)
        if cached is not None and (now - cached[1]) < self.CACHE_TTL:
            return {
                "domain": domain,
                "available": cached[0],
                "method": "cache",
                "confidence": "high",
            }

        if settings.offline_mode:
            self.logger.info("Offline mode — skipping RDAP/DNS for %s", domain)
            result = {
                "domain": domain,
                "available": True,
                "method": "offline",
                "confidence": "low",
            }
            self.CACHE[domain] = (True, now)
            return result

        available = await self._check_rdap(domain)
        if available is not None:
            self.CACHE[domain] = (available, now)
            return {
                "domain": domain,
                "available": available,
                "method": "rdap",
                "confidence": "high",
            }

        available = await self._check_dns(domain)
        if available is not None:
            self.CACHE[domain] = (available, now)
            return {
                "domain": domain,
                "available": available,
                "method": "dns",
                "confidence": "medium",
            }

        return {
            "domain": domain,
            "available": False,
            "method": "error",
            "confidence": "low",
        }

    async def _check_rdap(self, domain: str) -> Optional[bool]:
        tld = domain.rsplit(".", 1)[-1] if "." in domain else ""
        base = self.RDAP_BASE.get(tld)
        if base is None:
            self.logger.debug("No RDAP base for .%s, skipping", tld)
            return None

        url = f"{base}{domain}"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                resp = await client.get(url, follow_redirects=True)
        except httpx.TimeoutException:
            self.logger.warning("RDAP timeout for %s", domain)
            return None
        except httpx.HTTPError as exc:
            self.logger.warning("RDAP HTTP error for %s: %s", domain, exc)
            return None
        except OSError as exc:
            self.logger.warning("RDAP connection error for %s: %s", domain, exc)
            return None

        if resp.status_code == 404:
            return True
        if resp.status_code == 200:
            data = resp.json()
            rdap_class = data.get("objectClassName", "")
            if rdap_class == "domain":
                events = data.get("events", [])
                for ev in events:
                    if ev.get("eventAction") in ("registration", "last change of registration"):
                        return False
            return False
        if resp.status_code in (429, 503):
            self.logger.warning("RDAP rate-limited for %s (HTTP %d)", domain, resp.status_code)
            return None

        self.logger.warning("RDAP unexpected status %d for %s", resp.status_code, domain)
        return None

    async def _check_dns(self, domain: str) -> Optional[bool]:
        try:
            result = await asyncio.to_thread(socket.getaddrinfo, domain, 80)
            if result:
                return False
            return True
        except socket.gaierror:
            return True
        except OSError as exc:
            self.logger.warning("DNS error for %s: %s", domain, exc)
            return None

    async def check_batch(self, domains: list[str], concurrency: int = 20) -> list[dict]:
        sem = asyncio.Semaphore(concurrency)

        async def _worker(domain: str) -> dict:
            async with sem:
                return await self.check(domain)

        tasks = [asyncio.create_task(_worker(d)) for d in domains]
        return await asyncio.gather(*tasks)
