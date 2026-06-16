import random

from src.utils import setup_logger
from src.generators.base import BaseDomainGenerator

logger = setup_logger(__name__)

NICHE_KEYWORDS = {
    "ai": ["ai", "intelligence", "gpt", "llm", "neural", "chatbot", "ml", "deep", "learning", "model", "inference", "training", "pipeline", "agent", "automation", "cognition", "synthetic", "embedding", "vector", "transformer", "predict", "analytics"],
    "saas": ["saas", "cloud", "app", "platform", "software", "subscription", "automation", "workflow", "dashboard", "portal", "hub", "suite", "manager", "console", "studio", "engine", "kit", "toolkit"],
    "finance": ["finance", "invest", "capital", "wealth", "fund", "stock", "trade", "bank", "crypto", "blockchain", "defi", "nft", "token", "wallet", "swap", "yield", "stake", "ledger", "vault", "trust", "equity", "bond"],
    "health": ["health", "medical", "care", "wellness", "fitness", "nutrition", "diet", "therapy", "clinic", "diagnosis", "patient", "doctor", "nurse", "hospital", "pharma", "biotech", "genome", "dental", "vision"],
    "ecommerce": ["shop", "store", "buy", "cart", "commerce", "retail", "product", "market", "deal", "price", "checkout", "inventory", "wholesale", "merchant", "vendor", "ship", "delivery", "fulfill"],
    "realestate": ["realestate", "property", "home", "house", "rent", "apartment", "mortgage", "estate", "realtor", "agent", "listing", "condo", "lease", "broker", "appraisal", "title", "closing"],
    "cybersecurity": ["cyber", "security", "secure", "protect", "shield", "defense", "firewall", "encrypt", "vpn", "audit", "compliance", "threat", "malware", "ransomware", "identity", "privacy", "auth"],
    "education": ["edu", "learn", "course", "academy", "school", "training", "tutor", "knowledge", "skill", "lesson", "class", "curriculum", "certify", "diploma", "study", "teach", "scholar"],
    "productivity": ["productivity", "task", "manage", "organize", "workflow", "efficiency", "focus", "time", "calendar", "schedule", "track", "habit", "goal", "planner", "notion", "board"],
    "legal": ["law", "legal", "attorney", "lawyer", "justice", "court", "firm", "litigation", "contract", "patent", "trademark", "estate", "advocate", "counsel", "notary", "mediation"],
    "programming": ["code", "dev", "programming", "developer", "api", "backend", "frontend", "stack", "script", "debug", "deploy", "pipeline", "docker", "kubernetes", "serverless", "database", "sdk"],
    "marketing": ["marketing", "brand", "campaign", "seo", "social", "content", "email", "landing", "funnel", "convert", "traffic", "analytics", "crm", "lead", "growth", "referral", "influencer"],
}

PREFIXES = ["get", "go", "try", "use", "my", "the", "app", "neo", "on", "up", "hi", "zen", "syn", "ai", "cyber", "digi", "eco", "fin", "health", "med", "smart", "tech", "web", "quick", "brand", "cloud"]
SUFFIXES = ["hub", "lab", "labs", "app", "io", "ly", "ify", "ai", "tech", "soft", "ware", "gen", "ix", "os", "nest", "mind", "flow", "grid", "peak", "pulse", "volt", "edge", "link", "nova", "zen", "sync", "ops"]


def _get_keywords(niche: str) -> list[str]:
    if niche == "general":
        result = []
        for kw_list in NICHE_KEYWORDS.values():
            result.extend(kw_list)
        return result
    return NICHE_KEYWORDS.get(niche, [])


def _is_valid_candidate(name: str) -> bool:
    if len(name) < 3 or len(name) > 20:
        return False
    return name.isalnum()


class KeywordGenerator(BaseDomainGenerator):
    def __init__(self) -> None:
        self._prefixes = PREFIXES
        self._suffixes = SUFFIXES

    async def generate(self, niche: str = "general", count: int = 100) -> list[str]:
        keywords = _get_keywords(niche)
        if not keywords:
            logger.warning("No keywords found for niche: %s", niche)
            return []

        candidates: set[str] = set()

        # a. Direct keywords
        for kw in keywords:
            if _is_valid_candidate(kw):
                candidates.add(kw.lower())

        # b. Compound words
        for kw1 in keywords:
            for kw2 in keywords:
                compound = kw1 + kw2
                if _is_valid_candidate(compound):
                    candidates.add(compound.lower())

        # c. Prefix + keyword
        for prefix in self._prefixes:
            for kw in keywords:
                pk = prefix + kw
                if _is_valid_candidate(pk):
                    candidates.add(pk.lower())

        # d. Keyword + suffix
        for kw in keywords:
            for suffix in self._suffixes:
                ks = kw + suffix
                if _is_valid_candidate(ks):
                    candidates.add(ks.lower())

        # e. Prefix + suffix (brandable)
        for prefix in self._prefixes:
            for suffix in self._suffixes:
                ps = prefix + suffix
                if _is_valid_candidate(ps):
                    candidates.add(ps.lower())

        # f. Truncated compounds (first 3-4 chars)
        for kw1 in keywords:
            for kw2 in keywords:
                if kw1 != kw2:
                    trunc = kw1[:4] + kw2[:3]
                    if _is_valid_candidate(trunc):
                        candidates.add(trunc.lower())

        result = sorted(candidates)
        random.shuffle(result)
        result = result[:count]

        logger.info("Generated %d domain candidates for niche='%s'", len(result), niche)
        return result
