"""Main orchestrator — runs all 8 subagents in parallel."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from src.agents import (
    expiring_scout, marketplace_monitor, forsale_finder,
    buyer_finder_reddit, buyer_finder_hn,
    seller_contact, email_sellers, email_buyers,
)
from src.utils import setup_logger


async def run_pipeline(dry_run: bool = False) -> dict:
    """Run the full 8-agent pipeline."""
    logger = setup_logger("PipelineOrchestrator")
    start = datetime.now(timezone.utc)

    logger.info("=" * 60)
    logger.info("STARTING 8-AGENT DOMAIN BROKER PIPELINE")
    logger.info("=" * 60)

    # ============================================================
    # STEP 1: Run 5 discovery agents IN PARALLEL
    # ============================================================
    logger.info("Step 1/5: Running 5 discovery agents in parallel...")

    expiring_task = expiring_scout.run()
    marketplace_task = marketplace_monitor.run()
    forsale_task = forsale_finder.run()
    reddit_task = buyer_finder_reddit.run()
    hn_task = buyer_finder_hn.run()

    expiring, marketplace, forsale, reddit, hn = await asyncio.gather(
        expiring_task, marketplace_task, forsale_task, reddit_task, hn_task,
        return_exceptions=True,
    )

    expiring_domains = expiring if isinstance(expiring, list) else []
    marketplace_domains = marketplace if isinstance(marketplace, list) else []
    forsale_domains = forsale if isinstance(forsale, list) else []
    reddit_buyers = reddit if isinstance(reddit, list) else []
    hn_data = hn if isinstance(hn, dict) else {}
    hn_buyers = hn_data.get("buyers", [])
    hn_auctions = hn_data.get("auctions", [])

    # Merge all domains for sale
    all_for_sale: list[dict] = []
    seen: set[str] = set()
    for d in marketplace_domains + forsale_domains + hn_auctions:
        name = d.get("domain_name", "")
        if name and name not in seen:
            seen.add(name)
            all_for_sale.append(d)

    logger.info(
        "Discovery: %d expiring + %d marketplace + %d for-sale + %d hn-auctions = %d for-sale domains",
        len(expiring_domains), len(marketplace_domains), len(forsale_domains), len(hn_auctions), len(all_for_sale),
    )
    logger.info(
        "Buyers: %d reddit + %d hn = %d total leads",
        len(reddit_buyers), len(hn_buyers), len(reddit_buyers) + len(hn_buyers),
    )

    # ============================================================
    # STEP 2: Extract seller contacts for for-sale domains
    # ============================================================
    logger.info("Step 2/5: Extracting seller contacts...")

    domains_to_check = [d["domain_name"] for d in all_for_sale[:30]]
    # Also check some expiring domains
    for d in expiring_domains[:20]:
        if d["domain_name"] not in domains_to_check:
            domains_to_check.append(d["domain_name"])

    if domains_to_check:
        contact_results = await seller_contact.run(domains_to_check[:50])
        contact_map = {c["domain_name"]: c for c in contact_results}
        for d in all_for_sale:
            if d["domain_name"] in contact_map:
                d.update(contact_map[d["domain_name"]])
        for d in expiring_domains:
            if d["domain_name"] in contact_map:
                d.update(contact_map[d["domain_name"]])

    # ============================================================
    # STEP 3: Contact sellers — offer to broker
    # ============================================================
    logger.info("Step 3/5: Contacting sellers...")

    sellers_to_contact = [d for d in all_for_sale if d.get("seller_emails")]
    sellers_to_contact.extend([d for d in expiring_domains if d.get("seller_emails")])

    if sellers_to_contact:
        seller_outreach = await email_sellers.run(sellers_to_contact[:20], dry_run=dry_run)
    else:
        seller_outreach = {"sent": [], "skipped": [], "failed": []}

    # ============================================================
    # STEP 4: Contact buyers — offer domains
    # ============================================================
    logger.info("Step 4/5: Preparing buyer outreach...")

    all_buyers = reddit_buyers + hn_buyers
    buyer_outreach = await email_buyers.run(all_buyers, all_for_sale, dry_run=dry_run)

    # ============================================================
    # STEP 5: Generate report
    # ============================================================
    logger.info("Step 5/5: Generating report...")

    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    report_path = Path("data/reports")
    report_path.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")

    json_report = {
        "date": date_str,
        "elapsed_seconds": round(elapsed, 1),
        "summary": {
            "expiring_domains": len(expiring_domains),
            "marketplace_domains": len(marketplace_domains),
            "forsale_domains": len(forsale_domains),
            "hn_auctions": len(hn_auctions),
            "total_for_sale": len(all_for_sale),
            "reddit_buyers": len(reddit_buyers),
            "hn_buyers": len(hn_buyers),
            "total_buyers": len(all_buyers),
            "seller_outreach_sent": len(seller_outreach.get("sent", [])),
            "buyer_outreach_prepared": len(buyer_outreach.get("prepared", [])),
        },
        "top_for_sale_domains": [
            {"domain": d["domain_name"], "price": d.get("price", 0), "source": d.get("source", ""), "seller_emails": d.get("seller_emails", [])}
            for d in all_for_sale[:20]
        ],
        "top_buyer_leads": [
            {"author": b.get("author", ""), "source": b.get("source", ""), "title": b.get("title", "")[:80]}
            for b in all_buyers[:20]
        ],
    }

    json_path = report_path / f"pipeline_report_{date_str}.json"
    with open(json_path, "w") as f:
        json.dump(json_report, f, indent=2)

    md_lines = [
        f"# Domain Broker Report — {date_str}",
        f"Pipeline completed in {elapsed:.1f}s",
        "",
        "## Summary",
        f"- Expiring domains found: {len(expiring_domains)}",
        f"- Marketplace domains: {len(marketplace_domains)}",
        f"- For-sale domains: {len(forsale_domains)}",
        f"- HN auctions: {len(hn_auctions)}",
        f"- Reddit buyers: {len(reddit_buyers)}",
        f"- HN buyers: {len(hn_buyers)}",
        f"- Seller outreach sent: {len(seller_outreach.get('sent', []))}",
        f"- Buyer outreach prepared: {len(buyer_outreach.get('prepared', []))}",
        "",
        "## Top For-Sale Domains",
        "| Domain | Price | Source | Seller Email |",
        "|--------|-------|--------|--------------|",
    ]
    for d in all_for_sale[:15]:
        emails = ", ".join(d.get("seller_emails", [])[:2])
        md_lines.append(f"| {d['domain_name']} | ${d.get('price', 0):.0f} | {d.get('source', '')} | {emails} |")

    md_lines.extend(["", "## Top Buyer Leads", "| Author | Source | Title |", "|--------|--------|-------|"])
    for b in all_buyers[:15]:
        md_lines.append(f"| {b.get('author', '')} | {b.get('source', '')} | {b.get('title', '')[:50]} |")

    md_path = report_path / f"pipeline_report_{date_str}.md"
    with open(md_path, "w") as f:
        f.write("\n".join(md_lines))

    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info("  For-sale domains: %d", len(all_for_sale))
    logger.info("  Buyer leads: %d", len(all_buyers))
    logger.info("  Seller outreach: %d sent", len(seller_outreach.get("sent", [])))
    logger.info("  Buyer outreach: %d prepared", len(buyer_outreach.get("prepared", [])))
    logger.info("=" * 60)

    return {
        "elapsed": elapsed,
        "for_sale_domains": len(all_for_sale),
        "buyer_leads": len(all_buyers),
        "seller_outreach": len(seller_outreach.get("sent", [])),
        "buyer_outreach": len(buyer_outreach.get("prepared", [])),
    }
