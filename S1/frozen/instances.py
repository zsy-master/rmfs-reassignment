"""Instance construction extracted from the frozen experiment runner.

All retained class/function bodies are unchanged. Pilot-only execution is omitted.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from rmfs_core import Layout, Order
from synthetic_data import (
    base_community_labels,
    build_initial_layout,
    drift_by_pair_swaps,
    generate_gradual_orders,
    generate_orders,
)


@dataclass(frozen=True)
class ExperimentInstance:
    master_seed: int
    scenario: str
    drift_ratio_target: float
    drift_ratio_realized: float
    initial_orders: tuple[Order, ...]
    initial_layout: Layout
    decision_orders: tuple[Order, ...]
    test_orders: tuple[Order, ...]
    initial_fingerprint: str
    instance_fingerprint: str


def load_config(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def derived_seed(master_seed: int, *parts: object) -> int:
    payload = "|".join([str(master_seed), *(str(part) for part in parts)])
    return int.from_bytes(hashlib.sha256(payload.encode("utf-8")).digest()[:8], "big")


def _orders_payload(orders: Sequence[Order]) -> list[list[object]]:
    return [[order.order_id, list(order.skus)] for order in orders]


def fingerprint(*objects: object) -> str:
    payload = json.dumps(objects, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_instances_for_seed(
    master_seed: int, config: dict, drift_ratio: float
) -> dict[str, ExperimentInstance]:
    """Build all scenarios while sharing one initial window and layout.

    Hidden labels are consumed only by order generators in this function. They are
    not stored in ExperimentInstance and cannot reach layout construction or strategies.
    """
    n_skus = config["n_skus"]
    n_pods = config["n_pods"]
    capacity = config["pod_capacity"]
    length_probs = {
        int(length): probability
        for length, probability in config["order_length_probabilities"].items()
    }
    p_within = config["within_community_probability"]
    old_labels = base_community_labels(n_skus, n_pods)
    new_labels, realized_ratio = drift_by_pair_swaps(
        old_labels,
        drift_ratio,
        random.Random(derived_seed(master_seed, "drift_labels")),
    )

    initial_orders = generate_orders(
        config["initial_orders"],
        old_labels,
        random.Random(derived_seed(master_seed, "initial_window")),
        length_probs,
        p_within,
    )
    initial_layout = build_initial_layout(initial_orders, n_skus, n_pods, capacity)
    initial_fingerprint = fingerprint(_orders_payload(initial_orders), initial_layout)

    instances: dict[str, ExperimentInstance] = {}
    for scenario in config["scenarios"]:
        decision_rng = random.Random(derived_seed(master_seed, scenario, "decision_window"))
        test_rng = random.Random(derived_seed(master_seed, scenario, "test_window"))
        if scenario == "no_drift":
            decision_orders = generate_orders(
                config["decision_orders"], old_labels, decision_rng, length_probs, p_within
            )
            test_orders = generate_orders(
                config["test_orders"], old_labels, test_rng, length_probs, p_within
            )
            scenario_realized_ratio = 0.0
        elif scenario == "abrupt":
            decision_orders = generate_orders(
                config["decision_orders"], new_labels, decision_rng, length_probs, p_within
            )
            test_orders = generate_orders(
                config["test_orders"], new_labels, test_rng, length_probs, p_within
            )
            scenario_realized_ratio = realized_ratio
        elif scenario == "gradual":
            decision_orders = generate_gradual_orders(
                config["decision_orders"],
                old_labels,
                new_labels,
                decision_rng,
                length_probs,
                p_within,
            )
            test_orders = generate_orders(
                config["test_orders"], new_labels, test_rng, length_probs, p_within
            )
            scenario_realized_ratio = realized_ratio
        else:
            raise ValueError(f"Unknown scenario: {scenario}")

        instance_fingerprint = fingerprint(
            initial_layout,
            _orders_payload(decision_orders),
            _orders_payload(test_orders),
        )
        instances[scenario] = ExperimentInstance(
            master_seed=master_seed,
            scenario=scenario,
            drift_ratio_target=drift_ratio if scenario != "no_drift" else 0.0,
            drift_ratio_realized=scenario_realized_ratio,
            initial_orders=initial_orders,
            initial_layout=initial_layout,
            decision_orders=decision_orders,
            test_orders=test_orders,
            initial_fingerprint=initial_fingerprint,
            instance_fingerprint=instance_fingerprint,
        )

    fingerprints = {instance.initial_fingerprint for instance in instances.values()}
    layouts = {instance.initial_layout for instance in instances.values()}
    if len(fingerprints) != 1 or len(layouts) != 1:
        raise AssertionError("Scenarios with the same seed must share initial data and layout.")
    return instances
