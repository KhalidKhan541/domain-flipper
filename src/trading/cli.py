"""
Safe Trading CLI — Run the safe domain trading pipeline.
Usage: python -m src.trading.cli <command> [args]
"""

from __future__ import annotations

import asyncio
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.main import DomainBroker
from src.config import settings


async def main():
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    command = sys.argv[1]

    if command == "--help" or command == "-h":
        print_usage()
        sys.exit(0)

    broker = DomainBroker()
    await broker.db.init_db()

    try:
        if command == "setup-wallet":
            print("Creating crypto wallet...")
            status = await broker.setup_wallet()
            print(json.dumps(status, indent=2))

        elif command == "verify":
            if len(sys.argv) < 3:
                print("Usage: python -m src.trading.cli verify <domain>")
                sys.exit(1)
            domain = sys.argv[2]
            print(f"Verifying ownership of {domain}...")
            result = await broker.verify_domain(domain)
            print(json.dumps(result, indent=2))

        elif command == "status":
            print("Getting trading status...")
            status = await broker.get_trading_status()
            print(json.dumps(status, indent=2))

        elif command == "trade":
            if len(sys.argv) < 4:
                print("Usage: python -m src.trading.cli trade <domain> <price_usd>")
                sys.exit(1)
            domain = sys.argv[2]
            price = float(sys.argv[3])
            print(f"Running safe trading pipeline for {domain} (${price} USDC)...")
            result = await broker.run_safe_trading_pipeline(domain, price)
            print(json.dumps(result, indent=2, default=str))

        else:
            print(f"Unknown command: {command}")
            print_usage()
            sys.exit(1)

    finally:
        await broker.verifier.close()
        await broker.db.close()


def print_usage():
    print("Safe Trading CLI — No Bank Account Needed")
    print("")
    print("Usage: python -m src.trading.cli <command> [args]")
    print("")
    print("Commands:")
    print("  setup-wallet              Create crypto wallet")
    print("  verify <domain>           Verify domain ownership via RDAP/WHOIS")
    print("  status                    Show trading status (wallets, escrows, transfers)")
    print("  trade <domain> <price>    Run full trading pipeline")
    print("")
    print("Examples:")
    print("  python -m src.trading.cli setup-wallet")
    print("  python -m src.trading.cli verify example.com")
    print("  python -m src.trading.cli trade example.com 500")
    print("  python -m src.trading.cli status")
    print("")
    print("Safe Trading Flow:")
    print("  1. setup-wallet  → Create Coinbase/Phantom wallet (free)")
    print("  2. trade         → Find, verify, escrow, transfer, cashout")
    print("  3. status        → Check active deals and balances")
