> Historical notes only. The root README.md and review.py supersede execution guidance below.

# Supplementary Material S1
## Budget Effects on Partial Storage Reassignment in Robotic Mobile Fulfillment Systems under Demand Drift

This package contains executable frozen research code, per-seed results, the revision protocol, and supplementary analyses. The primary Q=4 methods, 100 seeds, all budgets, all movement costs and adverse results remain unchanged. The revision adds Q=2 at the registered representative settings, a cost decomposition, a decision trace and a 30/70/100 split. It does not test a new demand model.

## Quick start

Use CPython 3.12.14 for exact stream compatibility. Create your own environment; do not use or depend on a machine-specific virtual environment. From this folder:

    python -m pip install -r frozen/requirements.txt
    python revision.py preflight
    python revision.py aggregate --output reproduced_statistics
    python revision.py trace --output reproduced_trace
    python revision.py batch --workers 4 --output reproduced_q2

Use a fresh output folder for an actual new search. Reusing a folder containing batch_units reuses only completed, protocol-matching Q2 units. The archived results are in results/. The full Q2 run comprises 100 seeds and 200 search units (abrupt and gradual); it selects exchanges with Q2, freezes each selection, then evaluates held-out test orders. Q4 is reused from the frozen primary results. B2's selection is independent of Q and its recorded sequence is reused before Q2 test evaluation.

## Primary experiment reproduction

    python frozen/reproduce.py check
    python frozen/reproduce.py verify --scope all --output reproduced_primary_statistics
    python frozen/reproduce.py fresh --scope one --seed 2026092401 --workers 1 --output reproduced_one_seed
    python frozen/reproduce.py fresh --scope all --workers 4 --output reproduced_primary_full

check verifies source/assets. verify recalculates statistics from archived per-seed records. fresh reruns the selection and evaluation, and checks against reference records. replay (documented in frozen/) only replays archived search paths and must not be called a fresh search. Do not use --figures unless the font configuration of the frozen legacy plotter is available; the numerical reproduction commands do not need it. Runtime is hardware-dependent and is not expected to match exactly. Only a completed PASS report signifies a finished run.

The original study includes 22,500 primary detail rows (100 seeds x 3 scenarios x 3 budgets x 5 costs x 5 methods). Sensitivity detail contains 45,000 rows for abrupt/gradual drift at 5, 9 and 13 changed SKUs; the 9-SKU rows are reused primary results, not extra independent observations.

## Random streams and drift construction

See RANDOMNESS.md for exact stream payloads, SHA-256 conversion, PRNG and cycle construction. Main seed range: 2026092401 through 2026092500. The original cohort is 2026092401-2026092430; added cohort is 2026092431-2026092500. Instance fingerprints link identical inputs across methods and Q. None of the selection functions accepts test orders.

## Real transaction cases

Download Online Retail II from the UCI Machine Learning Repository, DOI https://doi.org/10.24432/C5CG6D (Daqing Chen, 2012; CC BY 4.0). Expected workbook: online_retail_II.xlsx, SHA-256 bcbe73b35f5b7babf197fb0cb983a11f5d9ff929078d4aa53d171b1f2df2e980, 45,622,278 bytes.

    python revision.py cases --raw /path/to/online_retail_II.xlsx --output reproduced_case_metadata
    python frozen/optional/real_data.py --raw /path/to/online_retail_II.xlsx --output reproduced_real_case_experiments

The first command regenerates extraction metadata and projected orders; the second reruns the real-case strategy experiments. The workbook is not embedded. Customer identifiers are not exported in the revision metadata. Invoice identifiers are retained from the public transaction source so extraction can be verified.

- results/case_boundaries.csv: all four windows in all five cases, dates/times, counts, first/last invoices and one-based global cleaned-basket positions.
- results/case_invoice_membership.csv: exact 30,000 invoice memberships (5,000 calibration + 400 initial + 200 decision + 400 test for each case).
- results/case_stockcodes.csv: all 150 selected StockCodes and case-local SKU IDs.
- results/case_projected_orders.csv: all 5,000 projected orders.
- results/case_dates.csv and frozen/optional/reference/real_data_cases.csv: original fingerprints and diagnostics.
- frozen/optional/reference/real_data_results.csv: all original case/method/budget/cost results.

Case-local numeric SKU IDs may recur across cases and represent different StockCodes. Window boundary dates may share a calendar day; invoice memberships and their chronological positions, not date alone, define the disjoint windows. Between eligible projected invoices there can be skipped invoices. Calibration uses the next 5,000 cleaned invoices after the prior case ends; the next 1,000 baskets containing at least two of its selected products form the three evaluation windows. The following case starts after the last selected test invoice.

These are transaction-data cases with constructed RMFS layouts. They do not validate physical robot routes, congestion, actual relocation time or a deployed warehouse.

## Added analyses and interpretation

- results/cost_decomposition.csv: primary 30% drift, lambda=1, Q4, B0/B2/M, all three K.
- results/decision_trace.csv and trace_report.json: first locked seed, gradual drift, Q4, lambda=1, K5; the whole selection is frozen before test evaluation. Test effects are reported for accepted prefixes only. A rejected swap is not evaluated on test.
- results/cohort_contrasts.csv: original30/added70/pooled100, primary PV and TC contrasts, all parameters and comparators.
- results/representative_cohorts.csv: main-text subset.
- results/cohort_strategy_summary.csv: per-cohort outcome summaries.
- results/batch_detail.csv: 3,600 rows, Q2 plus reused Q4 (100 paired seeds, two drift scenarios, three K, three strategies, lambda=1).
- results/batch_contrasts.csv and batch_summary.csv: paired contrasts and component means.
- results/batch_units/: exact Q2 search paths, decision gains, fingerprints and timings for every seed.
- figures/figure2_cells.csv: all 90 frozen mean/CI values underlying the enlarged Figure 2.

Differences are paired within seed. Negative method differences favor M; negative higher-minus-lower budget differences favor the larger allowance. wins/ties/losses in cohort_contrasts and batch_contrasts count negative/zero/positive differences. Their intervals use sample SD/sqrt(n) and two-sided Student-t critical values with df=n-1. For pooled100 we retain the exact historical critical constant 1.9842169515086827; for 30 and 70, the supplementary code computes t criticals with an integer-df cosine-integral recurrence (no SciPy needed). Cell intervals are exploratory and unadjusted for multiple comparisons. The expansion was fixed after the original30 results had been seen; the added70 is not a new untouched ex ante confirmatory design.

## Integrity and scope

protocol.json was recorded before the new Q2 results. Its hash is recorded in all Q2 units. frozen/ scientific files are byte-identical to the preserved project sources. The archival manifest also lists local IDE/environment files; these are excluded from the reviewer archive and are not execution dependencies. preflight permits only those two optional directories to be absent; every scientific source and reference asset must exist and match its SHA-256. SHA256SUMS.json covers every distributed file except itself. No public upload or permanent repository deposit is asserted by this package.
