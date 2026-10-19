"""Independent evaluator checks and regressions for the new reproduction layer."""

import argparse
import inspect
import json
import random
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from analysis import stats, validate_detail
from experiment import ROOT, expand, search
from instances import build_instances_for_seed, load_config
from io_utils import compare, read_rows
from reproduce import execute_unit, output_directory
from rmfs_core import Order, batch_orders, select_budgeted_batching_aware


def reference_batching(orders, layout, capacity):
    """Readable set-based oracle, independent of the bit-mask implementation."""
    location = {sku: index for index, pod in enumerate(layout) for sku in pod}
    pods = {order.order_id: {location[sku] for sku in order.skus} for order in orders}
    remaining = {order.order_id for order in orders}
    batches, visits = [], 0
    while remaining:
        first = sorted(remaining, key=lambda order: (-len(pods[order]), order))[0]
        selected, union = [first], set(pods[first])
        remaining.remove(first)
        while remaining and len(selected) < capacity:
            candidate = sorted(remaining, key=lambda order: (len(pods[order] - union), order))[0]
            selected.append(candidate)
            union.update(pods[candidate])
            remaining.remove(candidate)
        batches.append(tuple(selected))
        visits += len(union)
    return visits, tuple(batches)


class ReproductionTests(unittest.TestCase):
    def test_evaluator_against_independent_oracle(self):
        rng = random.Random(314159)
        for case in range(250):
            skus = list(range(1, 13))
            rng.shuffle(skus)
            layout = tuple(tuple(sorted(skus[i : i + 3])) for i in range(0, 12, 3))
            ids = rng.sample(range(1, 1000), rng.randrange(0, 25))
            orders = tuple(Order(i, tuple(rng.sample(skus, rng.randint(1, 6)))) for i in ids)
            capacity = rng.randint(1, 8)
            with self.subTest(case=case):
                expected_visits, expected_batches = reference_batching(orders, layout, capacity)
                actual = batch_orders(orders, layout, capacity)
                self.assertEqual(
                    (actual.pod_visits, actual.batches), (expected_visits, expected_batches)
                )

    def test_cached_expansion_matches_archived_scientific_rows(self):
        seed = 2026092401
        for count in (5, 9, 13):
            payload = json.loads(
                (ROOT / f"reference/checkpoints/seed_{seed}_changed_{count}.json").read_text()
            )
            rows, _ = expand(seed, count, payload)
            name = "formal_detail_100seeds.csv" if count == 9 else "sensitivity_detail_100seeds.csv"
            expected = [
                row
                for row in read_rows(ROOT / "reference" / name)
                if int(row["seed"]) == seed and (count == 9 or int(row["changed_skus"]) == count)
            ]
            keys = ([] if count == 9 else ["changed_skus"]) + [
                "seed",
                "scenario",
                "budget_k",
                "lambda",
                "strategy",
            ]
            self.assertEqual(compare(rows, expected, keys), 225 if count == 9 else 150)

    def test_lambda_and_budget_prefix_equal_direct_search(self):
        layout = ((1, 2), (3, 4), (5, 6), (7, 8))
        orders = tuple(
            Order(i + 1, pair)
            for i, pair in enumerate(
                [(1, 3), (1, 3), (2, 4), (2, 4), (5, 7), (5, 7), (6, 8), (6, 8)]
            )
        )
        full = select_budgeted_batching_aware(layout, orders, 2, None, 0, 16)
        for lam in (0, 0.25, 0.5, 1, 2, 4):
            retained = []
            for record in full.swaps:
                if record.marginal_gain - 2 * lam <= 1e-12:
                    break
                retained.append(record.sku_pair)
            for k in (0, 1, 3, 5):
                direct = select_budgeted_batching_aware(layout, orders, 2, k, lam, 16)
                self.assertEqual([r.sku_pair for r in direct.swaps], retained[:k])

    def test_missing_values_are_rejected_before_statistics(self):
        with self.assertRaises(ValueError):
            stats([0.0] * 99 + [float("nan")])
        with self.assertRaises(ValueError):
            compare(
                [{"seed": 1, "pv_test": float("nan")}],
                [{"seed": 1, "pv_test": float("nan")}],
                ["seed"],
            )

    def test_duplicate_records_are_rejected(self):
        rows = [{"seed": 1, "pv_test": 2}]
        with self.assertRaises(ValueError):
            compare(rows + rows, rows, ["seed"])

    def test_corrupted_resume_checkpoint_is_rejected(self):
        seed, count = 2026092401, 5
        path = ROOT / f"reference/checkpoints/seed_{seed}_changed_{count}.json"
        payload = json.loads(path.read_text())
        payload["scenarios"]["abrupt"]["B1"]["pairs"][0][0] = -1
        # No file is created or deleted: patch only the resumed checkpoint read.
        with patch.object(Path, "exists", return_value=True), patch.object(
            Path, "read_text", side_effect=[path.read_text(), json.dumps(payload)]
        ):
            with self.assertRaisesRegex(ValueError, "Search checkpoint mismatch"):
                execute_unit(seed, count, "fresh", ROOT / "results/test", True)

    def test_selection_functions_do_not_accept_test_orders(self):
        self.assertNotIn(
            "test_orders", inspect.signature(select_budgeted_batching_aware).parameters
        )
        instance = build_instances_for_seed(99, load_config(ROOT / "protocol_config.json"), 0.3)[
            "gradual"
        ]
        self.assertNotIn("labels", instance.__dataclass_fields__)

    def test_protected_reference_output_is_rejected(self):
        args = argparse.Namespace(
            output=ROOT / "reference/new", resume=False, mode="verify", scope="all"
        )
        with self.assertRaisesRegex(ValueError, "protected"):
            output_directory(args)


if __name__ == "__main__":
    unittest.main()
