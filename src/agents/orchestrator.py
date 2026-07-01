"""Main orchestrator — runs 7 subagents in parallel for buyer-first domain brokering."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from src.agents import (
    expiring_scout, marketplace_playwright, forsale_finder,
    buyer_finder_reddit, buyer_finder_hn,
    seller_contact, email_sellers, email_buyers,
)
from src.notifiers import DiscordNotifier, EmailNotifier
from src.utils import setup_logger


async def run_pipeline(dry_run: bool = False) -> dict:
    """Run the full 7-agent pipeline with buyer-first approach."""
    logger = setup_logger("PipelineOrchestrator")
    start = datetime.now(timezone.utc)

    logger.info("=" * 60)
    logger.info("STARTING 7-AGENT BUYER-FIRST DOMAIN BROKER PIPELINE")
    logger.info("=" * 60)

    # ============================================================
    # STEP 1: Find buyers FIRST (what domains do they want?)
    # ============================================================
    logger.info("Step 1/5: Finding buyers and what domains they want...")

    reddit_task = buyer_finder_reddit.run()
    hn_task = buyer_finder_hn.run()

    reddit, hn = await asyncio.gather(
        reddit_task, hn_task,
        return_exceptions=True,
    )

    reddit_buyers = reddit if isinstance(reddit, list) else []
    hn_data = hn if isinstance(hn, dict) else {}
    hn_buyers = hn_data.get("buyers", [])

    all_buyers = reddit_buyers + hn_buyers

    # Extract all buyer needs
    all_needs: dict[str, int] = {}
    for buyer in all_buyers:
        for need in buyer.get("buyer_needs", []):
            all_needs[need] = all_needs.get(need, 0) + 1

    logger.info("Found %d buyers", len(all_buyers))
    logger.info("Buyer needs: %s", dict(sorted(all_needs.items(), key=lambda x: -x[1])[:10]))

    # ============================================================
    # STEP 2: Find expiring domains that match buyer needs
    # ============================================================
    logger.info("Step 2/5: Finding expiring domains matching buyer needs...")

    expiring_task = expiring_scout.run()
    marketplace_task = marketplace_playwright.run()
    forsale_task = forsale_finder.run()

    expiring, marketplace, forsale = await asyncio.gather(
        expiring_task, marketplace_task, forsale_task,
        return_exceptions=True,
    )

    expiring_domains = expiring if isinstance(expiring, list) else []
    marketplace_domains = marketplace if isinstance(marketplace, list) else []
    forsale_domains = forsale if isinstance(forsale, list) else []

    # Merge all domains
    all_domains: list[dict] = []
    seen: set[str] = set()
    for d in expiring_domains + marketplace_domains + forsale_domains:
        name = d.get("domain_name", "")
        if name and name not in seen:
            seen.add(name)
            all_domains.append(d)

    # Count domains by category
    domain_categories: dict[str, int] = {}
    for d in all_domains:
        for cat in d.get("categories", ["generic"]):
            domain_categories[cat] = domain_categories.get(cat, 0) + 1

    logger.info("Found %d total domains", len(all_domains))
    logger.info("Domain categories: %s", dict(sorted(domain_categories.items(), key=lambda x: -x[1])[:10]))

    # ============================================================
    # STEP 3: Match buyers to domains
    # ============================================================
    logger.info("Step 3/5: Matching buyers to expiring domains...")

    # Extract seller contacts for high-value domains
    high_value_domains = [d for d in all_domains if (d.get("estimated_value", 0) > 50) or (d.get("price", 0) > 50)]
    domains_to_check = [d["domain_name"] for d in high_value_domains[:30]]

    if domains_to_check:
        contact_results = await seller_contact.run(domains_to_check[:50])
        contact_map = {c["domain_name"]: c for c in contact_results}
        for d in all_domains:
            if d["domain_name"] in contact_map:
                d.update(contact_map[d["domain_name"]])

    # ============================================================
    # STEP 4: Contact buyers with matching domains
    # ============================================================
    logger.info("Step 4/5: Preparing buyer outreach with matching domains...")

    buyer_outreach = await email_buyers.run(all_buyers, all_domains, dry_run=dry_run)

    # ============================================================
    # STEP 5: Contact sellers for high-value domains
    # ============================================================
    logger.info("Step 5/5: Contacting sellers for high-value domains...")

    sellers_to_contact = [d for d in all_domains if d.get("seller_emails") and (d.get("estimated_value", 0) > 100 or d.get("price", 0) > 50)]

    if sellers_to_contact:
        seller_outreach = await email_sellers.run(sellers_to_contact[:20], dry_run=dry_run)
    else:
        seller_outreach = {"sent": [], "skipped": [], "failed": []}

    # ============================================================
    # GENERATE REPORT
    # ============================================================
    logger.info("Generating report...")

    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    report_path = Path("data/reports")
    report_path.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")

    # Calculate profit potential
    total_profit = sum(s.get("profit_potential", 0) for s in buyer_outreach.get("prepared", []))

    json_report = {
        "date": date_str,
        "elapsed_seconds": round(elapsed, 1),
        "model": "buyer_first",
        "summary": {
            "total_buyers": len(all_buyers),
            "buyer_needs": all_needs,
            "total_domains": len(all_domains),
            "domain_categories": domain_categories,
            "buyer_outreach_prepared": len(buyer_outreach.get("prepared", [])),
            "buyer_outreach_skipped": len(buyer_outreach.get("skipped", [])),
            "seller_outreach_sent": len(seller_outreach.get("sent", [])),
            "estimated_total_profit": total_profit,
        },
        "top_buyer_leads": [
            {
                "author": b.get("author", ""),
                "source": b.get("source", ""),
                "title": b.get("title", "")[:80],
                "buyer_needs": b.get("buyer_needs", []),
                "suggested_domains": b.get("suggested_domains", [])[:3],
            }
            for b in all_buyers[:20]
        ],
        "top_domains": [
            {
                "domain": d["domain_name"],
                "categories": d.get("categories", []),
                "estimated_value": d.get("estimated_value", 0),
                "price": d.get("price", 0),
                "source": d.get("source", ""),
            }
            for d in all_domains[:20]
        ],
        "buyer_outreach": [
            {
                "author": o.get("author", ""),
                "source": o.get("source", ""),
                "matching_domains": o.get("matching_domains", []),
                "profit_potential": o.get("profit_potential", 0),
            }
            for o in buyer_outreach.get("prepared", [])[:10]
        ],
    }

    json_path = report_path / f"pipeline_report_{date_str}.json"
    with open(json_path, "w") as f:
        json.dump(json_report, f, indent=2)

    # Generate markdown report
    md_lines = [
        f"# Domain Broker Report — {date_str}",
        f"Pipeline completed in {elapsed:.1f}s",
        f"Model: **Buyer-First** (find buyer -> find domain -> register -> sell)",
        "",
        "## Summary",
        f"- Total buyers found: {len(all_buyers)}",
        f"- Buyer needs: {', '.join(f'{k}: {v}' for k, v in sorted(all_needs.items(), key=lambda x: -x[1])[:5])}",
        f"- Total domains found: {len(all_domains)}",
        f"- Domain categories: {', '.join(f'{k}: {v}' for k, v in sorted(domain_categories.items(), key=lambda x: -x[1])[:5])}",
        f"- Buyer outreach prepared: {len(buyer_outreach.get('prepared', []))}",
        f"- Estimated total profit: ${total_profit:.0f}",
        "",
        "## Top Buyer Leads",
        "| Author | Source | Needs | Suggested Domains |",
        "|--------|--------|-------|-------------------|",
    ]
    for b in all_buyers[:10]:
        needs = ", ".join(b.get("buyer_needs", [])[:2])
        domains = ", ".join(b.get("suggested_domains", [])[:2])
        md_lines.append(f"| {b.get('author', '')} | {b.get('source', '')} | {needs} | {domains} |")

    md_lines.extend([
        "",
        "## Top Domains by Value",
        "| Domain | Categories | Est. Value | Price | Source |",
        "|--------|-----------|------------|-------|--------|",
    ])
    for d in sorted(all_domains, key=lambda x: x.get("estimated_value", 0), reverse=True)[:10]:
        cats = ", ".join(d.get("categories", [])[:2])
        md_lines.append(f"| {d['domain_name']} | {cats} | ${d.get('estimated_value', 0):.0f} | ${d.get('price', 0):.0f} | {d.get('source', '')} |")

    md_lines.extend([
        "",
        "## Buyer Outreach Plan",
        "| Buyer | Needs | Domains | Profit Potential |",
        "|-------|-------|---------|------------------|",
    ])
    for o in buyer_outreach.get("prepared", [])[:10]:
        needs = ", ".join(o.get("buyer_needs", [])[:2])
        domains = ", ".join(o.get("suggested_domains", [])[:2])
        profit = o.get("profit_potential", 0)
        md_lines.append(f"| {o.get('author', '')} | {needs} | {domains} | ${profit:.0f} |")

    md_path = report_path / f"pipeline_report_{date_str}.md"
    with open(md_path, "w") as f:
        f.write("\n".join(md_lines))

    # ============================================================
    # SEND NOTIFICATIONS (Email + Discord)
    # ============================================================
    logger.info("Sending notifications...")

    md_text = "\n".join(md_lines)
    notifiers = [EmailNotifier(), DiscordNotifier()]
    for notifier in notifiers:
        try:
            if isinstance(notifier, EmailNotifier):
                sent = await notifier.send_alert(md_text)
            else:
                sent = await notifier.send_report(md_text, all_domains[:20])
            if sent:
                logger.info("Report sent via %s", type(notifier).__name__)
            else:
                logger.warning("Failed to send report via %s", type(notifier).__name__)
        except Exception as exc:
            logger.error("Notifier %s failed: %s", type(notifier).__name__, exc)

    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info("  Buyers found: %d", len(all_buyers))
    logger.info("  Domains found: %d", len(all_domains))
    logger.info("  Buyer outreach: %d prepared", len(buyer_outreach.get("prepared", [])))
    logger.info("  Estimated profit: $%.0f", total_profit)
    logger.info("=" * 60)

    return {
        "elapsed": elapsed,
        "buyers": len(all_buyers),
        "domains": len(all_domains),
        "buyer_outreach": len(buyer_outreach.get("prepared", [])),
        "estimated_profit": total_profit,
    }
