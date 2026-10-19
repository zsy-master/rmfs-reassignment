"""Portable, isolated reproduction of the final 100-seed RMFS experiment."""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from experiment import ROOT, SEEDS, COUNTS, expand, middle_intensity, search
from io_utils import compare, read_rows, save_json, sha256, write_rows

REFERENCE = ROOT / "reference"
DETAIL_KEYS = ["seed", "scenario", "budget_k", "lambda", "strategy"]


def check_assets() -> dict:
    checked = {}
    for name in ("reference/ASSET_HASHES.json", "CODE_HASHES.json"):
        lock = json.loads((ROOT / name).read_text(encoding="utf-8"))
        for relative, expected in lock.items():
            path = ROOT / relative
            if not path.is_file() or sha256(path) != expected:
                raise ValueError(f"Hash mismatch or missing file: {relative}")
        checked[name] = len(lock)
    return checked


def scientific_payload(value):
    if isinstance(value, dict):
        return {k: scientific_payload(v) for k, v in value.items() if "runtime" not in k}
    if isinstance(value, list):
        return [scientific_payload(v) for v in value]
    return value


def execute_unit(seed, count, mode, output, resume):
    directory = Path(output) / "checkpoints"
    path = directory / f"seed_{seed}_changed_{count}.json"
    expected = json.loads((REFERENCE / "checkpoints" / path.name).read_text(encoding="utf-8"))
    reused = resume and path.exists()
    if reused:
        payload = json.loads(path.read_text(encoding="utf-8"))
    elif mode == "replay":
        payload = expected
    else:
        payload = search(seed, count)
    # Compare the whole path (including iterations beyond K=5) and all decision gains.
    if scientific_payload(payload) != scientific_payload(expected):
        raise ValueError(f"Search checkpoint mismatch: seed={seed}, changed_skus={count}")
    if not reused:
        save_json(path, payload)
    detail, paths = expand(seed, count, payload)
    return seed, count, detail, paths, reused


def frames_from_rows(main, sensitivity, seeds):
    import pandas as pd
    from analysis import validate_detail, validate_middle

    frames = []
    for rows, is_sensitivity in [(main, False), (sensitivity, True)]:
        frame = pd.DataFrame(rows)
        numeric = ["seed", "budget_k", "lambda", "n_swaps", "pv_test", "movement", "total_cost"]
        numeric += (
            ["changed_skus", "drift_ratio"]
            if is_sensitivity
            else ["target_drift_ratio", "realized_drift_ratio"]
        )
        for field in numeric:
            frame[field] = pd.to_numeric(frame[field], errors="raise")
        validate_detail(frame, is_sensitivity, seeds)
        frames.append(frame)
    validate_middle(*frames)
    return frames


def analyze(output, frames, figures):
    from analysis import build_tables, table_keys

    comparisons = {}
    for name, table in build_tables(*frames).items():
        actual, expected = table.to_dict("records"), read_rows(REFERENCE / name)
        comparisons[name] = compare(actual, expected, table_keys(name))
        table.to_csv(output / name, index=False, encoding="utf-8-sig")
    if figures:
        from figures import render_figures

        render_figures(output)
    return comparisons


