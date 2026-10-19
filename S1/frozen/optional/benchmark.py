"""Time direct M/B2 calls serially; shared path timings are not used."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from _common import load_legacy, new_output
from io_utils import read_rows, save_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scope",
        choices=["one", "all"],
        default="all",
        help="one = first seed, 3 instances; all = original 3 seeds, 9 instances",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    legacy = load_legacy("benchmark_runtime")
    if args.scope == "one":
        legacy.SEEDS = legacy.SEEDS[:1]
    output = new_output(args.output)
    legacy.OUT = output
    manifest = {
        "status": "RUNNING",
        "scope": args.scope,
        "seeds": list(legacy.SEEDS),
        "started_local": datetime.now().isoformat(),
        "execution": "serial standalone calls",
        "runtime_match_required": False,
    }
    save_json(output / "BENCHMARK_REPORT.json", manifest)
    try:
        legacy.main()
        rows = read_rows(output / "Runtime_Table.csv")
        expected = len(legacy.SEEDS) * len(legacy.SCENARIOS) * 4
        if len(rows) != expected:
            raise ValueError("Incomplete runtime measurements")
        manifest.update(
            status="PASS", observations=len(rows), finished_local=datetime.now().isoformat()
        )
        save_json(output / "BENCHMARK_REPORT.json", manifest)
        print(json.dumps(manifest, indent=2), flush=True)
    except BaseException as error:
        manifest.update(status="FAIL", error=repr(error))
        save_json(output / "BENCHMARK_REPORT.json", manifest)
        raise


if __name__ == "__main__":
    main()
