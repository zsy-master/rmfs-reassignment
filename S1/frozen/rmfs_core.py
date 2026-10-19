"""Protocol-locked core functions for the RMFS synthetic experiment.

Selection functions in this module intentionally accept decision-window orders only.
Test-window orders are accepted only by ``evaluate_layout``.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import isclose
from random import Random
from typing import Iterable, Mapping, Sequence


EPS = 1e-12
Layout = tuple[tuple[int, ...], ...]


@dataclass(frozen=True, order=True)
class Order:
    order_id: int
    skus: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.skus:
            raise ValueError("An order must contain at least one SKU.")
        if len(set(self.skus)) != len(self.skus):
            raise ValueError("An order cannot contain duplicate SKUs.")
        object.__setattr__(self, "skus", tuple(sorted(self.skus)))


@dataclass(frozen=True)
class SwapRecord:
    step: int
    sku_pair: tuple[int, int]
    value_before: float
    value_after: float
    marginal_gain: float
    score: float


@dataclass(frozen=True)
class SelectionResult:
    layout: Layout
    swaps: tuple[SwapRecord, ...]


@dataclass(frozen=True)
class BatchEvaluation:
    pod_visits: int
    batches: tuple[tuple[int, ...], ...]


def normalize_layout(layout: Iterable[Iterable[int]]) -> Layout:
    normalized = tuple(tuple(sorted(pod)) for pod in layout)
    validate_layout(normalized)
    return normalized


def validate_layout(layout: Layout) -> None:
    if not layout:
        raise ValueError("Layout must contain at least one pod.")
    capacities = {len(pod) for pod in layout}
    if len(capacities) != 1 or 0 in capacities:
        raise ValueError("All pods must have the same positive capacity.")
    flattened = [sku for pod in layout for sku in pod]
    if len(flattened) != len(set(flattened)):
        raise ValueError("Each SKU must belong to exactly one pod.")


def sku_to_pod(layout: Layout) -> dict[int, int]:
    validate_layout(layout)
    return {sku: pod_id for pod_id, pod in enumerate(layout) for sku in pod}


def _order_pods(order: Order, mapping: Mapping[int, int]) -> frozenset[int]:
    try:
        return frozenset(mapping[sku] for sku in order.skus)
    except KeyError as exc:
        raise ValueError(f"Order contains SKU absent from layout: {exc.args[0]}") from exc


def _order_pod_mask(order: Order, mapping: Mapping[int, int]) -> int:
    mask = 0
    try:
        for sku in order.skus:
            mask |= 1 << mapping[sku]
    except KeyError as exc:
        raise ValueError(f"Order contains SKU absent from layout: {exc.args[0]}") from exc
    return mask


def batch_orders(
    orders: Sequence[Order], layout: Layout, batch_capacity: int
) -> BatchEvaluation:
    """Apply the deterministic batching rule locked in the protocol."""
    if batch_capacity <= 0:
        raise ValueError("batch_capacity must be positive.")
    if len({order.order_id for order in orders}) != len(orders):
        raise ValueError("Order IDs must be unique within a window.")

    mapping = sku_to_pod(layout)
    remaining = list(orders)
    masks_by_order = {order.order_id: _order_pod_mask(order, mapping) for order in orders}
    batches: list[tuple[int, ...]] = []
    total_visits = 0

    while remaining:
        seed = min(
            remaining,
            key=lambda order: (-masks_by_order[order.order_id].bit_count(), order.order_id),
        )
        remaining.remove(seed)
        selected = [seed]
        batch_mask = masks_by_order[seed.order_id]

        while remaining and len(selected) < batch_capacity:
            candidate = min(
                remaining,
                key=lambda order: (
                    (masks_by_order[order.order_id] & ~batch_mask).bit_count(),
                    order.order_id,
                ),
            )
            remaining.remove(candidate)
            selected.append(candidate)
            batch_mask |= masks_by_order[candidate.order_id]

        batches.append(tuple(order.order_id for order in selected))
        total_visits += batch_mask.bit_count()

    return BatchEvaluation(total_visits, tuple(batches))


def enumerate_cross_pod_swaps(layout: Layout) -> tuple[tuple[int, int], ...]:
    pairs: set[tuple[int, int]] = set()
    for left_pod, right_pod in combinations(layout, 2):
        for left_sku in left_pod:
            for right_sku in right_pod:
                pairs.add(tuple(sorted((left_sku, right_sku))))
    return tuple(sorted(pairs))


def apply_swap(layout: Layout, sku_pair: tuple[int, int]) -> Layout:
    left_sku, right_sku = tuple(sorted(sku_pair))
    mapping = sku_to_pod(layout)
    if left_sku not in mapping or right_sku not in mapping:
        raise ValueError("Both swap SKUs must be present in the layout.")
    left_pod = mapping[left_sku]
    right_pod = mapping[right_sku]
    if left_pod == right_pod:
        raise ValueError("A feasible swap requires SKUs from different pods.")

    mutable = [list(pod) for pod in layout]
    mutable[left_pod].remove(left_sku)
    mutable[right_pod].remove(right_sku)
    mutable[left_pod].append(right_sku)
    mutable[right_pod].append(left_sku)
    return normalize_layout(mutable)


def _is_better(
    value: float,
    pair: tuple[int, int],
    best_value: float | None,
    best_pair: tuple[int, int] | None,
) -> bool:
    if best_value is None or value > best_value + EPS:
        return True
    return isclose(value, best_value, abs_tol=EPS) and (
        best_pair is None or pair < best_pair
    )


def select_budgeted_batching_aware(
    layout: Layout,
    decision_orders: Sequence[Order],
    batch_capacity: int,
    max_swaps: int | None,
    lambda_cost: float,
    future_horizon: int,
) -> SelectionResult:
    """Select SKU swaps using decision data only.

    ``max_swaps=None`` implements the protocol's unbudgeted B3 strategy.
    """
    if max_swaps is not None and max_swaps < 0:
        raise ValueError("max_swaps must be nonnegative or None.")
    if lambda_cost < 0:
        raise ValueError("lambda_cost must be nonnegative.")
    if not decision_orders or future_horizon <= 0:
        raise ValueError("Decision and future horizons must be positive.")

    current = normalize_layout(layout)
    current_pv = batch_orders(decision_orders, current, batch_capacity).pod_visits
    horizon_scale = future_horizon / len(decision_orders)
    records: list[SwapRecord] = []

    while max_swaps is None or len(records) < max_swaps:
        best_pair: tuple[int, int] | None = None
        best_layout: Layout | None = None
        best_pv: int | None = None
        best_gain: float | None = None
        best_score: float | None = None

        for pair in enumerate_cross_pod_swaps(current):
            candidate_layout = apply_swap(current, pair)
            candidate_pv = batch_orders(
                decision_orders, candidate_layout, batch_capacity
            ).pod_visits
            predicted_gain = (current_pv - candidate_pv) * horizon_scale
            score = predicted_gain - 2.0 * lambda_cost
            if _is_better(score, pair, best_score, best_pair):
                best_pair = pair
                best_layout = candidate_layout
                best_pv = candidate_pv
                best_gain = predicted_gain
                best_score = score

        if best_score is None or best_score <= EPS:
            break

        assert best_pair is not None
        assert best_layout is not None
        assert best_pv is not None
        assert best_gain is not None
        records.append(
            SwapRecord(
                step=len(records) + 1,
                sku_pair=best_pair,
                value_before=float(current_pv),
                value_after=float(best_pv),
                marginal_gain=best_gain,
                score=best_score,
            )
        )
        current = best_layout
        current_pv = best_pv

    return SelectionResult(current, tuple(records))


def jaccard_matrix(orders: Sequence[Order], skus: Iterable[int]) -> dict[tuple[int, int], float]:
    sku_list = sorted(set(skus))
    occurrence = {sku: 0 for sku in sku_list}
    cooccurrence = {pair: 0 for pair in combinations(sku_list, 2)}
    for order in orders:
        present = set(order.skus)
        for sku in present:
            if sku in occurrence:
                occurrence[sku] += 1
        for pair in combinations(sorted(present & set(sku_list)), 2):
            cooccurrence[pair] += 1

    result: dict[tuple[int, int], float] = {}
    for pair, joint in cooccurrence.items():
        denominator = occurrence[pair[0]] + occurrence[pair[1]] - joint
        result[pair] = 0.0 if denominator == 0 else joint / denominator
    return result


def layout_association_score(
    layout: Layout, similarities: Mapping[tuple[int, int], float]
) -> float:
    return sum(
        similarities.get(tuple(sorted(pair)), 0.0)
        for pod in layout
        for pair in combinations(pod, 2)
    )


def select_association_greedy(
    layout: Layout,
    decision_orders: Sequence[Order],
    max_swaps: int,
) -> SelectionResult:
    """B2: at most K swaps, strict positive gain, lexicographic tie-break."""
    if max_swaps < 0:
        raise ValueError("max_swaps must be nonnegative.")
    current = normalize_layout(layout)
    all_skus = [sku for pod in current for sku in pod]
    similarities = jaccard_matrix(decision_orders, all_skus)
    current_score = layout_association_score(current, similarities)
    records: list[SwapRecord] = []

    while len(records) < max_swaps:
        best_pair: tuple[int, int] | None = None
        best_layout: Layout | None = None
        best_after: float | None = None
        best_gain: float | None = None
        for pair in enumerate_cross_pod_swaps(current):
            candidate_layout = apply_swap(current, pair)
            candidate_score = layout_association_score(candidate_layout, similarities)
            gain = candidate_score - current_score
            if _is_better(gain, pair, best_gain, best_pair):
                best_pair = pair
                best_layout = candidate_layout
                best_after = candidate_score
                best_gain = gain

        if best_gain is None or best_gain <= EPS:
            break

        assert best_pair is not None
        assert best_layout is not None
        assert best_after is not None
        records.append(
            SwapRecord(
                step=len(records) + 1,
                sku_pair=best_pair,
                value_before=current_score,
                value_after=best_after,
                marginal_gain=best_gain,
                score=best_gain,
            )
        )
        current = best_layout
        current_score = best_after

    return SelectionResult(current, tuple(records))


def select_random_swaps(layout: Layout, max_swaps: int, seed: int) -> SelectionResult:
    """B1: make at most K random feasible swaps while avoiding repeated layouts."""
    if max_swaps < 0:
        raise ValueError("max_swaps must be nonnegative.")
    rng = Random(seed)
    current = normalize_layout(layout)
    visited = {current}
    records: list[SwapRecord] = []
    while len(records) < max_swaps:
        candidates = [
            (pair, apply_swap(current, pair))
            for pair in enumerate_cross_pod_swaps(current)
        ]
        candidates = [(pair, candidate) for pair, candidate in candidates if candidate not in visited]
        if not candidates:
            break
        pair, candidate = rng.choice(candidates)
        records.append(
            SwapRecord(
                step=len(records) + 1,
                sku_pair=pair,
                value_before=float("nan"),
                value_after=float("nan"),
                marginal_gain=float("nan"),
                score=float("nan"),
            )
        )
        current = candidate
        visited.add(current)
    return SelectionResult(current, tuple(records))


def evaluate_layout(
    layout: Layout,
    test_orders: Sequence[Order],
    batch_capacity: int,
    lambda_cost: float,
    number_of_swaps: int,
) -> dict[str, float]:
    """Evaluate a frozen layout on test data; no selection occurs here."""
    pv_test = batch_orders(test_orders, layout, batch_capacity).pod_visits
    movement = 2 * number_of_swaps
    return {
        "pv_test": float(pv_test),
        "movement": float(movement),
        "total_cost": float(pv_test + lambda_cost * movement),
    }
