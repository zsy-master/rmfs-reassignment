# Locked Protocol: Real-Order-Data External Validation

Protocol lock timestamp: 2026-09-24, before downloading or inspecting transaction values.

Status: **preregistered project protocol**. The rules below may not be changed after viewing outcome comparisons. Any implementation-only clarification will be logged with a timestamp and must not use test results.

## Purpose and allowed claim

This is a real-order-data external validation / empirical transaction-data case study using UCI Online Retail II. It is not a real RMFS warehouse experiment because the dataset contains no SKU-to-pod layout, robot trajectories, pod visits, or physical relocation records. A model-generated initial layout and the frozen RMFS evaluator are therefore retained.

## Official source

- Dataset: Online Retail II
- Creator/citation: Daqing Chen, UCI Machine Learning Repository
- DOI: 10.24432/C5CG6D
- License: Creative Commons Attribution 4.0 International (CC BY 4.0)
- Recorded coverage: 1 December 2009 to 9 December 2011
- Official file: `online_retail_II.xlsx`

## Cleaning rules

Rows are processed in `InvoiceDate` order, with original row order as the final tie-break.

1. Normalize column names from the two workbook sheets to `InvoiceNo`, `StockCode`, `Description`, `Quantity`, `InvoiceDate`, `UnitPrice`, `CustomerID`, and `Country`.
2. Drop rows missing `InvoiceNo`, `StockCode`, or `InvoiceDate`.
3. Drop rows with missing/blank `Description`; `CustomerID` may be missing because it is not used.
4. Convert `InvoiceNo` and `StockCode` to trimmed uppercase strings.
5. Exclude invoice numbers beginning with `C` (cancellations).
6. Exclude `Quantity <= 0` and `UnitPrice <= 0`.
7. Keep only merchandise codes matching `^[0-9]{5}[A-Z]?$`; this excludes postage, fees, manual adjustments, and other non-product codes without consulting outcomes.
8. Remove exact duplicate transaction rows across all available fields.
9. Aggregate repeated lines for the same invoice and SKU; an order basket is the set of distinct retained SKUs in an `InvoiceNo`.
10. Retain the earliest invoice timestamp when identical invoice numbers have multiple timestamps and log such cases.

## Case-generation and SKU-selection rule

Cases are generated sequentially and non-overlapping from the cleaned invoice stream.

1. The calibration block is the next **5,000 cleaned invoice baskets** beginning at the current cursor.
2. Select 30 SKUs using only that calibration block, ranked by the number of distinct calibration invoices containing the SKU. Break frequency ties by lexicographically smaller `StockCode`.
3. Freeze these 30 SKUs for the case.
   Internally map the selected `StockCode` values in lexicographic order to integer IDs 1-30, so the frozen lexicographic tie-break in v1 corresponds to lexicographic `StockCode` order.
4. Project subsequent invoices onto the selected set and retain invoices containing at least **two distinct selected SKUs**.
5. Take the first 400 eligible projected orders as the initial window, the next 200 as the decision window, and the next 400 as the test window.
6. Advance the cursor to the first cleaned invoice after the case's test window and repeat.
7. Continue until another complete case cannot be formed. No calendar segment or case may be selected or discarded based on M/B2 outcomes.

## Go / No-Go rule

Proceed to the strategy experiment only if at least **three complete, non-overlapping cases** are formed and each case has exactly 30 selected SKUs plus 400/200/400 eligible orders. Otherwise record No-Go and stop without changing thresholds or window sizes.

No-Go also applies if implementation would require future/test information for SKU selection, algorithm redesign, or manual selection of favorable periods.

## Frozen layout, strategies, and parameters

- Build each case's initial layout from its 400-order initial window using the frozen deterministic Jaccard-plus-frequency greedy packing rule.
- Latent communities are unavailable and are not reconstructed.
- Run B0, B1, B2, B3, and M using the same case-specific initial layout, decision orders, and test orders.
- Use `K in {1,3,5}` and `lambda in {0,0.25,0.5,1,2}`.
- M uses the frozen v1 score and tie rules. B2 uses the frozen association-based rule. B3 follows the unbudgeted M path. B1 uses a reproducible case-specific hash-derived random stream and avoids repeated layouts.
- Test orders are accessible only to the final evaluation function.

## Outcomes

For every case, strategy, K, and lambda, retain:

- test pod visits (`PV_test`)
- executed swap count
- movement quantity (`M_move = 2 * swaps`)
- total cost (`TC = PV_test + lambda * M_move`)
- paired M-minus-B0 and M-minus-B2 differences
- candidate search path for M and B2

Across cases, report all case-level results and descriptive paired means, ranges, and win/tie/loss counts. With a small number of temporal cases, confidence intervals are descriptive and no broad population claim will be made.

## Drift diagnostics

For description only, compute binary SKU co-occurrence Jaccard matrices for the initial, decision, and test windows and their normalized Frobenius distances. These diagnostics do not enter layout construction, candidate scoring, stopping, parameter selection, or case inclusion.

## Stopping and reporting

- Do not modify v1 or tune parameters after results are seen.
- Do not exclude unfavorable cases.
- Report negative and null findings.
- If runtime or data preparation exceeds the planned one-to-two-day scope, preserve the partial log and declare No-Go rather than changing the scientific design.
