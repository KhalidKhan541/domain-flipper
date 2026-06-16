from __future__ import annotations

import re
from typing import Pattern

from src.config import settings
from src.utils import setup_logger


class CommercialAnalyzer:
    CATEGORIES: dict[str, list[str]] = {
        "ai": ["ai", "intelligence", "gpt", "llm", "neural", "chatbot", "machine learning", "deep learning", "ml"],
        "saas": ["saas", "cloud", "app", "platform", "software", "subscription", "automation"],
        "finance": ["finance", "invest", "capital", "wealth", "fund", "stock", "trade", "bank", "crypto", "blockchain", "defi", "nft"],
        "education": ["edu", "learn", "course", "academy", "school", "training", "tutor", "knowledge", "skill"],
        "programming": ["code", "dev", "programming", "developer", "api", "backend", "frontend", "stack", "script"],
        "cybersecurity": ["cyber", "security", "secure", "protect", "shield", "defense", "firewall", "encrypt"],
        "health": ["health", "medical", "care", "wellness", "fitness", "nutrition", "diet", "therapy", "clinic"],
        "fitness": ["fit", "gym", "workout", "exercise", "training", "yoga", "strength"],
        "ecommerce": ["shop", "store", "buy", "cart", "commerce", "retail", "product", "market", "deal"],
        "realestate": ["realestate", "property", "home", "house", "rent", "apartment", "mortgage", "estate", "realtor"],
        "legal": ["law", "legal", "attorney", "lawyer", "justice", "court", "firm", "litigation"],
        "productivity": ["productivity", "task", "manage", "organize", "workflow", "efficiency", "focus", "time"],
    }

    HIGH_VALUE_CATEGORIES: set[str] = {"ai", "finance", "crypto", "saas"}
    MEDIUM_VALUE_CATEGORIES: set[str] = {"health", "realestate", "ecommerce"}

    HIGH_VALUE_KEYWORDS: set[str] = {
        "ai", "crypto", "blockchain", "defi", "nft", "finance", "invest",
        "gpt", "llm", "neural", "machine learning", "deep learning",
    }

    COMMON_WORDS: set[str] = {
        "ace", "app", "ask", "auto", "best", "big", "bit", "blue", "book", "box",
        "call", "cap", "care", "city", "click", "cloud", "club", "code", "cool", "core",
        "data", "day", "deep", "dot", "drive", "drop", "easy", "edge", "eye", "face",
        "fact", "fast", "file", "find", "fire", "first", "fit", "flex", "flow", "food",
        "force", "form", "free", "fresh", "front", "full", "fun", "future", "game", "gate",
        "gear", "gem", "gift", "global", "go", "gold", "good", "great", "green", "grid",
        "grow", "guide", "happy", "head", "health", "heart", "help", "hero", "high", "home",
        "hope", "host", "hot", "house", "hub", "idea", "info", "key", "know", "land",
        "launch", "law", "lead", "learn", "level", "life", "light", "like", "line", "link",
        "list", "live", "load", "local", "lock", "log", "long", "look", "love", "low",
        "luck", "made", "mail", "main", "make", "man", "map", "market", "master", "match",
        "media", "meet", "mind", "mine", "mix", "mobile", "model", "money", "moon", "more",
        "move", "music", "name", "need", "net", "new", "next", "nice", "note", "now",
        "one", "only", "open", "order", "over", "own", "page", "paid", "part", "pass",
        "path", "pay", "peace", "people", "phone", "photo", "pick", "place", "plan", "play",
        "point", "power", "press", "price", "prime", "print", "pro", "pure", "push", "rank",
        "rate", "reach", "read", "ready", "real", "red", "rest", "result", "review", "ride",
        "right", "rise", "risk", "river", "road", "rock", "role", "room", "root", "rule",
        "run", "safe", "sale", "save", "scale", "school", "score", "sea", "search", "secure",
        "seed", "sell", "send", "sense", "serve", "shape", "share", "ship", "shop", "short",
        "show", "side", "sign", "simple", "site", "six", "size", "skill", "sky", "smart",
        "smile", "snap", "soft", "solar", "solid", "solve", "song", "soon", "sort", "sound",
        "source", "space", "speed", "spin", "sport", "spot", "star", "start", "state", "stay",
        "step", "stock", "stone", "stop", "store", "storm", "story", "stream", "street", "strong",
        "study", "style", "sun", "super", "supply", "support", "table", "take", "talk", "target",
        "task", "team", "test", "text", "theme", "thing", "think", "three", "time", "tiny",
        "tip", "title", "today", "tone", "tool", "top", "total", "touch", "tour", "town",
        "track", "trade", "train", "travel", "treat", "tree", "trend", "trial", "trip", "true",
        "trust", "truth", "try", "turn", "type", "union", "unit", "use", "user", "valid",
        "value", "venture", "video", "view", "vision", "visit", "voice", "walk", "want", "warm",
        "watch", "water", "wave", "way", "wealth", "web", "weight", "well", "west", "white",
        "wide", "will", "win", "wind", "window", "wine", "wing", "wire", "wise", "word",
        "work", "world", "worth", "write", "year", "yes", "young", "zone",
    }

    SEGMENT_SPLIT_RE: Pattern = re.compile(r"[-.\d]+")

    def __init__(self) -> None:
        self.logger = setup_logger("CommercialAnalyzer")

    async def analyze(self, domain_name: str) -> dict:
        self.logger.info("Analyzing commercial potential for: %s", domain_name)
        sld, tld = self._parse_domain(domain_name)

        category = self._classify_category(sld)
        self.logger.debug("Classified category: %s", category)

        brandability = self._score_brandability(sld, tld)
        keyword_value = self._score_keyword_value(sld, category)
        memorability = self._score_memorability(sld)
        resale_demand = self._score_resale_demand(category, brandability)

        commercial_score = self._compute_commercial_score(
            brandability, keyword_value, memorability, resale_demand
        )

        result = {
            "category": category,
            "brandability": round(brandability, 1),
            "keyword_value": round(keyword_value, 1),
            "memorability": round(memorability, 1),
            "resale_demand": resale_demand,
            "commercial_score": round(commercial_score, 1),
        }

        self.logger.info("Commercial analysis result: %s", result)
        return result

    def _parse_domain(self, domain: str) -> tuple[str, str]:
        domain = domain.lower().strip()
        domain = re.sub(r"^https?://", "", domain)
        domain = re.sub(r"^www\.", "", domain)
        domain = domain.split("/")[0]

        parts = domain.split(".")
        if len(parts) >= 2:
            return parts[-2], parts[-1]
        return parts[0], ""

    def _classify_category(self, sld: str) -> str:
        segments = [s for s in self.SEGMENT_SPLIT_RE.split(sld) if s]
        if not segments:
            return "general"

        best_category = "general"
        best_count = 0

        for category, keywords in self.CATEGORIES.items():
            count = 0
            for segment in segments:
                for keyword in keywords:
                    kw_norm = keyword.replace(" ", "")
                    if segment == kw_norm or (len(kw_norm) >= 2 and kw_norm in segment):
                        count += 1
                        break

            if count > best_count:
                best_count = count
                best_category = category

        return best_category

    def _score_brandability(self, sld: str, tld: str) -> float:
        length = len(sld)
        if length <= 3:
            score = 95.0
        elif length == 4:
            score = 85.0
        elif length == 5:
            score = 70.0
        elif length == 6:
            score = 60.0
        else:
            score = max(0.0, 60.0 - (length - 6) * 5)

        if sld in self.COMMON_WORDS:
            score += 15.0

        if tld == "com":
            score += 10.0

        hyphen_count = sld.count("-")
        if hyphen_count == 0:
            score += 10.0
        elif hyphen_count >= 2:
            score -= 15.0

        number_count = sum(c.isdigit() for c in sld)
        if number_count == 0:
            score += 5.0
        elif number_count == 1:
            score -= 5.0
        else:
            score -= 15.0

        return max(0.0, min(100.0, score))

    def _score_keyword_value(self, sld: str, category: str) -> float:
        score = 0.0

        if category != "general":
            score += 70.0

        normalized_sld = sld.lower()
        for hvc in self.HIGH_VALUE_CATEGORIES:
            if hvc in normalized_sld:
                score += 10.0
                break

        for kw in self.HIGH_VALUE_KEYWORDS:
            kw_norm = kw.replace(" ", "")
            if kw_norm in normalized_sld:
                score += 10.0
                break

        segments = [s for s in self.SEGMENT_SPLIT_RE.split(sld) if s]
        all_keywords: set[str] = set()
        for kw_list in self.CATEGORIES.values():
            for kw in kw_list:
                all_keywords.add(kw.replace(" ", ""))

        for segment in segments:
            if segment in all_keywords:
                score += 15.0
                break

        return max(0.0, min(100.0, score))

    def _score_memorability(self, sld: str) -> float:
        length = len(sld)

        if 3 <= length <= 6:
            score = 85.0
        elif 7 <= length <= 10:
            score = 65.0
        else:
            score = 40.0

        if sld in self.COMMON_WORDS:
            score += 15.0

        if "-" not in sld:
            score += 10.0

        return max(0.0, min(100.0, score))

    def _score_resale_demand(self, category: str, brandability: float) -> str:
        if category in self.HIGH_VALUE_CATEGORIES:
            demand = "high"
        elif category in self.MEDIUM_VALUE_CATEGORIES:
            demand = "medium"
        else:
            demand = "low"

        if brandability > 70:
            levels = {"low": "medium", "medium": "high", "high": "high"}
            demand = levels.get(demand, demand)

        return demand

    def _compute_commercial_score(
        self,
        brandability: float,
        keyword_value: float,
        memorability: float,
        resale_demand: str,
    ) -> float:
        demand_map = {"low": 30.0, "medium": 65.0, "high": 90.0}
        demand_score = demand_map.get(resale_demand, 30.0)

        score = (
            0.35 * brandability
            + 0.30 * keyword_value
            + 0.20 * memorability
            + 0.15 * demand_score
        )

        return max(0.0, min(100.0, score))
