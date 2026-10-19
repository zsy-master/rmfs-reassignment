"""Protocol-locked UCI Online Retail II external validation.

The protocol was written before the workbook was downloaded or inspected. This
script does not use test orders in SKU selection, layout construction, or swap
selection. Test orders enter only ``evaluate_layout`` and post-hoc diagnostics.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
sys.path.insert(0, str(PROJECT))

from experiment_runner import derived_seed, fingerprint  # noqa: E402
from rmfs_core import (  # noqa: E402
    Order,
    SelectionResult,
    SwapRecord,
    apply_swap,
    evaluate_layout,
    jaccard_matrix,
    select_association_greedy,
    select_budgeted_batching_aware,
    select_random_swaps,
)
from synthetic_data import build_initial_layout  # noqa: E402


RAW_XLSX = HERE / "raw" / "online_retail_II.xlsx"
BUDGETS = (1, 3, 5)
LAMBDAS = (0.0, 0.25, 0.5, 1.0, 2.0)
BATCH_CAPACITY = 4
CALIBRATION_BASKETS = 5000
INITIAL_N = 400
DECISION_N = 200
TEST_N = 400
MIN_PROJECTED_SKUS = 2
PRODUCT_CODE = re.compile(r"^[0-9]{5}[A-Z]?$")
EPS = 1e-12


def norm_code(value: object) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value)).strip().upper()
    return str(value).strip().upper()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_and_clean() -> tuple[list[dict[str, object]], dict[str, object]]:
    workbook = pd.ExcelFile(RAW_XLSX)
    frames = []
    input_rows_by_sheet: dict[str, int] = {}
    mapping = {
        "Invoice": "InvoiceNo",
        "StockCode": "StockCode",
        "Description": "Description",
        "Quantity": "Quantity",
        "InvoiceDate": "InvoiceDate",
        "Price": "UnitPrice",
        "Customer ID": "CustomerID",
        "Country": "Country",
    }
    for sheet_order, sheet in enumerate(workbook.sheet_names):
        frame = pd.read_excel(RAW_XLSX, sheet_name=sheet)
        input_rows_by_sheet[sheet] = len(frame)
        frame = frame.rename(columns=mapping)
        frame["_sheet_order"] = sheet_order
        frame["_source_row"] = range(2, len(frame) + 2)
        frames.append(frame)
    data = pd.concat(frames, ignore_index=True)
    counts: dict[str, object] = {
        "workbook_sha256": sha256(RAW_XLSX),
        "sheets": workbook.sheet_names,
        "input_rows_by_sheet": input_rows_by_sheet,
        "input_rows_total": len(data),
    }

    required_missing = data[["InvoiceNo", "StockCode", "InvoiceDate"]].isna().any(axis=1)
    counts["dropped_missing_invoice_stock_or_date"] = int(required_missing.sum())
    data = data.loc[~required_missing].copy()

    missing_description = data["Description"].isna() | data["Description"].astype(str).str.strip().eq("")
    counts["dropped_missing_or_blank_description"] = int(missing_description.sum())
    data = data.loc[~missing_description].copy()

    data["InvoiceNo"] = data["InvoiceNo"].map(norm_code)
    data["StockCode"] = data["StockCode"].map(norm_code)
    data["InvoiceDate"] = pd.to_datetime(data["InvoiceDate"], errors="coerce")
    data["Quantity"] = pd.to_numeric(data["Quantity"], errors="coerce")
    data["UnitPrice"] = pd.to_numeric(data["UnitPrice"], errors="coerce")

    conversion_missing = data[["InvoiceDate", "Quantity", "UnitPrice"]].isna().any(axis=1)
    counts["dropped_unparseable_date_quantity_or_price"] = int(conversion_missing.sum())
    data = data.loc[~conversion_missing].copy()

    cancellations = data["InvoiceNo"].str.startswith("C", na=False)
    counts["dropped_cancellation_rows"] = int(cancellations.sum())
    data = data.loc[~cancellations].copy()

    nonpositive_quantity = data["Quantity"] <= 0
    counts["dropped_nonpositive_quantity_rows_after_cancellation_filter"] = int(nonpositive_quantity.sum())
    data = data.loc[~nonpositive_quantity].copy()

    nonpositive_price = data["UnitPrice"] <= 0
    counts["dropped_nonpositive_unit_price_rows"] = int(nonpositive_price.sum())
    data = data.loc[~nonpositive_price].copy()

    anomalous_code = ~data["StockCode"].str.match(PRODUCT_CODE, na=False)
    counts["dropped_nonmerchandise_stockcode_rows"] = int(anomalous_code.sum())
    counts["excluded_stockcodes"] = sorted(data.loc[anomalous_code, "StockCode"].unique().tolist())
    data = data.loc[~anomalous_code].copy()

    duplicate_columns = [
        "InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate",
        "UnitPrice", "CustomerID", "Country",
    ]
    exact_duplicate = data.duplicated(subset=duplicate_columns, keep="first")
    counts["dropped_exact_duplicate_rows"] = int(exact_duplicate.sum())
    data = data.loc[~exact_duplicate].copy()
    counts["clean_rows"] = len(data)

    timestamp_counts = data.groupby("InvoiceNo")["InvoiceDate"].nunique()
    counts["invoice_numbers_with_multiple_timestamps"] = int((timestamp_counts > 1).sum())

    baskets = []
    for invoice, group in data.groupby("InvoiceNo", sort=False):
        skus = tuple(sorted(set(group["StockCode"])))
        if not skus:
            continue
        earliest = group["InvoiceDate"].min()
        baskets.append({"invoice": invoice, "date": earliest, "skus": skus})
    baskets.sort(key=lambda row: (row["date"], row["invoice"]))
    counts["clean_invoice_baskets"] = len(baskets)
    counts["date_min"] = baskets[0]["date"].isoformat() if baskets else None
    counts["date_max"] = baskets[-1]["date"].isoformat() if baskets else None
    return baskets, counts


def project_orders(
    basket_rows: list[dict[str, object]], selected: list[str]
) -> tuple[tuple[Order, ...], dict[int, str]]:
    code_to_id = {code: index + 1 for index, code in enumerate(sorted(selected))}
    id_to_code = {value: key for key, value in code_to_id.items()}
    orders = []
    for row in basket_rows:
        projected = tuple(sorted(code_to_id[code] for code in row["skus"] if code in code_to_id))
        if len(projected) >= MIN_PROJECTED_SKUS:
            orders.append(Order(len(orders) + 1, projected))
    return tuple(orders), id_to_code


def make_cases(baskets: list[dict[str, object]]) -> tuple[list[dict[str, object]], dict[str, object]]:
    cases = []
    cursor = 0
    incomplete_reason = ""
    while True:
        if cursor + CALIBRATION_BASKETS > len(baskets):
            incomplete_reason = "fewer than 5000 cleaned baskets remained for another calibration block"
            break
        calibration = baskets[cursor : cursor + CALIBRATION_BASKETS]
        frequencies = Counter(code for row in calibration for code in row["skus"])
        ranked = sorted(frequencies, key=lambda code: (-frequencies[code], code))
        if len(ranked) < 30:
            incomplete_reason = "calibration block contained fewer than 30 merchandise SKUs"
            break
        selected = ranked[:30]
        selected_set = set(selected)
        eligible_indices = []
        for index in range(cursor + CALIBRATION_BASKETS, len(baskets)):
            if len(selected_set.intersection(baskets[index]["skus"])) >= MIN_PROJECTED_SKUS:
                eligible_indices.append(index)
                if len(eligible_indices) == INITIAL_N + DECISION_N + TEST_N:
                    break
        if len(eligible_indices) < INITIAL_N + DECISION_N + TEST_N:
            incomplete_reason = "insufficient projected orders with at least two selected SKUs"
            break
        chosen_baskets = [baskets[index] for index in eligible_indices]
        orders, id_to_code = project_orders(chosen_baskets, selected)
        assert len(orders) == INITIAL_N + DECISION_N + TEST_N
        initial = orders[:INITIAL_N]
        decision = tuple(
            Order(index + 1, order.skus)
            for index, order in enumerate(orders[INITIAL_N : INITIAL_N + DECISION_N])
        )
        test = tuple(
            Order(index + 1, order.skus)
            for index, order in enumerate(orders[INITIAL_N + DECISION_N :])
        )
        layout = build_initial_layout(initial, 30, 10, 3)
        case_id = len(cases) + 1
        cases.append(
            {
                "case_id": case_id,
                "cursor_start": cursor,
                "calibration_start": calibration[0]["date"],
                "calibration_end": calibration[-1]["date"],
                "initial_start": chosen_baskets[0]["date"],
                "initial_end": chosen_baskets[INITIAL_N - 1]["date"],
                "decision_start": chosen_baskets[INITIAL_N]["date"],
                "decision_end": chosen_baskets[INITIAL_N + DECISION_N - 1]["date"],
                "test_start": chosen_baskets[INITIAL_N + DECISION_N]["date"],
                "test_end": chosen_baskets[-1]["date"],
                "selected_codes": selected,
                "id_to_code": id_to_code,
                "initial_orders": initial,
                "decision_orders": decision,
                "test_orders": test,
                "initial_layout": layout,
                "fingerprint": fingerprint(
                    case_id,
                    selected,
                    [[o.order_id, list(o.skus)] for o in initial],
                    [[o.order_id, list(o.skus)] for o in decision],
                    [[o.order_id, list(o.skus)] for o in test],
                    layout,
                ),
            }
        )
        cursor = eligible_indices[-1] + 1
    return cases, {"next_cursor": cursor, "incomplete_reason": incomplete_reason}


def apply_pairs(layout, pairs):
    current = layout
    for pair in pairs:
        current = apply_swap(current, tuple(pair))
    return current


def result_pairs(result: SelectionResult) -> list[tuple[int, int]]:
    return [record.sku_pair for record in result.swaps]


def lambda_prefix(full_m: SelectionResult, lambda_cost: float) -> list[tuple[int, int]]:
    pairs = []
    for record in full_m.swaps:
        if record.marginal_gain - 2.0 * lambda_cost <= EPS:
            break
        pairs.append(record.sku_pair)
    return pairs


def jaccard_distance(left: tuple[Order, ...], right: tuple[Order, ...]) -> float:
    pairs = [(i, j) for i in range(1, 31) for j in range(i + 1, 31)]
    a = jaccard_matrix(left, range(1, 31))
    b = jaccard_matrix(right, range(1, 31))
    return math.sqrt(sum((a[pair] - b[pair]) ** 2 for pair in pairs) / len(pairs))


def run_case(case: dict[str, object]) -> tuple[list[dict[str, object]], dict[str, object]]:
    initial_layout = case["initial_layout"]
    decision = case["decision_orders"]
    test = case["test_orders"]

    started = time.perf_counter()
    b2 = select_association_greedy(initial_layout, decision, max(BUDGETS))
    b2_runtime = time.perf_counter() - started
    started = time.perf_counter()
    full_m = select_budgeted_batching_aware(
        initial_layout, decision, BATCH_CAPACITY, None, 0.0, TEST_N
    )
    m_runtime = time.perf_counter() - started
    started = time.perf_counter()
    b1 = select_random_swaps(
        initial_layout, max(BUDGETS), derived_seed(20260924, "real", case["case_id"], "B1")
    )
    b1_runtime = time.perf_counter() - started

    b2_pairs = result_pairs(b2)
    b1_pairs = result_pairs(b1)
    rows = []
    for lambda_cost in LAMBDAS:
        m_path = lambda_prefix(full_m, lambda_cost)
        for budget in BUDGETS:
            by_strategy = {
                "B0": [],
                "B1": b1_pairs[:budget],
                "B2": b2_pairs[:budget],
                "B3": m_path,
                "M": m_path[:budget],
            }
            runtime = {"B0": 0.0, "B1": b1_runtime, "B2": b2_runtime, "B3": m_runtime, "M": m_runtime}
            for strategy, pairs in by_strategy.items():
                layout = apply_pairs(initial_layout, pairs)
                metrics = evaluate_layout(layout, test, BATCH_CAPACITY, lambda_cost, len(pairs))
                rows.append(
                    {
                        "case_id": case["case_id"],
                        "case_fingerprint": case["fingerprint"],
                        "strategy": strategy,
                        "budget_k": budget,
                        "lambda": lambda_cost,
                        "n_swaps": len(pairs),
                        "movement": metrics["movement"],
                        "pv_test": metrics["pv_test"],
                        "total_cost": metrics["total_cost"],
                        "first_swap": "" if not pairs else f"{pairs[0][0]}-{pairs[0][1]}",
                        "swap_sequence": json.dumps(pairs, separators=(",", ":")),
                        "search_runtime_seconds": runtime[strategy],
                    }
                )
    diag = {
        "case_id": case["case_id"],
        "jaccard_rms_initial_decision": jaccard_distance(case["initial_orders"], decision),
        "jaccard_rms_decision_test": jaccard_distance(decision, test),
        "jaccard_rms_initial_test": jaccard_distance(case["initial_orders"], test),
        "b2_full_path": b2_pairs,
        "m_full_positive_path_at_lambda0": result_pairs(full_m),
        "b2_search_runtime_seconds": b2_runtime,
        "m_search_runtime_seconds": m_runtime,
    }
    return rows, diag


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def paired_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    indexed = {
        (int(r["case_id"]), str(r["strategy"]), int(r["budget_k"]), float(r["lambda"])): r
        for r in rows
    }
    case_ids = sorted({int(r["case_id"]) for r in rows})
    output = []
    for budget in BUDGETS:
        for lambda_cost in LAMBDAS:
            differences = []
            wins = ties = losses = 0
            for case_id in case_ids:
                m = float(indexed[(case_id, "M", budget, lambda_cost)]["total_cost"])
                b2 = float(indexed[(case_id, "B2", budget, lambda_cost)]["total_cost"])
                difference = m - b2
                differences.append(difference)
                if difference < -EPS:
                    wins += 1
                elif difference > EPS:
                    losses += 1
                else:
                    ties += 1
            output.append(
                {
                    "budget_k": budget,
                    "lambda": lambda_cost,
                    "n_cases": len(differences),
                    "m_minus_b2_mean_tc": statistics.mean(differences),
                    "m_minus_b2_min_tc": min(differences),
                    "m_minus_b2_max_tc": max(differences),
                    "m_wins": wins,
                    "ties": ties,
                    "m_losses": losses,
                }
            )
    return output


def font(size: int, bold: bool = False):
    candidates = [
        Path(r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\calibrib.ttf" if bold else r"C:\Windows\Fonts\calibri.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def draw_figure(rows: list[dict[str, object]], path: Path) -> None:
    width, height = 2400, 650
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font, label_font, tick_font = font(34, True), font(24), font(21)
    draw.text((width // 2, 20), "Real-order-data case study: paired M-minus-B2 test-cost difference", font=title_font, fill="black", anchor="ma")
    case_ids = sorted({int(r["case_id"]) for r in rows})
    indexed_rows = {
        (int(r["case_id"]), str(r["strategy"]), int(r["budget_k"]), float(r["lambda"])): r
        for r in rows
    }
    differences = defaultdict(list)
    for case_id in case_ids:
        for budget in BUDGETS:
            for lambda_cost in LAMBDAS:
                m = float(indexed_rows[(case_id, "M", budget, lambda_cost)]["total_cost"])
                b2 = float(indexed_rows[(case_id, "B2", budget, lambda_cost)]["total_cost"])
                differences[(budget, lambda_cost)].append(m - b2)
    panel_w = 450
    gap = 22
    left0 = 65
    top, bottom = 120, 555
    all_values = [value for values in differences.values() for value in values]
    y_min = math.floor((min(all_values) - 2) / 10) * 10
    y_max = math.ceil((max(all_values) + 2) / 10) * 10
    if y_max <= y_min:
        y_max = y_min + 10
    for panel, lambda_cost in enumerate(LAMBDAS):
        left = left0 + panel * (panel_w + gap)
        right = left + panel_w
        draw.rectangle((left, top, right, bottom), outline=(60, 60, 60), width=2)
        draw.text(((left + right) // 2, 78), f"lambda = {lambda_cost:g}", font=label_font, fill="black", anchor="ma")
        for tick_index in range(5):
            value = y_min + (y_max - y_min) * tick_index / 4
            y = bottom - (bottom - top) * tick_index / 4
            draw.line((left, y, right, y), fill=(225, 225, 225), width=1)
            if panel == 0:
                draw.text((left - 10, y), f"{value:.0f}", font=tick_font, fill="black", anchor="rm")
        zero_y = bottom - (0 - y_min) / (y_max - y_min) * (bottom - top)
        draw.line((left, zero_y, right, zero_y), fill=(80, 80, 80), width=3)
        for x_index, budget in enumerate(BUDGETS):
            x = left + 65 + x_index * (panel_w - 130) / 2
            draw.text((x, bottom + 12), str(budget), font=tick_font, fill="black", anchor="ma")
        points = []
        for x_index, budget in enumerate(BUDGETS):
            values = differences[(budget, lambda_cost)]
            mean = statistics.mean(values)
            x = left + 65 + x_index * (panel_w - 130) / 2
            y = bottom - (mean - y_min) / (y_max - y_min) * (bottom - top)
            y_low = bottom - (min(values) - y_min) / (y_max - y_min) * (bottom - top)
            y_high = bottom - (max(values) - y_min) / (y_max - y_min) * (bottom - top)
            draw.line((x, y_low, x, y_high), fill=(34, 94, 168), width=3)
            draw.line((x - 7, y_low, x + 7, y_low), fill=(34, 94, 168), width=3)
            draw.line((x - 7, y_high, x + 7, y_high), fill=(34, 94, 168), width=3)
            points.append((x, y))
        draw.line(points, fill=(34, 94, 168), width=5)
        for point in points:
            draw.ellipse((point[0] - 8, point[1] - 8, point[0] + 8, point[1] + 8), fill=(34, 94, 168))
    draw.text((width // 2, 610), "Reassignment budget K (error bars: case range)", font=label_font, fill="black", anchor="ma")
    draw.text((10, 94), "M - B2 TC", font=label_font, fill="black")
    image.save(path, dpi=(300, 300))


def main() -> None:
    started_at = datetime.now(timezone.utc)
    baskets, cleaning = read_and_clean()
    cases, case_stop = make_cases(baskets)
    go = len(cases) >= 3

    case_rows = []
    for case in cases:
        case_rows.append(
            {
                "case_id": case["case_id"],
                "calibration_start": case["calibration_start"].isoformat(),
                "calibration_end": case["calibration_end"].isoformat(),
                "initial_start": case["initial_start"].isoformat(),
                "initial_end": case["initial_end"].isoformat(),
                "decision_start": case["decision_start"].isoformat(),
                "decision_end": case["decision_end"].isoformat(),
                "test_start": case["test_start"].isoformat(),
                "test_end": case["test_end"].isoformat(),
                "selected_stockcodes": json.dumps(case["selected_codes"], separators=(",", ":")),
                "case_fingerprint": case["fingerprint"],
            }
        )
    write_csv(HERE / "real_data_cases.csv", case_rows)

    cleaning_log = [
        "# Real Data Cleaning Log",
        "",
        f"Run timestamp (UTC): {started_at.isoformat()}",
        f"Protocol decision: {'GO' if go else 'NO-GO'}",
        f"Complete non-overlapping cases: {len(cases)}",
        f"Stopping reason: {case_stop['incomplete_reason']}",
        "",
        "## Row-level audit",
        "",
    ]
    for key, value in cleaning.items():
        cleaning_log.append(f"- {key}: `{json.dumps(value, ensure_ascii=False, default=str)}`")
    cleaning_log.extend(["", "## Case windows", ""])
    for row in case_rows:
        cleaning_log.append(
            f"- Case {row['case_id']}: calibration {row['calibration_start']} to {row['calibration_end']}; "
            f"initial {row['initial_start']} to {row['initial_end']}; decision {row['decision_start']} to {row['decision_end']}; "
            f"test {row['test_start']} to {row['test_end']}."
        )
    (HERE / "real_data_cleaning_log.md").write_text("\n".join(cleaning_log) + "\n", encoding="utf-8")

    if not go:
        (HERE / "real_data_validation_report.md").write_text(
            "# Real-Order-Data External Validation\n\n"
            f"**NO-GO.** The locked rule produced {len(cases)} complete non-overlapping cases; at least three were required. "
            "No strategy outcome experiment was run and no threshold was changed.\n",
            encoding="utf-8",
        )
        (HERE / "real_data_run_manifest.json").write_text(
            json.dumps({"go": False, "n_cases": len(cases), "cleaning": cleaning, "case_stop": case_stop}, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        print(json.dumps({"go": False, "n_cases": len(cases), "reason": case_stop["incomplete_reason"]}, indent=2))
        return

    detail = []
    diagnostics = []
    for case in cases:
        rows, diag = run_case(case)
        detail.extend(rows)
        diagnostics.append(diag)
        print(f"completed case {case['case_id']} of {len(cases)}", flush=True)
    write_csv(HERE / "real_data_results.csv", detail)
    write_csv(HERE / "real_data_diagnostics.csv", diagnostics)
    paired = paired_summary(detail)
    write_csv(HERE / "real_data_m_vs_b2_summary.csv", paired)
    draw_figure(detail, HERE / "real_data_budget_response.png")

    case_ids = sorted({int(row["case_id"]) for row in detail})
    report = [
        "# Real-Order-Data External Validation",
        "",
        "## Status and interpretation boundary",
        "",
        f"**GO.** The locked sequential rule produced {len(case_ids)} complete, non-overlapping temporal cases. "
        "This is an empirical transaction-data case study. The SKU-to-pod layout is model-generated because the source contains no RMFS layout or movement records.",
        "",
        "## Data and design",
        "",
        "The UCI Online Retail II dataset (DOI: 10.24432/C5CG6D; CC BY 4.0) records UK online-retail transactions from December 2009 to December 2011. "
        "Each case uses a 5,000-invoice calibration block to select 30 SKUs, followed in real time order by 400 initial, 200 decision, and 400 test orders containing at least two selected SKUs. "
        "The selected SKU set, initial layout, and strategy decisions are fixed before the test window is evaluated.",
        "",
        "## Drift diagnostics",
        "",
    ]
    for diag in diagnostics:
        report.append(
            f"- Case {diag['case_id']}: Jaccard RMS distance initial-decision = {diag['jaccard_rms_initial_decision']:.4f}; "
            f"decision-test = {diag['jaccard_rms_decision_test']:.4f}; initial-test = {diag['jaccard_rms_initial_test']:.4f}."
        )
    report.extend(["", "## M versus B2 (all cells retained)", ""])
    for row in paired:
        report.append(
            f"- K={row['budget_k']}, lambda={row['lambda']:g}: mean M-B2 TC = {row['m_minus_b2_mean_tc']:.2f} "
            f"(case range {row['m_minus_b2_min_tc']:.2f} to {row['m_minus_b2_max_tc']:.2f}); "
            f"W/T/L = {row['m_wins']}/{row['ties']}/{row['m_losses']}."
        )
    report.extend(
        [
            "",
            "## Reporting rule",
            "",
            "All cases and parameter cells are retained. These few sequential cases support descriptive external comparison, not a claim of statistical generalization to real RMFS warehouses. "
            "The external validation evaluates whether the frozen decision logic can operate on real transaction co-occurrence; it does not validate robot motion, physical relocation time, or a real warehouse layout.",
        ]
    )
    (HERE / "real_data_validation_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "go": True,
        "n_cases": len(cases),
        "protocol": {
            "calibration_baskets": CALIBRATION_BASKETS,
            "initial_orders": INITIAL_N,
            "decision_orders": DECISION_N,
            "test_orders": TEST_N,
            "minimum_projected_skus": MIN_PROJECTED_SKUS,
            "budgets": BUDGETS,
            "lambdas": LAMBDAS,
        },
        "cleaning": cleaning,
        "files": {
            name: sha256(HERE / name)
            for name in [
                "REAL_DATA_PROTOCOL.md", "real_data_cleaning_log.md", "real_data_cases.csv",
                "real_data_results.csv", "real_data_diagnostics.csv", "real_data_m_vs_b2_summary.csv",
                "real_data_budget_response.png", "real_data_validation_report.md",
            ]
        },
    }
    (HERE / "real_data_run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"go": True, "n_cases": len(cases), "detail_rows": len(detail)}, indent=2))


if __name__ == "__main__":
    main()
