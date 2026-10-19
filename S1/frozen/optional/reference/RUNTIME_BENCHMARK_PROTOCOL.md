# Runtime Benchmark Protocol

Locked before benchmark execution on 2026-09-24.

- Code: frozen v1 functions in `rmfs_core.py` and frozen instance builder.
- Instances: confirmatory seeds 2026092401-2026092403, each under no drift, abrupt drift, and gradual drift at the frozen 30% target intensity (nine instances).
- Methods: B2 with K=5; M with K=1, K=3, and K=5.
- M benchmark uses lambda=0 and future horizon 400. This measures the least restrictive stopping condition in the tested cost grid and does not change scientific outcomes.
- Timing boundary: strategy search only, measured with `time.perf_counter`; data generation and test evaluation are excluded.
- One deterministic timed run per instance-method pair. Report all 36 observations plus mean, median, minimum, and maximum. Timing results describe this machine and software environment only.
