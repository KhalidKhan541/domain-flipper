"""Entry point for the 6-agent pipeline: python -m src.agents"""

from __future__ import annotations

import asyncio

from src.agents.orchestrator import run_pipeline


async def main():
    result = await run_pipeline(dry_run=False)
    print("\nPipeline Result:")
    for k, v in result.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    asyncio.run(main())
