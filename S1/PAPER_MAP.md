# Paper to artifact map

    python review.py statistics --output ../review_statistics

This exports the numerical paper items from archived outcomes. The primary, q2 and retail modes execute the corresponding experiments.

| Item | Source | Output within review_statistics/paper | Fresh execution |
|---|---|---|---|
| Figure 1 | Recomputed sensitivity strategy summary | figure1.pdf/png; figure1_values.csv | primary |
| Table 1 | Recomputed sensitivity budget effects | table1_budget_interval_counts.csv | primary |
| Figure 2 | Recomputed 90 M-minus-B2 TC cells | figure2.pdf/png; figure2_values.csv | primary |
| Figure 3 | 375 retail outcomes and 75 paired case differences | figure3.pdf/png; figure3_case_differences.csv; figure3_values.csv | retail |
| Table 2 | Primary 22,500 rows, cohort cost decomposition | table2_cost_components.csv: 14 display rows | primary |
| Table 3 | Archived decision trace and trace report | table3_decision_trace.csv | smoke reruns the trace |
| Table 4 | batch_detail.csv: 3,600 rows, paired statistics recalculated | table4_capacity_budget_contrasts.csv: 8 contrasts | q2 regenerates Q2; Q4 is reused |
| Table 5 | Primary rows and original seed lock | table5_seed_cohorts.csv: 24 long-format rows, 8 contrasts x 3 cohorts | primary |
| Runtime | Original 9-instance serial benchmark | Separate runtime-mode output | runtime |

SEEDS.csv links the 100 seeds and their 30/70 cohort labels to each seed's outcomes. RANDOMNESS.md specifies hash derivation, PRNG and exact drift cycles; the implementations are frozen/instances.py and frozen/synthetic_data.py.

Retail traceability records:
- results/case_boundaries.csv: 20 window records, including calibration.
- results/case_invoice_membership.csv: all 30,000 invoice memberships.
- results/case_stockcodes.csv: 30 SKU-to-StockCode mappings per case.
- results/case_projected_orders.csv: 400 initial + 200 decision + 400 test orders per case.
- results/case_report.json: workbook hash, nonoverlap and fingerprint checks.
- frozen/optional/reference/real_data_results.csv: all 375 outcomes, linked by case_fingerprint.

Archived revised Figure 2 presentation files remain in figures/. Figure 3 bars show the range across five cases, not a confidence interval. Numerical reproduction preserves means, intervals, ranges and uncertainty masks; PDF metadata and font rendering need not be byte-identical to manuscript images.

To remake tables from a new Q2 run, use its q2/batch_detail.csv, batch_summary.csv and batch_contrasts.csv directly. To remake the retail comparison from a fresh retail run, use its cases/real_data_results.csv and real_data_m_vs_b2_summary.csv. The statistics export intentionally uses the archived full records so it can run without downloading the workbook or rerunning every experiment.
