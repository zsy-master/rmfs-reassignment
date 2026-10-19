"""Replay the original real-data pipeline with explicit input and isolated output."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from _common import OPTIONAL, load_legacy, new_output
from io_utils import compare, read_rows, save_json, sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True, help="Original online_retail_II.xlsx")
    parser.add_argument(
        "--output", type=Path, required=True, help="New non-existing output directory"
    )
    args = parser.parse_args()
    reference = OPTIONAL / "reference"
    recorded = json.loads((reference / "real_data_run_manifest.json").read_text(encoding="utf-8"))
    raw = args.raw.resolve()
    if not raw.is_file():
        parser.error(f"Workbook not found: {raw}")
    if sha256(raw) != recorded["cleaning"]["workbook_sha256"]:
        parser.error("Workbook SHA-256 differs from the recorded experiment")
    legacy = load_legacy("run_real_data_validation")
    output = new_output(args.output)
    legacy.HERE = output
    legacy.RAW_XLSX = raw
    shutil.copyfile(reference / "REAL_DATA_PROTOCOL.md", output / "REAL_DATA_PROTOCOL.md")
    save_json(output / "REPRODUCTION_REPORT.json", {"status": "RUNNING", "mode": "real_data"})
    try:
        legacy.main()
        current = json.loads((output / "real_data_run_manifest.json").read_text(encoding="utf-8"))
        if not current.get("go") or current.get("n_cases") != recorded["n_cases"]:
            raise ValueError("Real-data case count or GO decision differs from reference")
        if current["cleaning"] != recorded["cleaning"]:
            raise ValueError("Real-data cleaning counts differ from reference")
        comparisons = {}
        for name, keys in [
            ("real_data_cases.csv", ["case_id"]),
            ("real_data_results.csv", ["case_id", "strategy", "budget_k", "lambda"]),
            ("real_data_diagnostics.csv", ["case_id"]),
            ("real_data_m_vs_b2_summary.csv", ["budget_k", "lambda"]),
        ]:
            comparisons[name] = compare(read_rows(output / name), read_rows(reference / name), keys)
        report = {
            "status": "PASS",
            "mode": "real_data",
            "n_cases": current["n_cases"],
            "workbook_sha256": sha256(raw),
            "reference_comparisons": comparisons,
            "runtime_match_required": False,
        }
        save_json(output / "REPRODUCTION_REPORT.json", report)
        print(json.dumps(report, indent=2), flush=True)
    except BaseException as error:
        save_json(
            output / "REPRODUCTION_REPORT.json",
            {"status": "FAIL", "mode": "real_data", "error": repr(error)},
        )
        raise


if __name__ == "__main__":
    main()
