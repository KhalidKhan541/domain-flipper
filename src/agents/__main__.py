"""Entry point for the 7-agent pipeline: python -m src.agents"""

from __future__ import annotations

import asyncio
from pathlib import Path

from src.agents.orchestrator import run_pipeline


async def main():
    Path("data").mkdir(parents=True, exist_ok=True)
    Path("data/reports").mkdir(parents=True, exist_ok=True)
    result = await run_pipeline(dry_run=False)
    print("\nPipeline Result:")
    for k, v in result.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    asyncio.run(main())
