# Domain Flipper — Account Setup Checklist

## 1. Gmail SMTP (Outbound Email)

The bot sends outreach emails to domain buyers/sellers via Gmail's SMTP server.

**You need:**
- A Gmail address (e.g. `yourdomainbot@gmail.com`)
- A Gmail **App Password** (not your regular Google password)

**How to generate an App Password:**
1. Go to https://myaccount.google.com/security
2. Turn on **2-Step Verification** (required for App Passwords)
3. Go to https://myaccount.google.com/apppasswords
4. Select "Mail" as the app and "Other (custom name)" — enter "Domain Flipper"
5. Click **Generate** — copy the 16-character password (looks like `abcd efgh ijkl mnop`)

**Set in `.env`:**
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=yourdomainbot@gmail.com
SMTP_PASS=abcd efgh ijkl mnop
EMAIL_FROM=yourdomainbot@gmail.com
EMAIL_TO=your-email@gmail.com
```

The password includes spaces — paste it exactly as shown.

---

## 2. LinkedIn Account (Manual Research)

LinkedIn is used **manually** — no automation or API integration.

**What you'll use it for:**
- Looking up company pages for leads in `src/outreach/buyer_enricher.py` (niches: AI, SaaS, Finance, Health, etc.)
- Finding decision-makers (Marketing Directors, Head of Growth, etc.)
- Crafting DM templates based on profiles

**No setup required** — just have a LinkedIn account ready for manual research.

---

## 3. `.env` Configuration

Edit `.env` in the project root. Below is the full config reference:

```ini
# --- Core ---
DATABASE_PATH=data/domains.db
LOG_LEVEL=INFO
OFFLINE_MODE=false              # true = skip external API calls

# --- Budget ---
MAX_BID=100
PREFERRED_MIN=10
PREFERRED_MAX=50
EXCEPTIONAL_MAX=300

# --- Gmail SMTP (see step 1) ---
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=yourdomainbot@gmail.com
SMTP_PASS=abcd efgh ijkl mnop
EMAIL_FROM=yourdomainbot@gmail.com
EMAIL_TO=your-email@gmail.com

# --- Notifications (optional) ---
TELEGRAM_BOT_TOKEN=             # see step 5
TELEGRAM_CHAT_ID=
DISCORD_WEBHOOK_URL=            # see step 5

# --- Data Enrichment APIs (optional) ---
CATCHDOMS_API_KEY=
CRAWLY_API_KEY=
AHREFS_API_KEY=
MOZ_API_KEY=
```

Save the file after editing. The app reads it automatically on startup.

---

## 4. First Run

Make sure Python 3.11+ is installed, then:

```bash
# Install dependencies
pip install -r requirements.txt

# Install playwright browsers
playwright install

# Run the broker
python -m src.main
```

Or if installed via pip:
```bash
pip install -e .
domain-flipper
```

Start with `OFFLINE_MODE=true` to test without hitting real APIs.

---

## 5. Optional Improvements (once running)

| Feature | What to set in `.env` | Where to get it |
|---|---|---|
| **Telegram alerts** | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Create a bot via [@BotFather](https://t.me/BotFather) |
| **Discord alerts** | `DISCORD_WEBHOOK_URL` | Channel Settings → Integrations → Webhook |
| **Crawly API** | `CRAWLY_API_KEY` | [crawly.ai](https://crawly.ai) — enriches domain metadata |
| **CatchDoms API** | `CATCHDOMS_API_KEY` | [catchdoms.com](https://catchdoms.com) — expired domain data |
| **Ahrefs API** | `AHREFS_API_KEY` | [ahrefs.com](https://ahrefs.com) — backlink/SEO data |
| **Moz API** | `MOZ_API_KEY` | [moz.com](https://moz.com) — domain authority data |
