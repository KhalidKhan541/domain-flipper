"""Allow running: python -m src.trading <command> [args]"""
from src.trading.cli import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
