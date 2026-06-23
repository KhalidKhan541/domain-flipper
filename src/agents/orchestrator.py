"""Main orchestrator — runs all 6 subagents in parallel."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from src.agents import feed_scraper, marketplace_scraper, forsale_finder
from src.agents import seller_extractor, domain_analyzer, email_outreach
from src.utils import setup_logger


async def run_pipeline(dry_run: bool = False) -> dict:
    """Run the full 6-agent pipeline."""
    logger = setup_logger("PipelineOrchestrator")
    start = datetime.now(timezone.utc)

    logger.info("=" * 60)
    logger.info("STARTING 6-AGENT DOMAIN BROKER PIPELINE")
    logger.info("=" * 60)

    # ============================================================
    # STEP 1: Run feed scraper + marketplace scraper + for-sale finder IN PARALLEL
    # ============================================================
    logger.info("Step 1/4: Running 3 discovery agents in parallel...")

    feeds_task = feed_scraper.run()
    marketplace_task = marketplace_scraper.run()
    forsale_task = forsale_finder.run()

    feed_results, marketplace_results, forsale_results = await asyncio.gather(
        feeds_task, marketplace_task, forsale_task,
        return_exceptions=True,
    )

    # Handle exceptions
    feed_domains = feed_results if isinstance(feed_results, list) else []
    marketplace_domains = marketplace_results if isinstance(marketplace_results, list) else []
    forsale_domains = forsale_results if isinstance(forsale_results, list) else []

    logger.info(
        "Discovery complete: %d feed + %d marketplace + %d for-sale = %d total",
        len(feed_domains), len(marketplace_domains), len(forsale_domains),
        len(feed_domains) + len(marketplace_domains) + len(forsale_domains),
    )

    # Merge all discovered domains
    all_domains: list[dict] = []
    seen: set[str] = set()

    for d in feed_domains + marketplace_domains + forsale_domains:
        name = d.get("domain_name", "")
        if name and name not in seen:
            seen.add(name)
            all_domains.append(d)

    logger.info("Merged to %d unique domains", len(all_domains))

    if not all_domains:
        logger.warning("No domains found, aborting")
        return {"error": "no_domains", "domains": 0}

    # ============================================================
    # STEP 2: Extract seller contacts for for-sale domains + top marketplace domains
    # ============================================================
    logger.info("Step 2/4: Extracting seller contacts...")

    # Prioritize domains that have for_sale flag or marketplace listings
    domains_needing_contacts = []
    for d in all_domains:
        if d.get("for_sale") or d.get("source") in ("flippa", "afternic", "dan"):
            domains_needing_contacts.append(d["domain_name"])
        elif d.get("seller_emails"):
            continue  # Already has contact info

    # Also add top feed domains
    for d in feed_domains[:20]:
        if d["domain_name"] not in domains_needing_contacts:
            domains_needing_contacts.append(d["domain_name"])

    # Limit to 50 to avoid rate limiting
    domains_needing_contacts = domains_needing_contacts[:50]

    if domains_needing_contacts:
        contact_results = await seller_extractor.run(domains_needing_contacts)
        # Merge contact info back into domain dicts
        contact_map = {c["domain_name"]: c for c in contact_results}
        for d in all_domains:
            if d["domain_name"] in contact_map:
                d.update(contact_map[d["domain_name"]])

    # ============================================================
    # STEP 3: Analyze all domains (HTTP status, value estimation)
    # ============================================================
    logger.info("Step 3/4: Analyzing domains...")
    analyzed = await domain_analyzer.run(all_domains)

    # ============================================================
    # STEP 4: Send emails to sellers
    # ============================================================
    logger.info("Step 4/4: Sending outreach emails...")
    outreach_result = await email_outreach.run(analyzed, dry_run=dry_run)

    # ============================================================
    # GENERATE REPORT
    # ============================================================
    elapsed = (datetime.now(timezone.utc) - start).total_seconds()

    # Save full report
    report_path = Path("data/reports")
    report_path.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")

    # JSON report
    json_report = {
        "date": date_str,
        "elapsed_seconds": round(elapsed, 1),
        "summary": {
            "feed_domains": len(feed_domains),
            "marketplace_domains": len(marketplace_domains),
            "forsale_domains": len(forsale_domains),
            "total_unique": len(all_domains),
            "emails_sent": len(outreach_result.get("sent", [])),
            "emails_skipped": len(outreach_result.get("skipped", [])),
            "emails_failed": len(outreach_result.get("failed", [])),
        },
        "top_domains": [
            {
                "domain": d["domain_name"],
                "estimated_value": d.get("estimated_value", 0),
                "commission": d.get("commission", 0),
                "seller_emails": d.get("seller_emails", []),
                "source": d.get("source", ""),
                "for_sale": d.get("for_sale", False),
            }
            for d in analyzed[:20]
        ],
    }

    json_path = report_path / f"pipeline_report_{date_str}.json"
    with open(json_path, "w") as f:
        json.dump(json_report, f, indent=2)

    # Markdown report
    md_lines = [
        f"# Domain Broker Report — {date_str}",
        f"Pipeline completed in {elapsed:.1f}s",
        "",
        "## Summary",
        f"- Feed domains: {len(feed_domains)}",
        f"- Marketplace domains: {len(marketplace_domains)}",
        f"- For-sale domains: {len(forsale_domains)}",
        f"- Total unique: {len(all_domains)}",
        f"- Emails sent: {len(outreach_result.get('sent', []))}",
        f"- Emails skipped: {len(outreach_result.get('skipped', []))}",
        f"- Emails failed: {len(outreach_result.get('failed', []))}",
        "",
        "## Top Domains",
        "| Domain | Est. Value | Commission | Seller Emails | Source |",
        "|--------|-----------|------------|---------------|--------|",
    ]

    for d in analyzed[:20]:
        emails = ", ".join(d.get("seller_emails", [])[:2])
        md_lines.append(
            f"| {d['domain_name']} | ${d.get('estimated_value', 0):.0f} | "
            f"${d.get('commission', 0):.0f} | {emails} | {d.get('source', '')} |"
        )

    md_path = report_path / f"pipeline_report_{date_str}.md"
    with open(md_path, "w") as f:
        f.write("\n".join(md_lines))

    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info("  Domains found: %d", len(all_domains))
    logger.info("  Emails sent: %d", len(outreach_result.get("sent", [])))
    logger.info("  Report: %s", json_path)
    logger.info("=" * 60)

    return {
        "elapsed": elapsed,
        "total_domains": len(all_domains),
        "emails_sent": len(outreach_result.get("sent", [])),
        "top_domain": analyzed[0]["domain_name"] if analyzed else "none",
        "top_value": analyzed[0].get("estimated_value", 0) if analyzed else 0,
    }
