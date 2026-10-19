import random
import unittest
from collections import Counter

from synthetic_data import (
    base_community_labels,
    build_initial_layout,
    drift_by_pair_swaps,
    generate_gradual_orders,
    generate_orders,
)


LENGTH_PROBS = {2: 0.45, 3: 0.40, 4: 0.15}


class SyntheticDataTests(unittest.TestCase):
    def test_drift_preserves_community_sizes_and_is_reproducible(self) -> None:
        old = base_community_labels(30, 10)
        new_a, ratio_a = drift_by_pair_swaps(old, 0.30, random.Random(77))
        new_b, ratio_b = drift_by_pair_swaps(old, 0.30, random.Random(77))
        self.assertEqual(new_a, new_b)
        self.assertEqual(ratio_a, ratio_b)
        self.assertEqual(Counter(old.values()), Counter(new_a.values()))
        self.assertEqual(sum(old[sku] != new_a[sku] for sku in old), 9)
        self.assertEqual(ratio_a, 0.30)

    def test_windows_are_reproducible_from_their_own_seed(self) -> None:
        labels = base_community_labels(30, 10)
        first = generate_orders(20, labels, random.Random(101), LENGTH_PROBS, 0.8)
        second = generate_orders(20, labels, random.Random(101), LENGTH_PROBS, 0.8)
        other = generate_orders(20, labels, random.Random(102), LENGTH_PROBS, 0.8)
        self.assertEqual(first, second)
        self.assertNotEqual(first, other)

    def test_gradual_orders_have_unique_ids_and_valid_lengths(self) -> None:
        old = base_community_labels(30, 10)
        new, _ = drift_by_pair_swaps(old, 0.30, random.Random(5))
        orders = generate_gradual_orders(
            200, old, new, random.Random(6), LENGTH_PROBS, 0.8
        )
        self.assertEqual(len({order.order_id for order in orders}), 200)
        self.assertTrue(all(len(order.skus) in {2, 3, 4} for order in orders))

    def test_initial_layout_uses_every_sku_once(self) -> None:
        labels = base_community_labels(30, 10)
        orders = generate_orders(400, labels, random.Random(8), LENGTH_PROBS, 0.8)
        layout = build_initial_layout(orders, 30, 10, 3)
        self.assertEqual(sorted(sku for pod in layout for sku in pod), list(range(1, 31)))
        self.assertTrue(all(len(pod) == 3 for pod in layout))


if __name__ == "__main__":
    unittest.main(verbosity=2)
