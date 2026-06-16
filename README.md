# Domain Flipper - Autonomous Expired Domain Discovery Agent

Automatically discovers undervalued expired and auction domains by scraping major marketplaces, analyzing SEO metrics, history, and commercial potential, then ranks them by a weighted scoring system.

## Features

- **Multi-source collection**: GoDaddy Auctions, DropCatch, ExpiredDomains.net, NameJet, Dynadot
- **Smart filtering**: DR >= 20, RD >= 50, clean history, 2+ years age
- **Deep analysis**: Wayback Machine history, backlink estimation, category matching, brandability scoring
- **Weighted scoring**: 40% SEO + 30% Commercial + 20% Trust + 10% Price Efficiency
- **Daily automation**: GitHub Actions runs at 08:00 UTC
- **Multi-channel notifications**: Telegram, Discord, Email
- **Reports**: Markdown, CSV, JSON formats
- **Learning loop**: Tracks purchases and sales to refine scoring weights

## Quick Start

### 1. Clone and install

```bash
git clone <repo>
cd domain-flipper
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your budget and API keys
```

### 3. Run

```bash
python -m src.main
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| MAX_BID | 100 | Maximum bid per domain |
| PREFERRED_MIN | 10 | Minimum domain price range |
| PREFERRED_MAX | 50 | Maximum preferred price |
| EXCEPTIONAL_MAX | 300 | Max for flagged exceptional domains |
| TELEGRAM_BOT_TOKEN | - | Telegram bot token for notifications |
| TELEGRAM_CHAT_ID | - | Telegram chat/group ID |
| DISCORD_WEBHOOK_URL | - | Discord webhook URL |
| SMTP_* | - | Email notification settings |

## Scoring System

```
Final Score = 0.40 × SEO Score + 0.30 × Commercial Score + 0.20 × Trust Score + 0.10 × Price Efficiency
```

| Grade | Score | Action |
|-------|-------|--------|
| A+ | 85-100 | Buy immediately |
| A | 70-84 | Strong consider |
| B | 55-69 | Decent opportunity |
| C | 40-54 | Marginal |
| Avoid | < 40 | Skip |

## Project Structure

```
domain-flipper/
├── src/
│   ├── main.py              # Orchestrator
│   ├── config.py            # Settings (.env)
│   ├── database.py          # SQLite storage
│   ├── collectors/          # Marketplace scrapers
│   ├── analyzers/           # SEO, history, commercial, scoring
│   ├── notifiers/           # Telegram, Discord, Email
│   ├── reporting/           # Markdown, CSV, JSON
│   └── utils/               # Logger, retry decorators
├── tests/                   # Pytest test suite
├── data/                    # Database + reports
├── .github/workflows/       # CI/CD automation
└── .env.example
```

## GitHub Actions Automation

1. Push to GitHub
2. Add secrets to your repo (Settings > Secrets and variables > Actions)
3. The workflow runs daily at 08:00 UTC
4. Reports are saved as artifacts

## License

MIT
