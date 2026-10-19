import inspect
import unittest

from rmfs_core import (
    Order,
    batch_orders,
    evaluate_layout,
    layout_association_score,
    jaccard_matrix,
    select_association_greedy,
    select_budgeted_batching_aware,
    validate_layout,
)


class ProtocolLockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.layout = ((1, 2), (3, 4), (5, 6), (7, 8))
        sku_rows = [
            (1, 3),
            (1, 3),
            (2, 4),
            (2, 4),
            (5, 6),
            (5, 6),
            (7, 8),
            (7, 8),
        ]
        self.decision_orders = tuple(
            Order(index, skus) for index, skus in enumerate(sku_rows, start=1)
        )

    def test_hand_example_pod_visits(self) -> None:
        before = batch_orders(self.decision_orders, self.layout, 2)
        self.assertEqual(before.pod_visits, 6)
        self.assertEqual(before.batches, ((1, 2), (3, 4), (5, 6), (7, 8)))

    def test_main_method_tie_break_and_lambda(self) -> None:
        selected = select_budgeted_batching_aware(
            self.layout,
            self.decision_orders,
            batch_capacity=2,
            max_swaps=1,
            lambda_cost=1,
            future_horizon=16,
        )
        self.assertEqual(len(selected.swaps), 1)
        self.assertEqual(selected.swaps[0].sku_pair, (1, 4))
        self.assertEqual(selected.swaps[0].marginal_gain, 4)
        self.assertEqual(selected.swaps[0].score, 2)
        self.assertEqual(batch_orders(self.decision_orders, selected.layout, 2).pod_visits, 4)

        stopped = select_budgeted_batching_aware(
            self.layout,
            self.decision_orders,
            batch_capacity=2,
            max_swaps=5,
            lambda_cost=2,
            future_horizon=16,
        )
        self.assertEqual(stopped.layout, self.layout)
        self.assertEqual(len(stopped.swaps), 0)

    def test_b2_tie_break_at_most_k_and_early_stop(self) -> None:
        selected = select_association_greedy(
            self.layout, self.decision_orders, max_swaps=5
        )
        self.assertEqual(len(selected.swaps), 1)
        self.assertEqual(selected.swaps[0].sku_pair, (1, 4))
        similarities = jaccard_matrix(self.decision_orders, range(1, 9))
        self.assertEqual(layout_association_score(self.layout, similarities), 2)
        self.assertEqual(layout_association_score(selected.layout, similarities), 4)

    def test_budget_is_a_maximum(self) -> None:
        zero = select_budgeted_batching_aware(
            self.layout, self.decision_orders, 2, 0, 0, 16
        )
        one = select_budgeted_batching_aware(
            self.layout, self.decision_orders, 2, 1, 0, 16
        )
        self.assertEqual(len(zero.swaps), 0)
        self.assertLessEqual(len(one.swaps), 1)

    def test_test_data_is_absent_from_selection_interfaces(self) -> None:
        main_parameters = inspect.signature(select_budgeted_batching_aware).parameters
        b2_parameters = inspect.signature(select_association_greedy).parameters
        self.assertNotIn("test_orders", main_parameters)
        self.assertNotIn("test_orders", b2_parameters)
        self.assertIn("test_orders", inspect.signature(evaluate_layout).parameters)

    def test_capacity_and_unique_assignment_are_preserved(self) -> None:
        selected = select_budgeted_batching_aware(
            self.layout, self.decision_orders, 2, 3, 0, 16
        )
        validate_layout(selected.layout)
        self.assertTrue(all(len(pod) == 2 for pod in selected.layout))
        self.assertEqual(
            sorted(sku for pod in selected.layout for sku in pod), list(range(1, 9))
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
