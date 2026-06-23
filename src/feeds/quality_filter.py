from __future__ import annotations

import re

# Only these TLDs are worth flipping
PREMIUM_TLDS: set[str] = {
    "com", "io", "ai", "co", "net", "org", "dev", "app",
}

# Pharma/spam drug names to exclude
PHARMA_KEYWORDS: set[str] = {
    "flomax", "tamsulosin", "zoloft", "sertraline", "metformin",
    "lyrica", "pregabalin", "ventolin", "albuterol", "omeprazole",
    "prilosec", "lipitor", "atorvastatin", "amlodipine", "norvasc",
    "lisinopril", "prinivil", "zestril", "levothyroxine", "synthroid",
    "gabapentin", "neurontin", "xanax", "alprazolam", "adderall",
    "amphetamine", "oxycodone", "percocet", "hydrocodone", "vicodin",
    "tramadol", "viagra", "sildenafil", "cialis", "tadalafil",
    "prozac", "fluoxetine", "paxil", "paroxetine", "lexapro",
    "escitalopram", "celexa", "citalopram", "wellbutrin", "bupropion",
    "ambien", "zolpidem", "valium", "diazepam", "ativan", "lorazepam",
    "klonopin", "clonazepam", "prednisone", "deltasone", "methadone",
    "fentanyl", "morphine", "codeine", "cyclobenzaprine", "flexeril",
    "hydroxyzine", "meclizine", "ondansetron", "zofran", "promethazine",
    "phenergan", "ranitidine", "zantac", "famotidine", "pepcid",
    "pantoprazole", "protonix", "esomeprazole", "nexium", "doxycycline",
    "amoxicillin", "azithromycin", "zithromax", "ciprofloxacin", "cipro",
    "prednisolone", "milrinone", "carvedilol", "coreg", "metoprolol",
    "toprol", "propranolol", "inderal", "clopidogrel", "plavix",
    "warfarin", "coumadin", "digoxin", "lanoxin", "furosemide",
    "lasix", "spironolactone", "aldactone", "hydrochlorothiazide",
    "hctz", "losartan", "cozaar", "valsartan", "diovan", "irbesartan",
    "avapro", "telmisartan", "micardis", "olmesartan", "benicar",
}

# Known URL shorteners to exclude
URL_SHORTENERS: set[str] = {
    "ht.ly", "bit.ly", "tinyurl.com", "ow.ly", "is.gd", "buff.ly",
    "shorturl.at", "t.co", "goo.gl", "tiny.cc", "tr.im", "v.gd",
    "clicky.me", "rb.gy", "s.id", "shorte.st", "adf.ly", "bc.vc",
}

# SEO/spam keywords
SPAM_KEYWORDS: set[str] = {
    "pharmacy", "meds", "drugs", "cbd", "thc", "vape", "casino",
    "gambling", "poker", "betting", "loan", "credit", "insurance",
    "porn", "sex", "xxx", "nude", "naked", "dating", "hookup",
    "darkweb", "darkweb", "hacker", "crack", "exploit", "malware",
    "ransomware", "trojan", "botnet", "ddos", "spam", "scam",
    "fake", "counterfeit", "forged", "stolen", "hijacked",
    "antabuse", "finasteride", "viagra", "cialis", "xanax",
    "oxycontin", "vicodin", "adderall", "valium", "ambien",
}

# Known domain registries / subdomain hosts — exclude
KNOWN_SUBDOMAINS: set[str] = {
    "domainpunch", "namecheap", "godaddy", "squarespace", "wix",
    "weebly", "wordpress", "blogspot", "shopify", "webflow",
}


def is_premium_domain(domain_name: str) -> bool:
    """
    Quality filter: returns True only if the domain is worth analyzing.
    """
    name = domain_name.lower().strip()

    # Basic structure check
    if "." not in name:
        return False

    parts = name.split(".")
    tld = parts[-1]

    # 1. Subdomain check — max 2 parts (example.com, not sub.example.com)
    if len(parts) > 2:
        if parts[-2] not in ("co", "com", "io", "net", "org") and len(parts) > 2:
            return False

    # 2. Known subdomain hosts
    if len(parts) >= 2 and parts[-2] in KNOWN_SUBDOMAINS:
        return False

    # 3. URL shorteners
    if name in URL_SHORTENERS:
        return False

    # 4. TLD filter — only premium TLDs
    if tld not in PREMIUM_TLDS:
        return False

    domain = parts[-2] if len(parts) >= 2 else name.split(".")[0]
    # Handle co.uk, co.in etc
    if domain in ("co", "com", "org", "net", "gov", "ac"):
        if len(parts) >= 3:
            domain = parts[-3]

    # 5. Length filter
    if len(domain) < 3:
        return False
    if len(domain) > 18:
        return False

    # 6. Hyphen count — max 1
    if domain.count("-") > 1:
        return False

    # 7. Numbers — allow 0-1 numbers
    digit_count = sum(1 for c in domain if c.isdigit())
    if digit_count > 1:
        return False
    if digit_count == 1 and domain[-1].isdigit() and len(domain) > 3:
        # Likely a junk domain like "domain123.com"
        pass

    # 8. Pharma keywords
    for keyword in PHARMA_KEYWORDS:
        if keyword in domain:
            return False

    # 9. Spam keywords
    for keyword in SPAM_KEYWORDS:
        if keyword in domain:
            return False

    return True


def filter_domains(domains: list[dict]) -> list[dict]:
    """Filter a list of domain dicts to only premium domains."""
    before = len(domains)
    filtered = [d for d in domains if is_premium_domain(d.get("domain_name", ""))]
    rejected = before - len(filtered)
    if rejected:
        from src.utils import setup_logger
        logger = setup_logger("QualityFilter")
        logger.info(
            "Filtered out %d/%d junk domains (%.0f%% kept)",
            rejected, before, len(filtered) / before * 100 if before else 0,
        )
    return filtered
