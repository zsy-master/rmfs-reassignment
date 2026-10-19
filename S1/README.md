# Supplementary Material S1

## Budget Effects on Partial Storage Reassignment in Robotic Mobile Fulfillment Systems under Demand Drift

Shangyu Zhong and Kun Wang. Public reproducibility materials for the revised DILSCM2026 manuscript.

## Quick start

Use **CPython 3.12.14**, with the pinned packages in requirements.txt. Extract the entire S1 directory and open a terminal inside it, where review.py is located.

Windows PowerShell, without activating the environment:

    py -3.12 -m venv ../rmfs_env
    ../rmfs_env/Scripts/python.exe --version
    ../rmfs_env/Scripts/python.exe -m pip install -r requirements.txt
    ../rmfs_env/Scripts/python.exe review.py check
    ../rmfs_env/Scripts/python.exe review.py statistics --output ../review_statistics
    ../rmfs_env/Scripts/python.exe review.py smoke --workers 1 --output ../review_smoke

The version command should show 3.12.14. The Windows launcher selects an installed interpreter; it does not install the required patch version. On Linux/macOS, create the environment using python3.12 and use ../rmfs_env/bin/python for the later commands. Only Windows 10 with 64-bit CPython 3.12.14 was tested here.

No GPU, commercial optimizer, Word or PyCharm is needed. Initial dependency installation needs access to the package index, or locally supplied wheels. Synthetic reproduction then needs no network access. Raw retail reproduction also requires the public workbook described below.

## Execution modes

Use the environment's Python interpreter wherever "python" appears below. Each output directory must be **new and outside S1**. The default worker count is the smaller of 4 and the available CPU count; --workers 1 is suitable for a small execution check.

| Purpose | Command | Scope |
|---|---|---|
| Integrity | python review.py check | Distributed file hashes and frozen preflight; no search |
| Recalculate paper outputs | python review.py statistics --output ../review_statistics | Archived outcomes, 30/70/100 cohort statistics, tables 1-5 and figures 1-3 |
| Small fresh execution | python review.py smoke --workers 1 --output ../review_smoke | First seed, all 3 intensities; fresh Q2 abrupt/gradual selections and the Q4 decision trace |
| Full synthetic experiment | python review.py primary --output ../review_primary | 100 seeds, 3 intensities, 300 fresh search units, statistics and plots |
| Full Q2 supplement | python review.py q2 --output ../review_q2 | 100 seeds x 2 scenarios = 200 fresh Q2 search units |
| Retail extraction and experiment | python review.py retail --raw "/path/to/online_retail_II.xlsx" --output ../review_retail | Metadata extraction and all 5 retail-case strategy experiments |
| Runtime measurements | python review.py runtime --output ../review_runtime | Original 9 instances, 36 serial timing observations |

The final REVIEW_REPORT.json must have status PASS for the requested mode. A partial CSV or a completed pilot does not establish completion of a larger run.

Start with check, statistics and smoke. The statistics mode **recalculates existing outcomes**; it does not rerun selection. The primary, q2 and retail modes execute their respective experiments. The primary mode uses archived Q2 outcomes for Table 4; use q2 for fresh Q2 selection. Table 3 in statistics uses the archived illustration; smoke reruns that selection and stopping decision.

Plots can differ in font rendering or spacing from the final SAE presentation copies. Their means, intervals and uncertainty masks must match. Figure 2 is regenerated with the revised 10.5-point cell labels, 9-point axes and CI hatching. Values with magnitude below 0.05 print as 0.0; exact signed values remain in figure2_values.csv. This presentation wrapper does not change the frozen statistics.

## Optional checkpoint replay

After the checks above, an optional diagnostic can re-evaluate the archived path prefixes:

    python frozen/reproduce.py replay --scope one --seed 2026092401 --output ../review_replay

Run from the S1 directory and use the configured environment's interpreter. The output is a new directory outside S1, created automatically. Replay evaluates stored swap paths; it does not search for swaps again and must not be described as a fresh experiment. Use review.py smoke or the full experiment modes for fresh selection. The reviewed, frozen algorithm and parameters are unchanged.

## Inventory

