"""One search/expansion implementation for all three locked drift intensities."""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

from instances import build_instances_for_seed, derived_seed, load_config
from rmfs_core import (
    EPS,
    apply_swap,
    batch_orders,
    select_association_greedy,
    select_budgeted_batching_aware,
    select_random_swaps,
)

ROOT = Path(__file__).resolve().parent
SEEDS = tuple(range(2026092401, 2026092501))
COUNTS = (9, 5, 13)
STRATEGIES = ("B0", "B1", "B2", "B3", "M")


def scenarios_for(count: int) -> tuple[str, ...]:
    if count not in COUNTS:
        raise ValueError(f"Unsupported locked drift count: {count}")
    return ("no_drift", "abrupt", "gradual") if count == 9 else ("abrupt", "gradual")


def search(seed: int, count: int) -> dict:
    """Search decision orders only; preserve the formal B1 seed and B3 path."""
    config = load_config(ROOT / "protocol_config.json")
    instances = build_instances_for_seed(seed, config, count / 30)
    scenarios = {}
    for scenario in scenarios_for(count):
        instance = instances[scenario]
        start = time.perf_counter()
        b1 = select_random_swaps(
            instance.initial_layout,
            max(config["budgets"]),
            derived_seed(seed, scenario, "B1", max(config["budgets"])),
        )
        b1_time = time.perf_counter() - start
        start = time.perf_counter()
        b2 = select_association_greedy(
            instance.initial_layout,
            instance.decision_orders,
            max(config["budgets"]),
        )
        b2_time = time.perf_counter() - start
        start = time.perf_counter()
        b3 = select_budgeted_batching_aware(
            instance.initial_layout,
            instance.decision_orders,
            config["batch_capacity"],
            None,
            0.0,
            config["test_orders"],
        )
        b3_time = time.perf_counter() - start
        scenarios[scenario] = {
            "target_drift_ratio": instance.drift_ratio_target,
            "realized_drift_ratio": instance.drift_ratio_realized,
            "initial_fingerprint": instance.initial_fingerprint,
            "instance_fingerprint": instance.instance_fingerprint,
            "B1": {"pairs": [list(r.sku_pair) for r in b1.swaps], "runtime_seconds": b1_time},
            "B2": {"pairs": [list(r.sku_pair) for r in b2.swaps], "runtime_seconds": b2_time},
            "B3": {
                "records": [
                    dict(
                        step=r.step,
                        sku_pair=list(r.sku_pair),
                        value_before=r.value_before,
                        value_after=r.value_after,
                        marginal_gain=r.marginal_gain,
                        score_at_lambda_0=r.score,
                    )
                    for r in b3.swaps
                ],
                "runtime_seconds": b3_time,
            },
        }
    payload = {"seed": seed, "scenarios": scenarios}
    if count != 9:
        payload["changed_skus"] = count
    return payload


def validate_checkpoint(payload: dict, seed: int, count: int) -> None:
    if payload.get("seed") != seed or (count != 9 and payload.get("changed_skus") != count):
        raise ValueError("Checkpoint identity mismatch")
    if tuple(payload.get("scenarios", {})) != scenarios_for(count):
        raise ValueError("Incomplete checkpoint scenarios")
    for scenario, stored in payload["scenarios"].items():
        ratio = 0.0 if scenario == "no_drift" else count / 30
        if not math.isclose(stored["realized_drift_ratio"], ratio, rel_tol=0, abs_tol=EPS):
            raise ValueError("Checkpoint drift ratio mismatch")