def output_directory(args) -> Path:
    output = (
        args.output
        or ROOT / "results" / f"{args.mode}_{args.scope}_{datetime.now():%Y%m%d_%H%M%S_%f}"
    ).resolve()
    for protected in (ROOT, ROOT / "reference", ROOT / "tests", ROOT / "validation"):
        if output == protected or (protected != ROOT and protected in output.parents):
            raise ValueError(f"Output is in a protected directory: {output}")
    if args.resume:
        if args.output is None or not output.is_dir():
            raise ValueError("--resume requires an existing --output run directory")
    else:
        output.mkdir(parents=True, exist_ok=False)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["check", "verify", "replay", "fresh"])
    parser.add_argument("--scope", choices=["one", "all"], default="one")
    parser.add_argument("--seed", type=int, help="One locked seed; default 2026092401")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--figures", action="store_true")
    parser.add_argument("--output", type=Path, help="New run directory")
    parser.add_argument(
        "--resume", action="store_true", help="Reuse validated checkpoints from --output"
    )
    args = parser.parse_args()
    checked = check_assets()
    if args.mode == "check":
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "assets_checked": checked,
                    "python": platform.python_version(),
                    "searches_executed": 0,
                },
                indent=2,
            )
        )
        return
    if not 1 <= args.workers <= (os.cpu_count() or 1):
        parser.error("--workers must be between 1 and the available CPU count")
    if args.seed is not None and (args.seed not in SEEDS or args.scope != "one"):
        parser.error("--seed requires --scope one and a seed from 2026092401..2026092500")
    if args.resume and args.mode not in {"fresh", "replay"}:
        parser.error("--resume is supported for fresh/replay only")
    if args.figures and args.mode != "verify" and args.scope != "all":
        parser.error("--figures requires --scope all (or verify)")
    # Dependency checks occur before creating a directory or scheduling expensive work.
    import numpy
    import pandas

    if args.figures:
        import reportlab
        import pypdfium2
    seeds = SEEDS if args.scope == "all" or args.mode == "verify" else (args.seed or SEEDS[0],)
    signature = {
        "mode": args.mode,
        "seeds": list(seeds),
        "code_lock_sha256": sha256(ROOT / "CODE_HASHES.json"),
        "asset_lock_sha256": sha256(REFERENCE / "ASSET_HASHES.json"),
    }
    output = output_directory(args)
    manifest_path = output / "RUN_MANIFEST.json"
    if args.resume:
        old = json.loads(manifest_path.read_text(encoding="utf-8"))
        if any(old.get(k) != v for k, v in signature.items()):
            raise ValueError("Resume mode, seeds or source/assets differ from the recorded run")
    manifest = {
        **signature,
        "status": "RUNNING",
        "workers": args.workers,
        "started_local": datetime.now().isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "dependencies": {"numpy": numpy.__version__, "pandas": pandas.__version__},
        "completed_units": 0,
        "resume": args.resume,
    }
    save_json(manifest_path, manifest)
    print(f"Output: {output}", flush=True)
    try:
        main_rows, sensitivity_rows, main_paths, sensitivity_paths = [], [], [], []
        reused_units = completed = 0
        if args.mode == "verify":
            main_rows = read_rows(REFERENCE / "formal_detail_100seeds.csv")
            sensitivity_rows = read_rows(REFERENCE / "sensitivity_detail_100seeds.csv")
        else:
            units = [(seed, count) for seed in seeds for count in COUNTS]
            (output / "checkpoints").mkdir(exist_ok=True)
            print(f"Mode={args.mode}; units={len(units)}; workers={args.workers}", flush=True)
            with ProcessPoolExecutor(max_workers=args.workers) as pool:
                futures = [
                    pool.submit(execute_unit, seed, count, args.mode, str(output), args.resume)
                    for seed, count in units
                ]
                for future in as_completed(futures):
                    try:
                        seed, count, rows, paths, reused = future.result()
                    except BaseException:
                        for pending in futures:
                            pending.cancel()
                        raise
                    if count == 9:
                        main_rows.extend(rows)
                        main_paths.extend(paths)
                        sensitivity_rows.extend(middle_intensity(rows))
                        sensitivity_paths.extend(middle_intensity(paths))
                    else:
                        sensitivity_rows.extend(rows)
                        sensitivity_paths.extend(paths)
                    completed += 1
                    reused_units += int(reused)
                    manifest.update(completed_units=completed, reused_checkpoint_units=reused_units)
                    save_json(manifest_path, manifest)
                    print(
                        f"[{completed}/{len(units)}] seed={seed}, changed_skus={count}, reused={reused}",
                        flush=True,
                    )
            for rows in (main_rows, sensitivity_rows, main_paths, sensitivity_paths):
                rows.sort(
                    key=lambda r: (
                        r.get("changed_skus", 9),
                        r["seed"],
                        r["scenario"],
                        r.get("budget_k", 0),
                        r.get("lambda", 0),
                        r["strategy"],
                    )
                )
            suffix = "100seeds" if len(seeds) == 100 else "1seed"
            for name, rows in [
                (f"formal_detail_{suffix}.csv", main_rows),
                (f"sensitivity_detail_{suffix}.csv", sensitivity_rows),
                ("formal_search_paths.csv", main_paths),
                ("sensitivity_search_paths.csv", sensitivity_paths),
            ]:
                write_rows(output / name, rows)
        frames = frames_from_rows(main_rows, sensitivity_rows, seeds)
        comparisons = {}
        for name, rows, extra in [
            ("formal_detail_100seeds.csv", main_rows, []),
            ("sensitivity_detail_100seeds.csv", sensitivity_rows, ["changed_skus"]),
        ]:
            expected = [row for row in read_rows(REFERENCE / name) if int(row["seed"]) in seeds]
            comparisons[name] = compare(rows, expected, extra + DETAIL_KEYS)
        if len(seeds) == 100:
            comparisons.update(analyze(output, frames, args.figures))
        report = {
            "status": "PASS",
            "mode": args.mode,
            "seed_count": len(seeds),
            "main_rows": len(main_rows),
            "sensitivity_rows": len(sensitivity_rows),
            "reference_comparisons": comparisons,
            "checkpoint_units": completed,
            "new_search_units": completed - reused_units if args.mode == "fresh" else 0,
            "reused_checkpoint_units": reused_units,
            "CI_recomputed": len(seeds) == 100,
            "runtime_match_required": False,
            "figures_generated": args.figures,
        }
        save_json(output / "REPRODUCTION_REPORT.json", report)
        manifest.update(status="PASS", finished_local=datetime.now().isoformat())
        save_json(manifest_path, manifest)
        print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    except BaseException as error:
        manifest.update(status="FAIL", error=repr(error))
        save_json(manifest_path, manifest)
        raise


if __name__ == "__main__":
    main()
