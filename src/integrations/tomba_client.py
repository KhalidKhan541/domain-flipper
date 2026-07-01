from __future__ import annotations

import logging
from typing import Any, Optional

import aiohttp

logger = logging.getLogger(__name__)

BASE_URL = "https://api.tomba.io/v1"


class TombaClient:
    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key
        self._headers: dict[str, str] = {}
        if api_key:
            self._headers["X-Tomba-Key"] = api_key

    def _has_key(self) -> bool:
        if self.api_key:
            return True
        logger.warning("Tomba API key not configured — returning empty results")
        return False

    async def _get(self, path: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        url = f"{BASE_URL}{path}"
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=self._headers, params=params) as resp:
                resp.raise_for_status()
                return await resp.json()

    async def find_email(
        self, domain: str, first_name: str = "", last_name: str = ""
    ) -> dict[str, Any]:
        if not self._has_key():
            return {"email": None, "confidence": 0, "sources": [], "error": "API key not configured"}

        try:
            params: dict[str, Any] = {"domain": domain}
            if first_name:
                params["first_name"] = first_name
            if last_name:
                params["last_name"] = last_name

            data = await self._get("/email-finder", params=params)
            result = data.get("data", data)
            return {
                "email": result.get("email"),
                "confidence": result.get("confidence", 0),
                "sources": result.get("sources", []),
            }
        except Exception as exc:
            logger.error("Tomba find_email failed for %s: %s", domain, exc)
            return {"email": None, "confidence": 0, "sources": [], "error": str(exc)}

    async def find_emails(self, domain: str, limit: int = 10) -> list[dict[str, Any]]:
        if not self._has_key():
            return []

        try:
            data = await self._get("/email-count", params={"domain": domain})
            emails: list[dict[str, Any]] = []
            raw = data.get("data", data)
            if isinstance(raw, dict):
                raw = raw.get("emails", [])

            for entry in raw[:limit]:
                emails.append(
                    {
                        "email": entry.get("email"),
                        "first_name": entry.get("first_name", ""),
                        "last_name": entry.get("last_name", ""),
                        "position": entry.get("position", ""),
                        "confidence": entry.get("confidence", 0),
                    }
                )
            return emails
        except Exception as exc:
            logger.error("Tomba find_emails failed for %s: %s", domain, exc)
            return []

    async def verify_email(self, email: str) -> dict[str, Any]:
        if not self._has_key():
            return {"valid": False, "deliverable": False, "reason": "API key not configured"}

        try:
            data = await self._get("/email-verifier", params={"email": email})
            result = data.get("data", data)
            return {
                "valid": result.get("status") == "valid",
                "deliverable": result.get("mx_found", False),
                "reason": result.get("reason", ""),
            }
        except Exception as exc:
            logger.error("Tomba verify_email failed for %s: %s", email, exc)
            return {"valid": False, "deliverable": False, "reason": str(exc)}

    async def enrich_domain(self, domain: str) -> dict[str, Any]:
        if not self._has_key():
            return {"organization": None, "email_patterns": [], "error": "API key not configured"}

        try:
            data = await self._get(f"/domain/{domain}")
            result = data.get("data", data)
            return {
                "organization": {
                    "name": result.get("organization", ""),
                    "industry": result.get("industry", ""),
                    "description": result.get("description", ""),
                    "website": result.get("website", domain),
                    "employees": result.get("employees", ""),
                    "location": result.get("location", ""),
                },
                "email_patterns": result.get("patterns", []),
            }
        except Exception as exc:
            logger.error("Tomba enrich_domain failed for %s: %s", domain, exc)
            return {"organization": None, "email_patterns": [], "error": str(exc)}
