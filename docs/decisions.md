# Design Decisions

Recorded deviations from the implementation guide and why.

## 1. Synthetic truth is read only by synth/evaluate/weak_labels

The guide's leakage test says "no source module except synth.py mentions true_issue or
planted". `evaluate.py` and `weak_labels.py` also reference the generator's truth columns,
but strictly to *report* SYNTHETIC-tagged metrics — the guide's own Section 21.3 sanctions
this ("Using the generator's own truth labels to evaluate on synthetic data is fine").
`tests/test_no_label_leakage.py` enforces the real rule: no *pipeline* module
(ingest/normalize/classify/score/radar/alerts/brief/...) may touch truth columns.

## 2. Planted incident stores are forced to size 0.4

`synth.make()` sets any planted-incident store's size to 0.4. The demo story is "weak
signals at a small store beat big-store volume", and it keeps the radar tests
deterministic: with the default thresholds a 3-in-3-days burst at a 2.5-size store would
not clear the Poisson tail (p ≈ 0.0015), which would make the planted-incident test
depend on store-size randomness.

## 3. Policy alerts for records without a store use store_id = 'UNKNOWN'

Records with a missing store are still policy-scanned (per the guide); their alerts are
routed under 'UNKNOWN' rather than dropped, so no risk signal is silently lost.

## 4. pick_quotes falls back to time order when embeddings are unavailable

The centroid-based quote picker needs per-record embeddings; when they are not loaded it
falls back to the earliest records from different channels. Same output contract, one
dependency less in the brief step.

## 5. Truncation detection is empirically tuned to the demo data

The guide's rule (most-common length ≥ 1% of rows and ≥ 100 chars) only fires when the
length histogram is spread out. The generator therefore adds neutral filler phrases and
cuts exactly at the channel caps (6% of rows), producing a realistic spike. The rule in
normalize.py itself is unchanged.

## 6. National-rise check

The "slow national rise in app-crash complaints" uses a convex multiplier
m(d) = 1 + 3.5·(d/119)³ so the last-7-day rate is ≥ 1.4× the prior-28-day rate while no
single store's 3-day vs 28-day ratio approaches the radar's ratio_min of 3. The rise is
reported as a multi-store/national pattern, not a single-store alert (tested).

## 7. Thresholds are starting values

All thresholds (radar p_thr/k_min/ratio_min, dedupe cos_dup/cos_fuse, weak-label
weights, classifier C/tau) are config values, tuned on the team's dev set and injection
trials only. reports/radar_grid.csv records the injection tuning; every evaluate.py run
is appended to reports/eval_log.csv with config hash.
