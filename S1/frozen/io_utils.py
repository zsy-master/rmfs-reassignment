"""Small I/O and strict reference-comparison helpers."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

ABS_TOL = 1e-10
REL_TOL = 1e-12
NUMERIC_FIELDS = {
    "seed",
    "changed_skus",
    "budget_k",
    "lambda",
    "lower_budget",
    "higher_budget",
    "lower_changed_skus",
    "higher_changed_skus",
    "target_drift_ratio",
    "realized_drift_ratio",
    "drift_ratio",
    "n_swaps",
    "pv_test",
    "movement",
    "total_cost",
    "n",
    "df",
    "n_pairs",
    "mean_difference",
    "sd_difference",
    "ci95_low",
    "ci95_high",
    "m_wins",
    "m_losses",
    "ties",
    "lower_wins",
    "lower_losses",
    "higher_budget_wins",
    "higher_budget_losses",
} | {
    f"{prefix}_{suffix}"
    for prefix in ("pv", "tc", "swaps", "movement")
    for suffix in ("mean", "sd", "ci95_low", "ci95_high")
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_rows(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"Empty output: {path}")
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def save_json(path: Path, value) -> None:
    # Atomic replacement prevents interrupted writes from creating valid-looking checkpoints.
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def compare(actual: list[dict], expected: list[dict], keys: list[str]) -> int:
    """Exact discrete/text comparison; finite numeric fields use explicit tolerances."""

    def index(rows):
        result = {}
        for row in rows:
            key = tuple(str(float(row[k])) if k in NUMERIC_FIELDS else str(row[k]) for k in keys)
            if key in result:
                raise ValueError(f"Duplicate record key: {key}")
            result[key] = row
        return result

    left, right = index(actual), index(expected)
    if left.keys() != right.keys():
        raise ValueError(f"Record keys differ: {len(left)} versus {len(right)}")
    for key, a in left.items():
        b = right[key]
        columns = {c for c in a if "runtime" not in c}
        if columns != {c for c in b if "runtime" not in c}:
            raise ValueError(f"Columns differ: {key}")
        for column in columns:
            x, y = a[column], b[column]
            if column in NUMERIC_FIELDS:
                x, y = float(x), float(y)
                equal = (
                    math.isfinite(x)
                    and math.isfinite(y)
                    and math.isclose(
                        x,
                        y,
                        rel_tol=REL_TOL,
                        abs_tol=ABS_TOL,
                    )
                )
            else:
                equal = str(x) == str(y)
            if not equal:
                raise ValueError(f"Mismatch: {key}, {column}, {x!r} != {y!r}")
    return len(left)
