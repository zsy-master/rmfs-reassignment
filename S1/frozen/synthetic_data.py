"""Synthetic data generation separated from strategy selection."""

from __future__ import annotations

from collections import Counter
from itertools import combinations
from math import floor
from random import Random
from typing import Mapping, Sequence

from rmfs_core import Layout, Order, jaccard_matrix, normalize_layout


def base_community_labels(n_skus: int, n_communities: int) -> dict[int, int]:
    if n_skus % n_communities != 0:
        raise ValueError("The first protocol version requires equal-sized communities.")
    community_size = n_skus // n_communities
    return {sku: (sku - 1) // community_size for sku in range(1, n_skus + 1)}


def drift_by_pair_swaps(
    labels: Mapping[int, int], drift_ratio: float, rng: Random
) -> tuple[dict[int, int], float]:
    """Permute labels of disjoint SKU cycles while preserving community sizes.

    An odd target uses one three-SKU cycle; the remainder uses pair swaps.
    The historical function name is retained so existing scripts remain stable.
    """
    if not 0 <= drift_ratio <= 1:
        raise ValueError("drift_ratio must be in [0, 1].")
    result = dict(labels)
    # Use conventional half-up rounding. For 30 SKUs and 30%, this gives 9.
    target_changed = floor(len(labels) * drift_ratio + 0.5)
    if target_changed == 1:
        target_changed = 2
    available = list(sorted(labels))
    rng.shuffle(available)
    pairs: list[tuple[int, int]] = []

    changed = 0
    if target_changed % 2 == 1:
        triple: tuple[int, int, int] | None = None
        for candidate in combinations(available, 3):
            if len({labels[sku] for sku in candidate}) == 3:
                triple = candidate
                break
        if triple is None:
            raise ValueError("Unable to form a three-community drift cycle.")
        left, middle, right = triple
        result[left], result[middle], result[right] = (
            labels[middle],
            labels[right],
            labels[left],
        )
        for sku in triple:
            available.remove(sku)
        changed += 3

    target_pairs = (target_changed - changed) // 2
    while len(pairs) < target_pairs:
        found = False
        for left_index, left_sku in enumerate(available):
            for right_index in range(left_index + 1, len(available)):
                right_sku = available[right_index]
                if result[left_sku] != result[right_sku]:
                    pairs.append((left_sku, right_sku))
                    available.pop(right_index)
                    available.pop(left_index)
                    found = True
                    break
            if found:
                break
        if not found:
            break

    for left_sku, right_sku in pairs:
        result[left_sku], result[right_sku] = result[right_sku], result[left_sku]
    changed += 2 * len(pairs)
    realized_ratio = changed / len(labels)
    return result, realized_ratio


def _draw_order_length(rng: Random, probabilities: Mapping[int, float]) -> int:
    lengths = sorted(probabilities)
    weights = [probabilities[length] for length in lengths]
    if abs(sum(weights) - 1.0) > 1e-9:
        raise ValueError("Order-length probabilities must sum to one.")
    return rng.choices(lengths, weights=weights, k=1)[0]


def generate_orders(
    count: int,
    labels: Mapping[int, int],
    rng: Random,
    length_probabilities: Mapping[int, float],
    within_community_probability: float,
    first_order_id: int = 1,
) -> tuple[Order, ...]:
    if not 0 <= within_community_probability <= 1:
        raise ValueError("within_community_probability must be in [0, 1].")
    communities: dict[int, list[int]] = {}
    for sku, community in labels.items():
        communities.setdefault(community, []).append(sku)
    community_ids = sorted(communities)
    all_skus = sorted(labels)
    orders: list[Order] = []

    for offset in range(count):
        order_length = _draw_order_length(rng, length_probabilities)
        focal = rng.choice(community_ids)
        selected = [rng.choice(communities[focal])]
        while len(selected) < order_length:
            within_candidates = [sku for sku in communities[focal] if sku not in selected]
            all_candidates = [sku for sku in all_skus if sku not in selected]
            if within_candidates and rng.random() < within_community_probability:
                selected.append(rng.choice(within_candidates))
            else:
                selected.append(rng.choice(all_candidates))
        orders.append(Order(first_order_id + offset, tuple(selected)))
    return tuple(orders)


def generate_gradual_orders(
    count: int,
    old_labels: Mapping[int, int],
    new_labels: Mapping[int, int],
    rng: Random,
    length_probabilities: Mapping[int, float],
    within_community_probability: float,
    first_order_id: int = 1,
) -> tuple[Order, ...]:
    """Increase the probability of using the new structure linearly from 0 to 1."""
    orders: list[Order] = []
    for offset in range(count):
        alpha = 1.0 if count == 1 else offset / (count - 1)
        labels = new_labels if rng.random() < alpha else old_labels
        order = generate_orders(
            1,
            labels,
            rng,
            length_probabilities,
            within_community_probability,
            first_order_id + offset,
        )[0]
        orders.append(order)
    return tuple(orders)


def build_initial_layout(
    initial_orders: Sequence[Order], n_skus: int, n_pods: int, capacity: int
) -> Layout:
    """Deterministic Jaccard-greedy packing based only on the initial window."""
    if n_skus != n_pods * capacity:
        raise ValueError("n_skus must equal n_pods * capacity.")
    skus = list(range(1, n_skus + 1))
    similarities = jaccard_matrix(initial_orders, skus)
    frequencies = Counter(sku for order in initial_orders for sku in order.skus)
    unassigned = set(skus)
    pods: list[list[int]] = []

    for _ in range(n_pods):
        seed = min(unassigned, key=lambda sku: (-frequencies[sku], sku))
        pod = [seed]
        unassigned.remove(seed)
        while len(pod) < capacity:
            candidate = min(
                unassigned,
                key=lambda sku: (
                    -sum(
                        similarities.get(tuple(sorted((sku, placed))), 0.0)
                        for placed in pod
                    ),
                    -frequencies[sku],
                    sku,
                ),
            )
            pod.append(candidate)
            unassigned.remove(candidate)
        pods.append(pod)
    return normalize_layout(pods)
