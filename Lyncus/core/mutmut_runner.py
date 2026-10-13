"""Run mutmut and emit its machine-readable CI statistics."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    """Run mutation tests, export their statistics, and print only JSON to stdout."""
    run_result = subprocess.run(
        [sys.executable, "-m", "mutmut", "run"],
        check=False,
        stdout=sys.stderr,
        stderr=sys.stderr,
    )
    if run_result.returncode != 0:
        return run_result.returncode

    export_result = subprocess.run(
        [sys.executable, "-m", "mutmut", "export-cicd-stats"],
        check=False,
        stdout=sys.stderr,
        stderr=sys.stderr,
    )
    if export_result.returncode != 0:
        return export_result.returncode

    stats_path = Path("mutants/mutmut-cicd-stats.json")
    try:
        stats = json.loads(stats_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"Could not read mutmut CI stats: {error}", file=sys.stderr)
        return 2

    json.dump(stats, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
