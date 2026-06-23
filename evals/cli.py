"""CLI: ``uv run python -m evals.cli <dataset.yaml>``."""

import asyncio
import sys
from pathlib import Path

from evals.reporters import print_report
from evals.runner import load_dataset, run_dataset
from evals.scorers import SCORERS
from evals.targets import FakeAgentsTarget


async def main(argv: list[str]) -> int:
    if not argv:
        print("usage: python -m evals.cli <dataset.yaml>")
        return 2
    path = Path(argv[0])
    if not path.exists():
        print(f"dataset not found: {path}")
        return 2
    cases = load_dataset(path)
    target = FakeAgentsTarget()
    report = await run_dataset(path.stem, cases, target, SCORERS)
    print_report(report)
    return 0 if report.pass_rate == 1.0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
