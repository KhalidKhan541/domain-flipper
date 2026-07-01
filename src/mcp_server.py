"""
MCP Server for Domain Flipper — exposes domain brokering tools via the Model Context Protocol.

Run: python -m src.mcp_server
Then connect any MCP-compatible AI client (Claude, Cursor, etc.) to this process.

Protocol: JSON-RPC 2.0 over stdin/stdout
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from src.config import settings
from src.database import Database
from src.coordinators.broker import BrokerCoordinator, NICHES
from src.analyzers.broker import BrokerAnalyzer
from src.constants import LEADS_BY_NICHE
from src.analyzers.commercial import CommercialAnalyzer
from src.analyzers.history import HistoryAnalyzer
from src.analyzers.seo import SEOAnalyzer
from src.analyzers.scoring import ScoringEngine
from src.checkers.rdap_checker import RDAPChecker
from src.generators.keyword_generator import KeywordGenerator
from src.generators.thesaurus_generator import ThesaurusGenerator
from src.outreach.template_generator import TemplateGenerator
from src.outreach.commission_agreement import CommissionAgreementGenerator
from src.outreach.tracker import OutreachTracker

logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
logger = logging.getLogger("mcp-server")


TOOLS = [
    {
        "name": "discover_opportunities",
        "description": "Run the domain discovery pipeline to find domain opportunities in a niche. Discovers expired/auction domains, checks availability, analyzes SEO/history/commercial potential, and scores them for brokering.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "niche": {
                    "type": "string",
                    "enum": NICHES,
                    "default": "saas",
                    "description": "Market niche to target"
                },
                "max_domains": {
                    "type": "integer",
                    "default": 50,
                    "description": "Maximum number of domains to return"
                },
                "min_score": {
                    "type": "number",
                    "default": 0,
                    "description": "Minimum broker score filter (0-100)"
                }
            }
        }
    },
    {
        "name": "analyze_domain",
        "description": "Run full broker analysis on a specific domain name. Returns SEO metrics, history/trust score, commercial potential, buyer leads, estimated value, and broker grade.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain_name": {"type": "string", "description": "Domain to analyze (e.g. example.com)"},
                "niche": {"type": "string", "enum": NICHES, "default": "general", "description": "Niche for buyer lead generation"}
            },
            "required": ["domain_name"]
        }
    },
    {
        "name": "get_top_opportunities",
        "description": "Get the top-scored domain opportunities from the database.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 20, "description": "Number of top domains to return"},
                "min_score": {"type": "number", "default": 0, "description": "Minimum final score filter"}
            }
        }
    },
    {
        "name": "find_buyers",
        "description": "Find potential buyers for a domain based on niche and domain keywords. Returns company leads with buyer profiles.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain_name": {"type": "string", "description": "Domain to find buyers for"},
                "niche": {"type": "string", "enum": list(LEADS_BY_NICHE.keys()) + ["general"], "default": "general", "description": "Market niche"}
            },
            "required": ["domain_name"]
        }
    },
    {
        "name": "generate_outreach_template",
        "description": "Generate a cold outreach email template for buyer or seller.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {"type": "string", "description": "The domain being brokered"},
                "recipient_name": {"type": "string", "description": "Name of the person to contact"},
                "recipient_company": {"type": "string", "description": "Company of the recipient"},
                "estimated_value": {"type": "integer", "default": 1000, "description": "Estimated domain value in USD"},
                "niche": {"type": "string", "default": "general", "description": "Market niche"},
                "type": {"type": "string", "enum": ["buyer", "seller"], "default": "buyer", "description": "Outreach type"}
            },
            "required": ["domain", "recipient_name", "recipient_company"]
        }
    },
    {
        "name": "generate_commission_agreement",
        "description": "Generate a domain broker commission agreement HTML document.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {"type": "string", "description": "The domain being brokered"},
                "buyer_name": {"type": "string", "description": "Buyer's full name"},
                "buyer_company": {"type": "string", "description": "Buyer's company"},
                "seller_name": {"type": "string", "description": "Seller's full name"},
                "seller_company": {"type": "string", "description": "Seller's company"},
                "estimated_value": {"type": "integer", "default": 1000, "description": "Estimated domain value in USD"},
                "commission_rate": {"type": "number", "default": 0.15, "description": "Commission rate (0.0-1.0)"}
            },
            "required": ["domain", "buyer_name", "buyer_company", "seller_name", "seller_company"]
        }
    },
    {
        "name": "check_availability",
        "description": "Check if a domain is available via RDAP + DNS fallback.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain_name": {"type": "string", "description": "Domain to check (e.g. example.com)"}
            },
            "required": ["domain_name"]
        }
    },
    {
        "name": "generate_domain_names",
        "description": "Generate domain name candidates from niche keywords. Uses combinatorial patterns (prefix+keyword, keyword+suffix, compounds).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "niche": {"type": "string", "enum": NICHES, "default": "saas", "description": "Niche for domain generation"},
                "count": {"type": "integer", "default": 30, "description": "Number of domain ideas to generate"},
                "use_thesaurus": {"type": "boolean", "default": True, "description": "Expand keywords via thesaurus"}
            }
        }
    },
    {
        "name": "get_pipeline_status",
        "description": "Get the current broker pipeline status: recent domain count, top opportunities, outreach stats.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_dashboard_summary",
        "description": "Get outreach dashboard summary: lead counts by status and type.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status_filter": {
                    "type": "string",
                    "enum": ["all", "pending", "sent", "replied", "negotiating", "closed_won", "closed_lost"],
                    "default": "all"
                }
            }
        }
    },
]


class DomainFlipperMCP:
    def __init__(self):
        self.db: Database | None = None
        self.tracker: OutreachTracker | None = None
        self.coordinator: BrokerCoordinator | None = None
        self.broker_analyzer = BrokerAnalyzer()
        self.commercial_analyzer = CommercialAnalyzer()
        self.history_analyzer = HistoryAnalyzer()
        self.seo_analyzer = SEOAnalyzer()
        self.scoring_engine = ScoringEngine()
        self.checker = RDAPChecker()
        self.keyword_gen = KeywordGenerator()
        self.thesaurus_gen = ThesaurusGenerator()
        self.template_gen = TemplateGenerator()
        self.commission_gen = CommissionAgreementGenerator()

    async def initialize(self):
        self.db = Database(settings.database_path)
        await self.db.init_db()
        self.tracker = OutreachTracker()
        await self.tracker.init_db()
        self.coordinator = BrokerCoordinator(db=self.db)

    async def shutdown(self):
        if self.db:
            await self.db.close()
        if self.tracker:
            await self.tracker.close()

    async def handle_call(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        handler = getattr(self, f"tool_{tool_name}", None)
        if not handler:
            raise ValueError(f"Unknown tool: {tool_name}")
        return await handler(**arguments)

    async def tool_discover_opportunities(self, niche: str = "saas", max_domains: int = 50, min_score: float = 0) -> dict:
        domains = await self.coordinator.discover(max_domains=max_domains)
        analyzed = await self.coordinator.analyze_all(domains)
        filtered = [d for d in analyzed if d.get("broker_score", 0) >= min_score]
        return {
            "total_found": len(filtered),
            "niche": niche,
            "opportunities": [
                {
                    "domain": d["domain_name"],
                    "broker_score": d.get("broker_score", 0),
                    "broker_grade": d.get("broker_grade", "Cold"),
                    "final_score": d.get("final_score", 0),
                    "estimated_value": d.get("estimated_value", 0),
                    "commission": d.get("commission", {}).get("amount", 0),
                    "buyer_leads": d.get("buyer_leads", {}).get("total_leads", 0),
                    "seo_score": d.get("seo_score", 0),
                    "dr": d.get("dr", 0),
                    "domain_age": d.get("domain_age", 0),
                    "category": d.get("category", "general"),
                    "price": d.get("price", 0),
                }
                for d in filtered[:max_domains]
            ],
        }

    async def tool_analyze_domain(self, domain_name: str, niche: str = "general") -> dict:
        history, seo, commercial, broker = await asyncio.gather(
            self.history_analyzer.analyze(domain_name),
            self.seo_analyzer.analyze(domain_name),
            self.commercial_analyzer.analyze(domain_name),
            self.broker_analyzer.analyze(domain_name, niche),
            return_exceptions=True,
        )

        def safe(d, field, default):
            return d.get(field, default) if isinstance(d, dict) else default

        result = {
            "domain_name": domain_name,
            "seo": {
                "dr": safe(seo, "dr", 0),
                "referring_domains": safe(seo, "referring_domains", 0),
                "domain_age": safe(seo, "domain_age", 0),
                "seo_score": safe(seo, "seo_score", 0),
            },
            "history": {
                "cleanliness_score": safe(history, "cleanliness_score", 50),
                "trust_score": safe(history, "trust_score", 50),
                "wayback_snapshots": safe(history, "wayback_snapshots", 0),
                "has_threats": safe(history, "has_threats", False),
            },
            "commercial": {
                "category": safe(commercial, "category", "general"),
                "commercial_score": safe(commercial, "commercial_score", 50),
                "brandability": safe(commercial, "brandability", 50),
                "keyword_value": safe(commercial, "keyword_value", 0),
                "memorability": safe(commercial, "memorability", 50),
            },
            "broker": {
                "estimated_value": safe(broker, "estimated_value", 0),
                "commission": safe(broker, "commission", {"amount": 0, "rate": 0.15}),
                "buyer_leads": safe(broker, "buyer_leads", {"total_leads": 0, "leads": []}),
                "marketplace_listings": safe(broker, "marketplace", {}),
                "broker_score": safe(broker, "broker_score", 0),
                "broker_grade": safe(broker, "broker_grade", "Cold"),
            },
        }

        score = self.scoring_engine.calculate(
            domain=domain_name,
            price=0,
            seo_score=result["seo"]["seo_score"],
            commercial_score=result["commercial"]["commercial_score"],
            trust_score=result["history"]["trust_score"],
            cleanliness_score=result["history"]["cleanliness_score"],
        )
        result["final_score"] = score["final_score"]
        result["opportunity_grade"] = score["opportunity_grade"]

        return result

    async def tool_get_top_opportunities(self, limit: int = 20, min_score: float = 0) -> dict:
        if not self.db:
            return {"error": "Database not initialized"}
        domains = await self.db.get_top_domains(limit=limit)
        filtered = [d for d in domains if d.get("final_score", 0) >= min_score]
        return {
            "total": len(filtered),
            "opportunities": [
                {
                    "domain": d["domain_name"],
                    "final_score": d.get("final_score", 0),
                    "opportunity_grade": d.get("opportunity_grade", "N/A"),
                    "seo_score": d.get("seo_score", 0),
                    "dr": d.get("dr", 0),
                    "domain_age": d.get("domain_age", 0),
                    "category": d.get("category", "general"),
                    "price": d.get("price", 0),
                    "source": d.get("source", ""),
                }
                for d in filtered
            ],
        }

    async def tool_find_buyers(self, domain_name: str, niche: str = "general") -> dict:
        analyzer = BrokerAnalyzer()
        result = await analyzer.analyze(domain_name, niche)
        leads = result.get("buyer_leads", {})
        return {
            "domain": domain_name,
            "niche": niche,
            "total_leads": leads.get("total_leads", 0),
            "leads": leads.get("leads", []),
        }

    async def tool_generate_outreach_template(self, domain: str, recipient_name: str, recipient_company: str, estimated_value: int = 1000, niche: str = "general", type: str = "buyer") -> dict:
        if type == "buyer":
            template = self.template_gen.buyer_outreach(domain, recipient_company, recipient_name, estimated_value, niche)
        else:
            template = self.template_gen.seller_outreach(domain, recipient_name, estimated_value)
        return {
            "type": type,
            "subject": template["subject"],
            "body": template["body"],
            "character_count": len(template["body"]),
        }

    async def tool_generate_commission_agreement(self, domain: str, buyer_name: str, buyer_company: str, seller_name: str, seller_company: str, estimated_value: int = 1000, commission_rate: float = 0.15) -> dict:
        commission_amount = int(estimated_value * commission_rate)
        html = await self.commission_gen.generate(
            domain=domain,
            buyer_name=buyer_name,
            buyer_company=buyer_company,
            seller_name=seller_name,
            seller_company=seller_company,
            commission_amount=commission_amount,
            commission_rate=commission_rate,
            estimated_value=estimated_value,
        )
        path = await self.commission_gen.save(html, domain)
        return {
            "domain": domain,
            "commission_amount": commission_amount,
            "commission_rate": commission_rate,
            "estimated_value": estimated_value,
            "html": html,
            "saved_to": str(path),
        }

    async def tool_check_availability(self, domain_name: str) -> dict:
        results = await self.checker.check_batch([domain_name])
        result = results[0] if results else {"available": False, "method": "unknown"}
        return {
            "domain": domain_name,
            "available": result.get("available", False),
            "method": result.get("method", "unknown"),
            "registrar": result.get("registrar", ""),
        }

    async def tool_generate_domain_names(self, niche: str = "saas", count: int = 30, use_thesaurus: bool = True) -> dict:
        candidates: set[str] = set()
        keywords = await self.keyword_gen.generate(niche, count=count)
        candidates.update(keywords)
        if use_thesaurus:
            thesaurus = await self.thesaurus_gen.generate(niche, count=count)
            candidates.update(thesaurus)
        return {
            "niche": niche,
            "total_generated": len(candidates),
            "examples": sorted(list(candidates))[:count],
        }

    async def tool_get_pipeline_status(self) -> dict:
        if not self.db:
            return {"error": "Database not initialized"}
        today = await self.db.get_today_domains()
        top = await self.db.get_top_domains(limit=5)
        return {
            "domains_today": len(today),
            "top_opportunities": [{"domain": d["domain_name"], "score": d.get("final_score", 0), "grade": d.get("opportunity_grade", "")} for d in top],
            "average_score": round(sum(d.get("final_score", 0) for d in today) / len(today), 1) if today else 0,
        }

    async def tool_get_dashboard_summary(self, status_filter: str = "all") -> dict:
        if not self.tracker:
            return {"error": "Tracker not initialized"}
        leads = await self.tracker.get_all()
        if status_filter != "all":
            leads = [l for l in leads if l["status"] == status_filter]
        from collections import Counter
        by_status = Counter(l["status"] for l in leads)
        by_type = Counter(l["lead_type"] for l in leads)
        return {
            "total_leads": len(leads),
            "by_status": dict(by_status),
            "by_type": dict(by_type),
            "leads": [
                {
                    "id": l["id"],
                    "domain": l["domain_name"],
                    "company": l["company"],
                    "type": l["lead_type"],
                    "contact": l["contact_name"],
                    "email": l["contact_email"],
                    "status": l["status"],
                }
                for l in leads[:50]
            ],
        }


async def main():
    mcp = DomainFlipperMCP()
    await mcp.initialize()

    request_id = 0
    buffer = ""

    while True:
        try:
            line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
            if not line:
                break
            buffer += line
            try:
                msg = json.loads(buffer)
                buffer = ""
            except json.JSONDecodeError:
                continue

            method = msg.get("method", "")
            msg_id = msg.get("id", request_id)
            request_id += 1

            if method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {},
                        },
                        "serverInfo": {
                            "name": "domain-flipper-mcp",
                            "version": "0.1.0",
                        },
                    },
                }
            elif method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"tools": TOOLS},
                }
            elif method == "tools/call":
                tool_name = msg.get("params", {}).get("name", "")
                arguments = msg.get("params", {}).get("arguments", {})
                try:
                    result = await mcp.handle_call(tool_name, arguments)
                    response = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(result, indent=2, default=str),
                                }
                            ],
                        },
                    }
                except Exception as e:
                    response = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {"code": -32603, "message": str(e)},
                    }
            elif method == "notifications/initialized":
                continue
            elif method == "shutdown":
                response = {"jsonrpc": "2.0", "id": msg_id, "result": None}
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
                break
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                }

            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()

        except EOFError:
            break
        except Exception as e:
            logger.error("Fatal error: %s", e, exc_info=True)
            break

    await mcp.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
