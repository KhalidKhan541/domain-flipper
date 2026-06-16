from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup

from src.config import settings
from src.utils import async_retry, setup_logger

ADULT_KEYWORDS = frozenset({"adult", "xxx", "porn", "nsfw"})
GAMBLING_KEYWORDS = frozenset({"casino", "poker", "betting", "gambling"})
PHARMA_KEYWORDS = frozenset({"pharmacy", "viagra", "cialis", "prescription"})

WAYBACK_CDX_URL = "https://web.archive.org/cdx/search/cdx"
SAFE_BROWSING_URL = "https://safebrowsing.googleapis.com/v4/threatMatches:find"

DEFAULT_RESPONSE: dict[str, Any] = {
    "cleanliness_score": 50.0,
    "trust_score": 50.0,
    "has_adult_history": False,
    "has_gambling_history": False,
    "has_pharma_history": False,
    "has_malware_history": False,
    "wayback_snapshots": 0,
    "first_seen": "",
    "ownership_changes": 0,
    "spam_indicators": [],
    "is_clean": False,
}


class HistoryAnalyzer:
    def __init__(self) -> None:
        self.logger = setup_logger("HistoryAnalyzer")

    def _offline_defaults(self) -> dict[str, Any]:
        return {
            "cleanliness_score": 70.0,
            "trust_score": 65.0,
            "has_adult_history": False,
            "has_gambling_history": False,
            "has_pharma_history": False,
            "has_malware_history": False,
            "wayback_snapshots": 0,
            "first_seen": "",
            "ownership_changes": 0,
            "spam_indicators": [],
            "is_clean": True,
        }

    async def analyze(self, domain: str) -> dict[str, Any]:
        if settings.offline_mode:
            self.logger.info("Offline mode — skipping HTTP calls for %s", domain)
            return self._offline_defaults()

        result = dict(DEFAULT_RESPONSE)
        spam_indicators: list[str] = []

        snapshots = await self._fetch_wayback_snapshots(domain)
        has_history = bool(snapshots)

        if snapshots:
            result["wayback_snapshots"] = len(snapshots)
            result["first_seen"] = self._parse_first_seen(snapshots)

            try:
                flags, spam = await self._classify_from_snapshots(domain, snapshots[:3])
                result["has_adult_history"] = flags["adult"]
                result["has_gambling_history"] = flags["gambling"]
                result["has_pharma_history"] = flags["pharma"]
                spam_indicators.extend(spam)
            except Exception:
                self.logger.warning("Content classification failed for %s", domain, exc_info=True)

        try:
            malware = await self._check_safe_browsing(domain)
            result["has_malware_history"] = malware
            if malware:
                spam_indicators.append("flagged_by_safe_browsing")
        except Exception:
            self.logger.warning("Safe Browsing check failed for %s", domain, exc_info=True)

        result["spam_indicators"] = spam_indicators
        result["cleanliness_score"] = self._compute_cleanliness(result, has_history, spam_indicators)
        result["trust_score"] = self._compute_trust(result["cleanliness_score"], result["wayback_snapshots"])
        result["is_clean"] = self._check_is_clean(result)

        return result

    @async_retry(max_attempts=2, delay=0.1)
    async def _fetch_wayback_snapshots(self, domain: str) -> list[list[str]]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                WAYBACK_CDX_URL,
                params={"url": domain, "output": "json", "limit": 10, "fl": "timestamp,original"},
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list) and len(data) > 1:
                return data[1:]
            return []

    def _parse_first_seen(self, snapshots: list[list[str]]) -> str:
        timestamps = [row[0] for row in snapshots if row]
        if not timestamps:
            return ""
        earliest = min(timestamps)
        return earliest[:4] if len(earliest) >= 4 else earliest

    async def _classify_from_snapshots(
        self, domain: str, snapshots: list[list[str]]
    ) -> tuple[dict[str, bool], list[str]]:
        flags: dict[str, bool] = {"adult": False, "gambling": False, "pharma": False}
        spam: list[str] = []

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            for row in snapshots:
                if len(row) < 2:
                    continue
                ts, original_url = row[0], row[1]
                archive_url = f"https://web.archive.org/web/{ts}/{original_url}"
                try:
                    resp = await client.get(archive_url)
                    if resp.status_code != 200:
                        continue
                    soup = BeautifulSoup(resp.text, "html.parser")
                    text_content = self._extract_text(soup).lower()
                    for kw in ADULT_KEYWORDS:
                        if kw in text_content:
                            flags["adult"] = True
                            spam.append(f"adult_content_{kw}")
                            break
                    for kw in GAMBLING_KEYWORDS:
                        if kw in text_content:
                            flags["gambling"] = True
                            spam.append(f"gambling_content_{kw}")
                            break
                    for kw in PHARMA_KEYWORDS:
                        if kw in text_content:
                            flags["pharma"] = True
                            spam.append(f"pharma_content_{kw}")
                            break
                except Exception:
                    self.logger.debug("Failed to fetch archived page %s", archive_url, exc_info=True)
                    continue

            return flags, spam

    @staticmethod
    def _extract_text(soup: BeautifulSoup) -> str:
        parts: list[str] = []
        title = soup.find("title")
        if title:
            parts.append(title.get_text())
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            parts.append(str(meta_desc["content"]))
        return " ".join(parts)

    @async_retry(max_attempts=2, delay=0.1)
    async def _check_safe_browsing(self, domain: str) -> bool:
        api_key = getattr(settings, "google_safe_browsing_key", None)
        if not api_key:
            return False

        target = domain if domain.startswith(("http://", "https://")) else f"https://{domain}"
        payload = {
            "client": {"clientId": "domain-flipper", "clientVersion": "1.0.0"},
            "threatInfo": {
                "threatTypes": [
                    "THREAT_TYPE_UNSPECIFIED",
                    "MALWARE",
                    "SOCIAL_ENGINEERING",
                    "UNWANTED_SOFTWARE",
                    "POTENTIALLY_HARMFUL_APPLICATION",
                ],
                "platformTypes": ["ANY_PLATFORM"],
                "threatEntryTypes": ["URL"],
                "threatEntries": [{"url": target}],
            },
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{SAFE_BROWSING_URL}?key={api_key}", json=payload)
            if resp.status_code == 200:
                data = resp.json()
                matches = data.get("matches", [])
                return len(matches) > 0
            self.logger.warning(
                "Safe Browsing API returned %d for %s", resp.status_code, domain
            )
            return False

    @staticmethod
    def _compute_cleanliness(
        result: dict[str, Any], has_history: bool, spam_indicators: list[str]
    ) -> float:
        score = 100.0
        if result["has_adult_history"]:
            score -= 30.0
        if result["has_gambling_history"]:
            score -= 25.0
        if result["has_pharma_history"]:
            score -= 20.0
        if result["has_malware_history"]:
            score -= 40.0
        pharma_spam = [s for s in spam_indicators if "pharma" in s]
        score -= 15.0 * min(len(pharma_spam), 3)
        excess = len(spam_indicators) - min(len(pharma_spam), 3)
        if excess > 5:
            score -= 5.0 * (excess - 5)
        if not has_history:
            score -= 10.0
        return max(0.0, min(100.0, score))

    @staticmethod
    def _compute_trust(cleanliness: float, snapshots: int) -> float:
        snap_factor = min(100.0, snapshots / 10.0)
        return round(0.7 * cleanliness + 0.3 * snap_factor, 2)

    @staticmethod
    def _check_is_clean(result: dict[str, Any]) -> bool:
        return all([
            not result["has_adult_history"],
            not result["has_gambling_history"],
            not result["has_pharma_history"],
            not result["has_malware_history"],
            result["cleanliness_score"] >= 60.0,
        ])
