# Exact randomness and construction specification

## PRNG and derived seeds

The code uses CPython 3.12.14 random.Random (Mersenne Twister), not NumPy's generator and not Python's process-randomized hash(). The integer seed is:
1. Form payload = "|".join([str(master_seed), *(str(part) for part in parts)]).
2. Encode UTF-8.
3. Compute SHA-256.
4. Take digest bytes 0 through 7 (the first eight bytes).
5. Interpret as an unsigned big-endian integer and pass to random.Random.

Stream parts:
- drift_labels
- initial_window
- <scenario>|decision_window
- <scenario>|test_window
Here <scenario> is no_drift, abrupt or gradual. Initial data and layout are shared across these scenarios for a given master seed. A stream does not depend on method, K, lambda or Q. B1 uses parts (<scenario>, "B1", 5), i.e. payload "<master>|<scenario>|B1|5". It creates one max-five-swap path, enumerates feasible cross-pod pairs lexicographically, excludes previously visited layouts, chooses rng.choice from the remaining ordered candidates at each step, and takes the appropriate K prefix. The stream does not include intensity, so its draws are shared across intensities while feasible candidates depend on the actual layout. No hidden community labels are stored in ExperimentInstance or passed to layout construction or selection.

## Initial demand and layout

SKU labels are {(sku): (sku-1)//3 for sku in 1..30}. Order generation consumes random draws in this order: length via rng.choices over sorted lengths [2,3,4] with weights [.45,.40,.15]; focal community via rng.choice over sorted community IDs; first SKU via rng.choice within that community. At each later item, build unused focal and all-unused candidates in stable list order. If focal candidates exist and rng.random()<.8, choose one from them; otherwise choose one from all unused SKUs. Short-circuiting means the .8 probability draw is not consumed if the focal candidate list is empty. The all-unused set may still contain a focal-community SKU.

The 400 initial orders alone determine the layout. Jaccard uses counts of orders containing i, j and both; an empty union gives zero. Fill pods in sequence: start with unassigned SKU minimizing (-frequency, SKU ID); then select SKU minimizing (-sum of its Jaccard scores to items already in that pod, -frequency, SKU ID) until capacity3. Normalize layout by sorting items inside pods; preserve pod order. Labels play no part.

## Exact changed-label cycles

This is a community-membership permutation used only in data generation; it is not the physical SKU swap sequence.
1. target = floor(30*ratio + .5). The tested ratios are 5/30, .3 and 13/30, giving exactly5,9,13 changes.
2. Start available=sorted(SKU IDs), then rng.shuffle(available) using drift_labels stream.
3. For an odd target, enumerate itertools.combinations(available,3) in that shuffled-list order. Choose the first triple (left,middle,right) with three distinct original community labels. Assign new[left]=old[middle], new[middle]=old[right], new[right]=old[left]. Remove those three from available without reordering others.
4. Scan remaining list positions left_index from0, then right_index>left_index ascending. Choose the first pair with different current labels; record it and remove the right then left positions. Repeat until (target-3)/2 disjoint pairs have been found.
5. Exchange labels of the recorded pairs. Every selected SKU changes community. Other SKUs stay fixed. Community sizes remain three.
The frozen implementation is drift_by_pair_swaps in synthetic_data.py; its historical name includes pair swaps although odd targets also need a triple.

## Scenario order windows

Initial window always uses the old structure. No drift: decision and test both old. Abrupt: decision and test both new. Gradual: for decision offset t=0..199, draw rng.random() and use the new structure iff it is <t/199, otherwise old; then generate that one order with the same decision-window RNG. Test uses the new structure throughout, with a separate test-window RNG. Hence gradual switching is a mixture probability, not interpolation of SKU labels or a physical gradual relocation. Initial/decision/test lengths400/200/400.

## Evaluation and tie handling

Within each candidate layout, initialize a batch with the remaining order requiring most distinct pods; tie: smaller order ID. Add the order giving fewest additional distinct pods; tie: smaller order ID; stop at Q or no orders. Count each pod once per batch and sum across batches. Candidate pairs are cross-pod SKU pairs ordered lexicographically. Main M ranks by horizon-scaled decision PV reduction minus 2*lambda; ties within EPS=1e-12 use lexicographic SKU pair. Accept only Score>EPS (the numerical realization of strictly positive). Stop at most K or no positive score. Recompute after each accepted exchange. B2 maximizes strictly positive within-pod pairwise Jaccard increment with the same tie rule, at mostK. Search routines receive current layout, decision orders, Q/K/lambda and horizon length, never test order content.

Horizon scaling=400/200=2. Movement=2*actual_swaps. Test TC=PV_test+lambda*Movement. The selected layout is frozen before withheld orders are evaluated. Do not select methods, seeds or examples using held-out outcomes.

## Retail random-baseline stream

For the five transaction-data cases, B1 uses master seed 20260924 and parts ("real", case_id, "B1"). The exact UTF-8 payload is "20260924|real|<case_id>|B1", where case_id is the case identifier recorded in the retail metadata and results. Apply the same SHA-256, first-eight-byte and unsigned-big-endian conversion specified above. This specifies the existing implementation in frozen/optional/legacy/run_real_data_validation.py; it does not change the retail generator, case extraction or recorded paths.

## Fingerprints

fingerprint(*objects) serializes the argument tuple with json.dumps(ensure_ascii=True,sort_keys=True,separators=(",",":")) then SHA-256 UTF-8. Initial fingerprint covers initial order payload and initial layout. Instance fingerprint covers initial layout, decision-order payload and test-order payload. Each order payload is [order_id,list(skus)]. See instances.py and the recorded checkpoints for exact object ordering.
