"""Pure statistics for the locked 100 paired seeds, with no global side effects."""

from __future__ import annotations

import json
import math
import statistics

import numpy as np
import pandas as pd

from experiment import SEEDS, STRATEGIES
from io_utils import compare

T99 = 1.9842169515086827
EPS = 1e-12
DETAIL_KEYS = ["seed", "scenario", "budget_k", "lambda", "strategy"]


def validate_detail(
    frame: pd.DataFrame, sensitivity: bool = False, seeds: tuple[int, ...] = SEEDS
) -> None:
    """Check the complete Cartesian grid and the scientific identities before analysis."""
    extra = ["changed_skus"] if sensitivity else []
    scenarios = {"abrupt", "gradual"} if sensitivity else {"no_drift", "abrupt", "gradual"}
    keys = extra + DETAIL_KEYS
    expected = len(seeds) * len(scenarios) * 3 * 5 * 5 * (3 if sensitivity else 1)
    if len(frame) != expected or frame.duplicated(keys).any():
        raise ValueError("Incomplete or duplicated detail grid")
    for field, values in [
        ("seed", set(seeds)),
        ("scenario", scenarios),
        ("budget_k", {1, 3, 5}),
        ("lambda", {0, 0.25, 0.5, 1, 2}),
        ("strategy", set(STRATEGIES)),
    ]:
        if set(frame[field]) != values:
            raise ValueError(f"Unexpected {field} grid")
    if sensitivity:
        if set(frame.changed_skus) != {5, 9, 13} or not np.allclose(
            frame.drift_ratio,
            frame.changed_skus / 30,
            rtol=0,
            atol=EPS,
        ):
            raise ValueError("Incorrect realized sensitivity intensity")
    else:
        ratios = np.where(frame.scenario.eq("no_drift"), 0, 0.3)
        for field in ("target_drift_ratio", "realized_drift_ratio"):
            if not np.allclose(frame[field], ratios, rtol=0, atol=EPS):
                raise ValueError("Incorrect main drift intensity")
    numeric = frame[["pv_test", "movement", "total_cost", "n_swaps"]].to_numpy(dtype=float)
    if not np.isfinite(numeric).all() or (numeric < 0).any():
        raise ValueError("Non-finite or negative scientific metric")
    if not (frame[["pv_test", "movement", "n_swaps"]] % 1 == 0).all().all():
        raise ValueError("PV, movement and swap counts must be integers")
    budgeted = frame.strategy.isin(["B1", "B2", "M"])
    if not (frame.loc[budgeted, "n_swaps"] <= frame.loc[budgeted, "budget_k"]).all():
        raise ValueError("Swap budget exceeded")
    if not frame.loc[frame.strategy.eq("B0"), "n_swaps"].eq(0).all():
        raise ValueError("B0 performed a swap")
    if not frame.movement.eq(2 * frame.n_swaps).all() or not np.allclose(
        frame.total_cost,
        frame.pv_test + frame["lambda"] * frame.movement,
        rtol=1e-12,
        atol=1e-10,
    ):
        raise ValueError("Movement or TC identity failed")
    if not frame.groupby("seed").initial_fingerprint.nunique().eq(1).all():
        raise ValueError("Initial data differ across scenarios/intensities")
    if not frame.groupby(extra + ["seed", "scenario"]).instance_fingerprint.nunique().eq(1).all():
        raise ValueError("Strategies do not share the same instance")
    for row in frame.to_dict("records"):
        layout, path = json.loads(row["final_layout"]), json.loads(row["swap_sequence"])
        if (
            len(layout) != 10
            or any(len(pod) != 3 for pod in layout)
            or sorted(s for pod in layout for s in pod) != list(range(1, 31))
        ):
            raise ValueError("Invalid final layout capacity/SKU assignment")
        if len(path) != row["n_swaps"] or any(
            len(pair) != 2 or pair[0] >= pair[1] for pair in path
        ):
            raise ValueError("Invalid swap sequence")
        first = "" if not path else f"{path[0][0]}-{path[0][1]}"
        if row["first_swap"] != first:
            raise ValueError("First swap disagrees with path")


def validate_middle(main: pd.DataFrame, sensitivity: pd.DataFrame) -> None:
    left = main[main.scenario.isin(["abrupt", "gradual"])].drop(
        columns=["target_drift_ratio", "realized_drift_ratio"]
    )
    right = sensitivity[sensitivity.changed_skus.eq(9)].drop(
        columns=["changed_skus", "drift_ratio"]
    )
    compare(left.to_dict("records"), right.to_dict("records"), DETAIL_KEYS)


def stats(values, prefix="m") -> dict:
    values = list(map(float, values))
    if len(values) != 100 or not all(math.isfinite(x) for x in values):
        raise ValueError("Expected 100 finite paired observations")
    mean, sd = statistics.mean(values), statistics.stdev(values)
    half = T99 * sd / 10
    return {
        "n_pairs": 100,
        "df": 99,
        "mean_difference": mean,
        "sd_difference": sd,
        "ci95_low": mean - half,
        "ci95_high": mean + half,
        f"{prefix}_wins": sum(x < -EPS for x in values),
        "ties": sum(abs(x) <= EPS for x in values),
        f"{prefix}_losses": sum(x > EPS for x in values),
    }


