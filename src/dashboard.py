"""
Domain Broker Dashboard — CLI for managing outreach.
Run: python -m src.dashboard
"""

from __future__ import annotations

import asyncio
from collections import Counter
from typing import Any
from src.outreach.tracker import OutreachTracker
from src.utils import setup_logger


def _fmt(val: Any, default: str = "-") -> str:
    return str(val).strip() if val else default


def _sep_row(widths: list[int]) -> str:
    return "+" + "+".join("-" * w for w in widths) + "+"


def _data_row(fields: list[str], widths: list[int]) -> str:
    parts = []
    for f, w in zip(fields, widths):
        parts.append(f.ljust(w))
    return "| " + " | ".join(parts) + " |"


def _header_row(headers: list[str], widths: list[int]) -> str:
    return _data_row(headers, widths)


def _print_table(headers: list[str], rows: list[list[str]], defaults: list[str] | None = None) -> None:
    if not rows:
        print("(none)")
        return
    n = len(headers)
    widths = [len(h) for h in headers]
    for row in rows:
        for i in range(n):
            widths[i] = max(widths[i], len(row[i]))
    widths = [min(w + 2, 50) for w in widths]
    sep = _sep_row(widths)
    print(sep)
    print(_header_row(headers, widths))
    print(sep)
    for row in rows:
        print(_data_row(row, widths))
    print(sep)


VALID_STATUSES = {"pending", "sent", "replied", "negotiating", "closed_won", "closed_lost"}


class Dashboard:
    def __init__(self) -> None:
        self.logger = setup_logger("Dashboard")
        self.tracker = OutreachTracker()

    async def run(self) -> None:
        await self.tracker.init_db()
        while True:
            self._show_menu()
            choice = input("\nSelect option: ").strip()
            if choice == "1":
                await self._show_summary()
            elif choice == "2":
                await self._show_pending()
            elif choice == "3":
                await self._show_domain_details()
            elif choice == "4":
                await self._update_status()
            elif choice == "5":
                await self._show_all()
            elif choice == "q":
                break
            else:
                print("Invalid option. Try again.")
        await self.tracker.close()

    def _show_menu(self) -> None:
        print("\n" + "=" * 50)
        print("  DOMAIN BROKER DASHBOARD")
        print("=" * 50)
        print("  1. Summary")
        print("  2. Pending outreach")
        print("  3. Domain details")
        print("  4. Update status")
        print("  5. All leads")
        print("  q. Quit")
        print("=" * 50)

    async def _show_summary(self) -> None:
        all_leads = await self.tracker.get_all()
        total = len(all_leads)
        by_status: Counter[str] = Counter(l["status"] for l in all_leads)
        by_type: Counter[str] = Counter(l["lead_type"] for l in all_leads)

        print(f"\nTotal leads: {total}")
        if total == 0:
            return

        print("\n── By Status ──")
        status_rows = [[s, str(c)] for s, c in sorted(by_status.items())]
        _print_table(["Status", "Count"], status_rows)
        print(f"  Total: {total}")

        print("\n── By Type ──")
        type_rows = [[t, str(c)] for t, c in sorted(by_type.items())]
        _print_table(["Type", "Count"], type_rows)

    async def _show_pending(self) -> None:
        pending = await self.tracker.get_pending()
        print(f"\nPending / Sent leads: {len(pending)}")
        if not pending:
            return
        rows = []
        for l in pending:
            rows.append([
                str(l["id"]),
                _fmt(l["domain_name"]),
                _fmt(l["company"]),
                _fmt(l["lead_type"]),
                _fmt(l["contact_name"]),
                _fmt(l["contact_email"]),
                _fmt(l["status"]),
            ])
        _print_table(
            ["ID", "Domain", "Company", "Type", "Contact", "Email", "Status"],
            rows,
        )

    async def _show_domain_details(self) -> None:
        domain = input("Enter domain name: ").strip()
        if not domain:
            print("No domain entered.")
            return
        leads = await self.tracker.get_by_domain(domain)
        print(f"\nLeads for {domain}: {len(leads)}")
        if not leads:
            return
        rows = []
        for l in leads:
            rows.append([
                str(l["id"]),
                _fmt(l["company"]),
                _fmt(l["lead_type"]),
                _fmt(l["contact_name"]),
                _fmt(l["contact_email"]),
                _fmt(l["status"]),
            ])
        _print_table(
            ["ID", "Company", "Type", "Contact", "Email", "Status"],
            rows,
        )

        print("\n── Detail ──")
        for l in leads:
            print(f"  ID: {l['id']}")
            print(f"  Domain: {l['domain_name']}")
            print(f"  Type: {l['lead_type']}")
            print(f"  Company: {_fmt(l['company'])}")
            print(f"  Contact: {_fmt(l['contact_name'])}  ({_fmt(l['contact_title'])})")
            print(f"  Email: {_fmt(l['contact_email'])}")
            print(f"  LinkedIn: {_fmt(l['contact_linkedin'])}")
            print(f"  Status: {l['status']}")
            print(f"  Subject: {_fmt(l['template_subject'])}")
            print(f"  Notes: {_fmt(l['notes'])}")
            print(f"  Created: {l['created_at']}")
            print(f"  Updated: {l['updated_at']}")
            print()

    async def _update_status(self) -> None:
        raw = input("Enter lead ID: ").strip()
        try:
            lead_id = int(raw)
        except ValueError:
            print("Invalid lead ID — must be a number.")
            return
        print(f"Status options: {', '.join(sorted(VALID_STATUSES))}")
        status = input("New status: ").strip().lower()
        if status not in VALID_STATUSES:
            print(f"Invalid status — must be one of: {', '.join(sorted(VALID_STATUSES))}")
            return
        notes = input("Notes (optional): ").strip()
        await self.tracker.update_status(lead_id, status, notes=notes or None)
        print(f"Lead {lead_id} updated to {status}.")

    async def _show_all(self) -> None:
        all_leads = await self.tracker.get_all()
        print(f"\nAll leads: {len(all_leads)}")
        if not all_leads:
            return
        rows = []
        for l in all_leads:
            rows.append([
                str(l["id"]),
                _fmt(l["domain_name"]),
                _fmt(l["company"]),
                _fmt(l["lead_type"]),
                _fmt(l["contact_name"]),
                _fmt(l["contact_email"]),
                _fmt(l["status"]),
            ])
        _print_table(
            ["ID", "Domain", "Company", "Type", "Contact", "Email", "Status"],
            rows,
        )


async def main() -> None:
    dashboard = Dashboard()
    await dashboard.run()


if __name__ == "__main__":
    asyncio.run(main())