- review.py: English execution gateway.
- paper_outputs.py: numerical paper tables and plot exports.
- requirements.txt: pinned dependencies, identical to frozen/requirements.txt.
- SEEDS.csv: all 100 seeds and original-30 / added-70 cohort labels.
- RANDOMNESS.md: SHA-256 seed derivation, PRNG, initial packing, drift cycles and ties.
- EVALUATION.md: expected counts, numerical anchors and completion criteria.
- PAPER_MAP.md: paper item to source, command and output.
- DATA_DICTIONARY.md: record keys, variables, units and contrast signs.
- RIGHTS.md and CITATION.cff: attribution and package metadata.
- frozen/: unchanged scientific code, references, checkpoints and historical records.
- results/: archived revision outcomes, per-seed Q2 paths and retail metadata.
- figures/: revised Figure 2 presentation files and all 90 exact cells.
- provenance/: original revision source and portability record.
- validation/: validation scope and selected reports for this reviewer package.
- SHA256SUMS.json: SHA-256 for each distributed file except the manifest itself.
- PACKAGING.json: author-approved auxiliary omissions and documentation replacement.
- validation/SLIM_VALIDATION.json: validation scope for this submission copy.
- validation/FINAL_VALIDATION.json: final documentation and execution checks; earlier reports retain their original dates and scopes.
- provenance/PUBLIC_RELEASE.json: public release packaging and historical local-path redactions.

This submission copy omits 14 author-only legacy helpers and tutorials, as explicitly listed in PACKAGING.json. No scientific source or outcome is omitted. The frozen/README.md module guide is updated; its original is retained at provenance/frozen_README.md. The archive also excludes virtual environments, IDE settings and __pycache__.

Use review.py from this S1 directory. Historical records in docs/, provenance/ and validation/ retain their original dates and scopes and may mention earlier local workflows. This README is the current execution guide.

protocol.json and frozen/PACKAGE_HASHES.json preserve the original snapshot inventories, including the omitted helpers. SHA256SUMS.json is the current distributed-file inventory. Preflight checks the exact auxiliary omission list and original documentation provenance, while still requiring all scientific code and reference assets. See PACKAGING.json for the audited packaging changes.

## Data source

Synthetic orders are generated by the frozen program. No private warehouse data is required.

For raw retail reproduction, download and extract online_retail_II.xlsx from the [UCI Online Retail II page](https://archive.ics.uci.edu/dataset/502/online+retail+ii).
Source: Chen, D. (2012), Online Retail II, UCI Machine Learning Repository, [DOI 10.24432/C5CG6D](https://doi.org/10.24432/C5CG6D), CC BY 4.0.

Expected workbook size: 45,622,278 bytes. SHA-256:

    bcbe73b35f5b7babf197fb0cb983a11f5d9ff929078d4aa53d171b1f2df2e980

The workbook is not embedded. Projected baskets, selected StockCodes, dates and exact invoice memberships are included. CustomerID values are not exported. The five cases use transaction data and constructed layouts; they are not physical warehouse validation.

## Frozen experiment

N=30, P=10, C=3; initial/decision/test windows of 400/200/400 orders; main Q=4; K={1,3,5}; lambda={0,0.25,0.5,1,2}. Scenarios are no drift, abrupt drift and gradual drift. Actual changed-SKU counts are 5, 9 and 13.

Seeds are 2026092401 through 2026092500. The original 30 end at 2026092430; the added 70 begin at 2026092431. Primary detail has 22,500 rows; sensitivity detail has 45,000 rows. The middle intensity reuses the primary results. Q2 contributes 1,800 new outcome rows plus 1,800 reused Q4 rows. The five retail cases contribute 375 outcomes.

Movement = 2 x actual swaps; TC = PV_test + lambda x movement. Contrasts are paired within seed. The two-sided 95% t intervals are exploratory and unadjusted, with the cohort's actual degrees of freedom. The pooled-100 calculation retains the historical critical constant. The expansion followed examination of the original 30 results; it is not an untouched confirmatory sample. Adverse outcomes are retained. The paper claims neither universal superiority of M over B2 nor an optimal budget.

The reviewer gateway, export wrapper and documentation do not change the frozen algorithm, generator, seeds, parameters or results. Public availability does not assign a new open-source licence. See RIGHTS.md for attribution and rights.

## Public release

Public artifact version: 1.0.0. This is a packaging version; the scientific method remains frozen v1. Historical absolute local paths in seven validation reports are represented as LOCAL_PATH/<basename>. Report scopes and outcomes are unchanged. No scientific source, per-seed result, seed list, protocol, checkpoint or case metadata was altered. The raw retail workbook and manuscript are not distributed. The archive is named S1.zip for a portable GitHub release asset. Its distributed-file inventory is SHA256SUMS.json.