def expand(seed: int, count: int, payload: dict) -> tuple[list[dict], list[dict]]:
    """Rebuild instances, replay paths, and evaluate each distinct final layout once.

    Evaluation caching is local to an immutable test window; PV is independent of
    K, lambda and strategy. TC and movement are computed separately for every row.
    """
    validate_checkpoint(payload, seed, count)
    config = load_config(ROOT / "protocol_config.json")
    instances = build_instances_for_seed(seed, config, count / 30)
    detail, paths = [], []
    for scenario in scenarios_for(count):
        instance, stored = instances[scenario], payload["scenarios"][scenario]
        for field in ("initial_fingerprint", "instance_fingerprint"):
            if getattr(instance, field) != stored[field]:
                raise ValueError(f"{field} mismatch: seed={seed}, count={count}, {scenario}")
        b1_pairs, b2_pairs, records = (
            stored["B1"]["pairs"],
            stored["B2"]["pairs"],
            stored["B3"]["records"],
        )
        intensity = {} if count == 9 else {"changed_skus": count, "drift_ratio": count / 30}
        for strategy, pairs, gains, runtime in (
            ("B1", b1_pairs, "", stored["B1"]["runtime_seconds"]),
            ("B2", b2_pairs, "", stored["B2"]["runtime_seconds"]),
            (
                "B3_lambda0",
                [r["sku_pair"] for r in records],
                json.dumps([r["marginal_gain"] for r in records], separators=(",", ":")),
                stored["B3"]["runtime_seconds"],
            ),
        ):
            paths.append(
                {
                    **intensity,
                    "seed": seed,
                    "scenario": scenario,
                    "strategy": strategy,
                    "path_length": len(pairs),
                    "swap_sequence": compact(pairs),
                    "marginal_gains": gains,
                    "search_runtime_seconds": runtime,
                    "initial_fingerprint": instance.initial_fingerprint,
                    "instance_fingerprint": instance.instance_fingerprint,
                }
            )
        layout_cache, pv_cache = {}, {}
        for lam in config["lambdas"]:
            b3_pairs = []
            for record in records:
                if record["marginal_gain"] - 2 * lam <= EPS:
                    break
                b3_pairs.append(record["sku_pair"])
            for budget in config["budgets"]:
                by_strategy = {
                    "B0": [],
                    "B1": b1_pairs[:budget],
                    "B2": b2_pairs[:budget],
                    "B3": b3_pairs,
                    "M": b3_pairs[:budget],
                }
                for strategy, pairs in by_strategy.items():
                    start = time.perf_counter()
                    key = tuple(tuple(pair) for pair in pairs)
                    if key not in layout_cache:
                        layout = instance.initial_layout
                        for pair in key:
                            layout = apply_swap(layout, pair)
                        layout_cache[key] = layout
                    layout = layout_cache[key]
                    if layout not in pv_cache:
                        pv_cache[layout] = batch_orders(
                            instance.test_orders,
                            layout,
                            config["batch_capacity"],
                        ).pod_visits
                    pv, movement = float(pv_cache[layout]), float(2 * len(pairs))
                    drift = (
                        {
                            "target_drift_ratio": instance.drift_ratio_target,
                            "realized_drift_ratio": instance.drift_ratio_realized,
                        }
                        if count == 9
                        else intensity
                    )
                    detail.append(
                        {
                            **drift,
                            "seed": seed,
                            "scenario": scenario,
                            "budget_k": budget,
                            "lambda": lam,
                            "strategy": strategy,
                            "first_swap": "" if not pairs else f"{pairs[0][0]}-{pairs[0][1]}",
                            "swap_sequence": compact(pairs),
                            "n_swaps": len(pairs),
                            "pv_test": pv,
                            "movement": movement,
                            "total_cost": pv + lam * movement,
                            "final_layout": compact(layout),
                            # Search time is the shared full path, NOT standalone M time.
                            "path_search_runtime_seconds": (
                                0.0
                                if strategy == "B0"
                                else stored["B3" if strategy == "M" else strategy][
                                    "runtime_seconds"
                                ]
                            ),
                            "evaluation_runtime_seconds": time.perf_counter() - start,
                            "initial_fingerprint": instance.initial_fingerprint,
                            "instance_fingerprint": instance.instance_fingerprint,
                        }
                    )
    return detail, paths


def compact(value) -> str:
    return json.dumps(value, separators=(",", ":"))


def middle_intensity(rows: list[dict]) -> list[dict]:
    return [
        dict(
            changed_skus=9,
            drift_ratio=0.3,
            **{
                k: v
                for k, v in row.items()
                if k not in {"target_drift_ratio", "realized_drift_ratio"}
            },
        )
        for row in rows
        if row["scenario"] in {"abrupt", "gradual"}
    ]
