# Expected outputs and validation

All paths below are relative to the folder specified by --output.

| Output | Expected content |
|---|---|
| REVIEW_REPORT.json | Final status PASS, completed steps and environment |
| primary/formal_detail_1seed.csv in smoke |225 rows, 1 seed |
| primary/sensitivity_detail_1seed.csv in smoke |450 rows, 1 seed |
| primary/formal_detail_100seeds.csv in primary |22,500 rows |
| primary/sensitivity_detail_100seeds.csv in primary |45,000 rows |
| primary/REPRODUCTION_REPORT.json | Mode, seed count and reference comparisons |
| primary/*summary*.csv and *comparisons*.csv | Main/sensitivity means, paired intervals and counts |
| primary/figures/ | Four regenerated synthetic figure sets |
| cohorts/cohort_contrasts.csv |1,260 PV/TC comparisons across 3 cohorts |
| cohorts/cohort_strategy_summary.csv |675 cohort/strategy summaries |
| paper/ | Tables 1-5 CSV, figures 1-3 PDF/PNG and underlying values |
| q2/batch_detail.csv in full q2 mode |3,600 rows = 1,800 Q2 + 1,800 Q4 |
| q2/batch_units/2026092401.json | Exact pairs, decision gains, fingerprints |
| trace/decision_trace.csv in smoke | Accepted (23,26), then rejected score-zero (10,22) |
| metadata/case_invoice_membership.csv in retail |30,000 memberships, no overlap |
| metadata/case_stockcodes.csv |150 case-specific mappings, 30 per case |
| metadata/case_projected_orders.csv |5,000 projected orders |
| cases/real_data_results.csv |375 outcomes |
| cases/REPRODUCTION_REPORT.json |5 cases, workbook hash, reference comparisons |
| runtime/BENCHMARK_REPORT.json |36 observations; timings hardware dependent |

statistics reads archived raw outcomes and does not copy raw detail into primary/.
primary/fresh writes new raw detail. Do not confuse recomputation with new selection.

## Numerical anchors

Primary 30% abrupt drift, Q=4, lambda=1: M mean TC for K=1/3/5 is 282.86/260.21/243.12.
Paired budget differences: −22.65[−24.43,−20.87],−17.09[−19.21,−14.97].
Primary 30% gradual drift, Q=4, lambda=1: M mean TC is 286.67/280.36/280.45.
K5−K3: 0.09[−0.10,0.28].
Same gradual setting, Q=2: M mean TC is 467.43/446.40/444.61.
K5−K3: −1.79[−3.11,−0.47]; 8 savings / 92 ties / 0 losses.
Do not directly compare absolute TC across capacities.

Trace: forecast net saving 18; realized net saving 5; next Score=0 stops; rejected candidate not evaluated on test.
Original/added/pooled M−B2 abrupt K=1, lambda=1:
−1.43[−3.69,.82],−1.19[−2.54,.17],−1.26[−2.40,−.12].
Anchors supplement comprehensive checks; they do not replace them.

## Workload and meaning of PASS

check: no selection; file/source integrity only.
statistics: light aggregation relative to fresh search; not an experiment.
smoke: 1 seed and 3 primary units, 2 Q2 selections plus trace; only a small execution check.
primary: 300 fresh search units, generally much longer than smoke.
q2: 200 fresh selection units.
retail: reads 1,067,371 workbook rows and executes 5 cases; Excel cleaning is memory intensive.
runtime: 36 serial calls on the original 9 instances; no exact-seconds match expected.
A partial CSV, progress counter or pilot PASS does not mean the larger run finished.
Existing historical validation reports have their own dates/scopes and are not today's executions.

## Troubleshooting

Extract ZIP fully; open terminal in S1. Install requirements using the execution interpreter.
Use a new output folder outside S1. For fewer cores choose --workers 1 or --workers 2.
For hash failures re-extract; do not edit hashes to suppress errors.
Use the exact UCI workbook, not a renamed substitute.
A different elapsed time is normal; different paths/PV/TC/fingerprints are not silently accepted.
The scripts need no PyCharm, Word, commercial solver or Windows shortcuts.
Only Windows 10 / CPython 3.12.14 was tested in this session. Linux/macOS commands are provided without claiming those platforms were tested.


## Submission-copy integrity

PACKAGING.json records the approved omission of exactly 14 author-only files and replacement of one module README. Original scientific files, data and protocol hashes remain unchanged. The current preflight verifies 355 present frozen files (354 in original bytes plus the replacement README), the archived original README, and all core/asset locks. It records the 14 approved omissions separately from the 978 absent local IDE/environment files.

Historical snapshot inventories and validation reports are retained as provenance, with their original execution scopes. SHA256SUMS.json describes the actual current archive. Refer to validation/SLIM_VALIDATION.json for this packaging check. A legacy report is not a claim that the current run repeated the full experiment.