def summary(frame, extra):
    rows = []
    group = extra + ["scenario", "budget_k", "lambda", "strategy"]
    for key, data in frame.groupby(group, sort=True):
        row = dict(zip(group, key), n=100, df=99)
        for column, prefix in [
            ("pv_test", "pv"),
            ("total_cost", "tc"),
            ("n_swaps", "swaps"),
            ("movement", "movement"),
        ]:
            values = stats(data[column])
            for suffix, field in [
                ("mean", "mean_difference"),
                ("sd", "sd_difference"),
                ("ci95_low", "ci95_low"),
                ("ci95_high", "ci95_high"),
            ]:
                row[f"{prefix}_{suffix}"] = values[field]
        if extra:
            row["drift_ratio"] = row["changed_skus"] / 30
        rows.append(row)
    return pd.DataFrame(rows)


def contrasts(frame, extra, kind="paired"):
    rows = []
    group = (
        extra + ["scenario", "budget_k", "lambda"]
        if kind == "paired"
        else extra + ["scenario", "lambda"]
    )
    source = frame if kind == "paired" else frame[frame.strategy.eq("M")]
    for key, data in source.groupby(group):
        for metric, column in [("PV", "pv_test"), ("TC", "total_cost")]:
            wide = data.pivot(
                index="seed", columns="strategy" if kind == "paired" else "budget_k", values=column
            ).reindex(SEEDS)
            choices = (
                [("M", baseline) for baseline in ("B0", "B1", "B2", "B3")]
                if kind == "paired"
                else [(3, 1), (5, 3)]
            )
            for left, right in choices:
                row = dict(zip(group, key), metric=metric)
                if kind == "paired":
                    row.update(
                        comparator=right, difference_definition=f"M_{metric}-{right}_{metric}"
                    )
                    prefix = "m"
                else:
                    row.update(
                        lower_budget=right,
                        higher_budget=left,
                        difference_definition=f"M_K{left}_{metric}-M_K{right}_{metric}",
                    )
                    prefix = "higher_budget"
                if extra:
                    row["drift_ratio"] = row["changed_skus"] / 30
                row.update(stats(wide[left] - wide[right], prefix))
                rows.append(row)
    return pd.DataFrame(rows)


def intensity(frame, gap=False):
    rows = []
    group = ["scenario", "budget_k", "lambda"]
    for key, data in frame.groupby(group):
        metrics = [("PV", "pv_test"), ("TC", "total_cost")]
        if not gap:
            metrics.append(("swaps", "n_swaps"))
        for metric, column in metrics:
            if gap:
                by_strategy = data.pivot(
                    index=["seed", "changed_skus"], columns="strategy", values=column
                )
                wide = (by_strategy.M - by_strategy.B2).unstack("changed_skus").reindex(SEEDS)
            else:
                wide = (
                    data[data.strategy.eq("M")]
                    .pivot(index="seed", columns="changed_skus", values=column)
                    .reindex(SEEDS)
                )
            for low, high in [(5, 9), (9, 13)]:
                row = dict(
                    zip(group, key),
                    lower_changed_skus=low,
                    higher_changed_skus=high,
                    metric=metric,
                    difference_definition=f'({"M-B2" if gap else "M"})_{high}-{low}_{metric}',
                )
                # Keep legacy field names to match archived tables; negative favors higher intensity.
                row.update(stats(wide[high] - wide[low], "lower"))
                rows.append(row)
    return pd.DataFrame(rows)


def build_tables(main, sensitivity):
    tables = {}
    for prefix, frame, extra in [("", main, []), ("sensitivity_", sensitivity, ["changed_skus"])]:
        for name, result in [
            ("strategy_summary", summary(frame, extra)),
            ("paired_comparisons", contrasts(frame, extra)),
            ("budget_effects", contrasts(frame, extra, "budget")),
        ]:
            tables[f"{prefix}{name}_100seeds.csv"] = result
    tables["sensitivity_intensity_effects_100seeds.csv"] = intensity(sensitivity)
    tables["sensitivity_gap_effects_100seeds.csv"] = intensity(sensitivity, gap=True)
    return tables


def table_keys(name):
    extra = ["changed_skus"] if name.startswith("sensitivity_") else []
    if "strategy_summary" in name:
        return extra + ["scenario", "budget_k", "lambda", "strategy"]
    if "paired_comparisons" in name:
        return extra + ["scenario", "budget_k", "lambda", "comparator", "metric"]
    if "budget_effects" in name:
        return extra + ["scenario", "lambda", "lower_budget", "higher_budget", "metric"]
    return ["scenario", "budget_k", "lambda", "lower_changed_skus", "higher_changed_skus", "metric"]
