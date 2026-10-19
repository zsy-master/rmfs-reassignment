from __future__ import annotations

import csv
import platform
import statistics
import time
from pathlib import Path

from experiment_runner import build_instances_for_seed, load_config
from rmfs_core import select_association_greedy, select_budgeted_batching_aware


ROOT = Path(__file__).resolve().parent
CONFIG = load_config(ROOT / "protocol_config.json")
OUT = ROOT / "final_package"
SEEDS = (2026092401, 2026092402, 2026092403)
SCENARIOS = ("no_drift", "abrupt", "gradual")


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    observations = []
    for seed in SEEDS:
        instances = build_instances_for_seed(seed, CONFIG, 0.30)
        for scenario in SCENARIOS:
            instance = instances[scenario]
            tasks = [("B2_K5", "B2", 5), ("M_K1", "M", 1), ("M_K3", "M", 3), ("M_K5", "M", 5)]
            for label, method, budget in tasks:
                start = time.perf_counter()
                if method == "B2":
                    result = select_association_greedy(instance.initial_layout, instance.decision_orders, budget)
                else:
                    result = select_budgeted_batching_aware(
                        instance.initial_layout,
                        instance.decision_orders,
                        CONFIG["batch_capacity"],
                        budget,
                        0.0,
                        CONFIG["test_orders"],
                    )
                elapsed = time.perf_counter() - start
                observations.append(
                    {
                        "seed": seed,
                        "scenario": scenario,
                        "method": label,
                        "budget_k": budget,
                        "executed_swaps": len(result.swaps),
                        "runtime_seconds": elapsed,
                    }
                )
                print(f"{seed} {scenario} {label}: {elapsed:.4f}s", flush=True)
    write_csv(OUT / "Runtime_Table.csv", observations)
    summary = []
    for label in ("B2_K5", "M_K1", "M_K3", "M_K5"):
        values = [float(row["runtime_seconds"]) for row in observations if row["method"] == label]
        summary.append(
            {
                "method": label,
                "n_instances": len(values),
                "mean_seconds": statistics.mean(values),
                "median_seconds": statistics.median(values),
                "min_seconds": min(values),
                "max_seconds": max(values),
            }
        )
    write_csv(OUT / "Runtime_Summary.csv", summary)
    (OUT / "runtime_environment.txt").write_text(
        f"platform={platform.platform()}\npython={platform.python_version()}\nprocessor={platform.processor()}\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
