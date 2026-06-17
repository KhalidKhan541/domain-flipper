# Domain Flipper Enhancement Plan: n8n + MCP

## Changes Made

| Change | Files | Impact |
|--------|-------|--------|
| **MCP Server** | `src/mcp_server.py` (new) | 10 tools + full JSON-RPC protocol — any AI agent can now query the pipeline |
| **Removed all mock data** | feeds/, collectors/ (deleted), outreach/ | No more silent fake data; empty results are honest |
| **Deduplicated LEADS_BY_NICHE** | `src/constants.py` (new), broker.py, buyer_enricher.py, coordinator | Single source of truth eliminates 150 lines of duplication |
| **Fixed offline mode lock** | `src/main.py` | Was permanently stuck in offline mode after first outbound run |
| **Removed deprecated collectors** | `src/collectors/` (deleted) | 2,000+ lines of dead code removed |

## MCP Server Tools (src/mcp_server.py)

| Tool | What it does |
|---|---|
| `discover_opportunities` | Full pipeline: generate → collect → analyze → score → return top domains |
| `analyze_domain` | SEO + history + commercial + broker analysis on any domain |
| `get_top_opportunities` | Query best domains from the database |
| `find_buyers` | Find potential buyer companies for a domain by niche |
| `generate_outreach_template` | Cold email template for buyer or seller |
| `generate_commission_agreement` | HTML commission document for the deal |
| `check_availability` | RDAP + DNS availability check |
| `generate_domain_names` | Generate domain candidates from keywords |
| `get_pipeline_status` | Summary of today's pipeline |
| `get_dashboard_summary` | Outreach lead counts by status |

## How to use the MCP Server

```bash
# Chat-based AI client:
python -m src.mcp_server
# Then connect any MCP client (Claude Code, Cursor, etc.)

# Or run directly:
python -m src.main                    # Full pipeline
python -m src.dashboard               # Outreach dashboard
```

## n8n Enhancement Potential (when/if you use n8n)

Without paid APIs, n8n's free self-hosted version can still add:

| n8n Node | Replaces | Benefit |
|----------|----------|---------|
| Telegram / Discord / Email | Custom notifiers | Production error handling |
| Google Sheets | Custom CSV reports | Live shared spreadsheet |
| Airtable | SQLite database | Visual domain tracking |
| Slack | — | Team notifications (free) |
| Schedule / Cron | — | Visual workflow scheduling |
| RSS Feed Read | — | Monitor domain availability RSS |

## Architecture

```
┌─────────────────────────────────────────────────┐
│              Domain Flipper Pipeline             │
├─────────────────────────────────────────────────┤
│  Generate → Collect (real feeds only) →          │
│  Analyze (SEO/history/commercial/broker) →       │
│  Score → Report → Notify → Outreach              │
│                                                  │
│  ┌────────────────┐                              │
│  │  MCP Server    │ ←── Any AI agent can call    │
│  │  (10 tools)    │     these tools via protocol  │
│  └────────────────┘                              │
└─────────────────────────────────────────────────┘
```

## Run

```bash
# Main pipeline (requires live internet + working scrapers)
python -m src.main

# MCP server (connect any AI agent)
python -m src.mcp_server

# Dashboard
python -m src.dashboard
```
