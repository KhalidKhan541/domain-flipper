"""Shared data constants for domain flipper — single source of truth."""

LEADS_BY_NICHE: dict[str, list[str]] = {
    "ai": [
        "OpenAI", "Anthropic", "Cohere", "Hugging Face", "Stability AI",
        "Jasper AI", "Copy.ai", "Writer.com", "Runway ML", "Midjourney",
        "Scale AI", "DataRobot", "H2O.ai", "C3 AI", "Pathmind",
    ],
    "saas": [
        "Salesforce", "HubSpot", "Zendesk", "Slack", "Atlassian",
        "Notion", "Airtable", "Asana", "Monday.com", "ClickUp",
        "Freshworks", "Intercom", "DocuSign", "Box", "Dropbox",
    ],
    "finance": [
        "Stripe", "Square", "Plaid", "Robinhood", "Coinbase",
        "PayPal", "Revolut", "Wise", "Klarna", "Affirm",
        "Chime", "Betterment", "Wealthfront", "SoFi", "Nubank",
    ],
    "health": [
        "Teladoc", "Ro", "Hims", "Noom", "Calm",
        "Headspace", "MyFitnessPal", "Fitbit", "Whoop", "Oura",
        "One Medical", "Carbon Health", "Zymergen", "Illumina", "23andMe",
    ],
    "ecommerce": [
        "Shopify", "Wix", "Squarespace", "WooCommerce",
        "Magento", "PrestaShop", "OpenCart", "Ecwid",
        "Etsy", "Amazon", "eBay", "Walmart",
    ],
    "education": [
        "Coursera", "Udemy", "edX", "Khan Academy", "Duolingo",
        "Chegg", "Quizlet", "Byju's", "MasterClass", "Skillshare",
        "Pluralsight", "DataCamp", "Brilliant", "Codecademy",
    ],
    "cybersecurity": [
        "CrowdStrike", "Palo Alto Networks", "Fortinet", "Zscaler", "Cloudflare",
        "Okta", "SentinelOne", "Darktrace", "Snyk", "Rapid7",
        "Tenable", "Check Point", "McAfee", "Trend Micro",
    ],
    "realestate": [
        "Zillow", "Redfin", "Compass", "Opendoor", "Realtor.com",
        "Airbnb", "Vrbo", "Booking.com", "CoStar", "Zumper",
        "Trulia", "Homes.com", "LoopNet",
    ],
    "productivity": [
        "Notion", "Todoist", "Evernote", "Bear", "Roam Research",
        "Obsidian", "Miro", "Trello",
        "Forest", "Focusmate", "RescueTime", "Clockify", "Toggl",
    ],
    "legal": [
        "LegalZoom", "Rocket Lawyer", "Avvo", "Clio", "MyCase",
        "Ironclad", "Evisort",
        "LexisNexis", "Thomson Reuters",
    ],
}

NICHES = list(LEADS_BY_NICHE.keys())
