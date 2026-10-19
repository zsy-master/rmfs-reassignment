# Data dictionary

| File | Record key | Content |
|---|---|---|
| frozen/reference/formal_detail_100seeds.csv |seed,scenario,budget_k,lambda,strategy |22,500 primary outcomes |
| frozen/reference/sensitivity_detail_100seeds.csv |changed_skus,seed,scenario,budget_k,lambda,strategy |45,000 sensitivity outcomes |
| results/batch_detail.csv |seed,scenario,Q,K,lambda_cost,strategy |Q2 and reused Q4, 3,600 rows |
| results/cohort_contrasts.csv |cohort,scenario,K,lambda,kind,contrast,metric |30/70/100 paired estimates |
| frozen/optional/reference/real_data_results.csv |case_id,strategy,budget_k,lambda |375 case outcomes |
| results/case_invoice_membership.csv |case_id,window,position_in_window |Complete invoice memberships |
| results/case_stockcodes.csv |case_id,sku_id |Case-specific StockCode mapping |
| results/case_projected_orders.csv |case_id,window,order_id |Projected baskets and source invoices |

seed: master seed, not a count of independent parameter cells.
scenario: no_drift/abrupt/gradual.
changed_skus: demand labels changed (5/9/13), not physical moves.
budget_k/K: maximum swaps; n_swaps: actual swaps.
lambda/lambda_cost: cost per SKU-position movement, in PV-equivalent units.
Q: orders per batch; 4 primary / 2 supplement.
strategy: B0 unchanged; B1 random; B2 Jaccard; B3 unbudgeted batching-aware; M budgeted prefix.
movement=2*n_swaps; movement_charge=lambda*movement where present; otherwise derive.
pv_test: held-out pod visits; total_cost=pv_test+lambda*movement, not currency/travel time.
swap_sequence: ordered JSON SKU pairs; final_layout: JSON groups in pod order.
initial_fingerprint: SHA-256 of initial orders/layout.
instance_fingerprint: SHA-256 of initial layout+decision/test payload.
case_fingerprint: ties case outcomes to extraction.
runtime fields are hardware dependent and excluded from numerical identity checks.

Method contrast M−baseline: negative favors M.
Budget contrast K3−K1 / K5−K3: negative favors the larger allowance.
mean/sd/ci_low/ci_high: paired mean / sample SD / two-sided 95% t interval.
n/df: actual pairs/degrees of freedom: 30/29, 70/69, 100/99.
wins/ties/losses: negative / within EPS / positive differences in revision outputs.
Frozen field names explicitly identify M or higher-budget wins.
Cell intervals are exploratory/unadjusted. Repeated cost cells are not independent replications.
Retail mean/min/max across 5 cases are descriptive; ranges are not 95% CIs.

calibration: 5,000 cleaned invoices selecting 30 products.
initial/decision/test: 400/200/400 eligible projected invoices.
30 x 5 mappings do not imply 150 globally distinct StockCodes.
One-based global_cleaned_basket_position indexes sorted cleaned invoices.
Boundary invoices can enclose skipped ineligible baskets; exact memberships define windows.
CustomerID values are not exported; public-source invoice IDs are retained for traceability.
