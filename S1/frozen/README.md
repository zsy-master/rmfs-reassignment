# Frozen scientific implementation

Use the English gateway in the parent S1 directory:

    python review.py check
    python review.py statistics --output ../review_statistics
    python review.py smoke --workers 1 --output ../review_smoke

The parent README.md describes the interpreter, dependencies, full experiments and expected outputs. Run the commands from S1, where review.py is located.

## Modules

| File or folder | Role |
|---|---|
| rmfs_core.py | Deterministic batching, swaps and selection |
| synthetic_data.py | Frozen order generator and initial layout |
| instances.py | Instance construction, streams and fingerprints |
| experiment.py | Search paths and outcome expansion |
| analysis.py | Statistical tables and consistency checks |
| figures.py | Numerical synthetic plots |
| io_utils.py | Checkpoints and strict reference comparison |
| reproduce.py | Synthetic execution, validation and resumption |
| protocol_config.json | Preserved historical configuration |
| requirements.txt | Pinned dependency versions |
| reference/ | Frozen outcomes and checkpoints required for comparison |
| optional/ | Retail and serial-runtime reproduction |
| tests/ | Scientific and reproduction tests |
| validation/ | Historical execution and fidelity records |

The historical drift_ratios field in protocol_config.json is preserved. The final study uses the explicit changed-SKU counts 5, 9 and 13 in experiment.py.

## Distribution provenance

The author-only tutorials and shortcuts were omitted from this submission copy with author approval. PACKAGING.json in S1 enumerates the exact 14 omissions and this README replacement. The original README is preserved at provenance/frozen_README.md.

PACKAGE_HASHES.json is the original frozen-snapshot inventory. It is retained unchanged as provenance and includes the omitted helpers. It is not the current distribution inventory. The current complete distribution is checked against S1/SHA256SUMS.json. The revised preflight permits only the explicitly named auxiliary omissions and this documentation replacement; all scientific files, data and original protocol checks remain mandatory.

The algorithms, random streams, seeds, parameters, reference outcomes and original scientific code hashes are unchanged. Output directories are supplied explicitly by review.py; the program creates new directories outside S1.
