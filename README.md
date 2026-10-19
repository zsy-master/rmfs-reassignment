# RMFS partial storage reassignment

Reproducibility materials for **Budget Effects on Partial Storage Reassignment in Robotic Mobile Fulfillment Systems under Demand Drift**, by Shangyu Zhong and Kun Wang.

## Fixed paper artifact

Public artifact version **1.0.0** packages the frozen **v1 scientific method**. The release contains executable sources, all per-seed synthetic outcomes, exact random-stream and drift specifications, supplementary Q=2 results, original/added/pooled seed statistics, decision traces and five retail-case extraction records.

- [Release v1.0.0](https://github.com/zsy-master/rmfs-reassignment/releases/tag/v1.0.0)
- [Download the complete S1.zip](https://github.com/zsy-master/rmfs-reassignment/releases/download/v1.0.0/S1.zip)
- [English reproduction guide](S1/README.md)
- [Randomness and drift construction](S1/RANDOMNESS.md)
- [Paper-to-file map](S1/PAPER_MAP.md)
- [Expected outputs](S1/EVALUATION.md)

S1.zip SHA-256:

4708f0c5151af4806cb48516fc13057b8323fef44990718baba4a6cf0d973d57

Use the versioned release asset for the exact archived ZIP bytes. GitHub-generated source snapshots may use a different outer ZIP layout; file-level checks are recorded in S1/SHA256SUMS.json.

## Start here

Download and fully extract S1.zip. Open a terminal inside the extracted S1 folder and use CPython 3.12.14 with the dependencies pinned in requirements.txt.

~~~powershell
py -3.12 -m venv ../rmfs_env
../rmfs_env/Scripts/python.exe -m pip install -r requirements.txt
../rmfs_env/Scripts/python.exe review.py check
../rmfs_env/Scripts/python.exe review.py statistics --output ../review_statistics
../rmfs_env/Scripts/python.exe review.py smoke --workers 1 --output ../review_smoke
~~~

check verifies files; statistics recalculates archived results; smoke performs a small fresh selection check. Complete synthetic, Q=2, retail and runtime modes are documented in S1/README.md. Each output directory must be new and outside S1; it is created automatically. No author-specific drive or directory is required.

## Data and interpretation

Synthetic experiments use 100 paired seeds, three drift intensities and the unchanged frozen rules. The original-30 and added-70 cohorts are disclosed separately. Unfavorable results and zero-containing intervals are retained. The study does not establish a universal advantage of M over B2 or an optimal budget.

Retail cases use [Online Retail II, Chen (2012), UCI](https://doi.org/10.24432/C5CG6D), CC BY 4.0. The raw workbook must be downloaded separately. This repository supplies window dates, selected StockCodes, invoice boundaries and memberships, projected baskets and outcomes; CustomerID is not exported. The layouts are constructed for evaluation, so these are transaction-data cases rather than physical warehouse validation.

## Public packaging and rights

The public package leaves scientific code, results, seeds, protocol and case data unchanged. Historical local paths in seven validation reports have been represented as LOCAL_PATH/basename. The publication provenance is recorded in S1/provenance/PUBLIC_RELEASE.json.

See S1/RIGHTS.md. Public distribution does not assign a new MIT, BSD or GPL licence. The manuscript and raw workbook are not included. A code release is not a statement of manuscript acceptance.
