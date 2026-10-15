# Data Dictionary

## Day-1 discovery checklist (answers to write when the organizers' files arrive)

1. Files, columns and encodings of the four channels and the store master. Which column
   joins a record to a store?
2. Timestamp format and time zone, date range, and whether there is a time of day or only
   a date.
3. Is any labeled sample given to developers (size, columns)? Or do labels exist only
   inside evaluate.py?
4. Taxonomy fields: issue ids and names, owner function, any default severity, any
   mandatory-risk flag.
5. The severity scale and the exact definition of 'actionable'.
6. How evaluate.py is called, which prediction and detection files it expects, and how
   lead time and its reference point are defined.
7. Duplicate rate, truncation rate, share of each language pattern, and the distribution
   of records per store.
8. Whether product, supplier, batch or equipment identifiers exist anywhere.

`python -m storesignal.cli inspect` answers items 1, 2 and 7 automatically
(reports/profile.md). `python -m storesignal.cli automap` proposes the column mapping
(config/mapping_suggested.yaml). `python -m storesignal.cli build_taxonomy` converts the
organizers' taxonomy file into taxonomy.yaml + a routing draft (review
reports/taxonomy_match.csv by hand).

## Unified record schema (current, synthetic mode)

| Column | Type | Notes |
|---|---|---|
| record_id | str | channel + source id, unique, never reused |
| channel | str | review, app, staff_note, call |
| ts | datetime (UTC) | NaT is flagged, not deleted |
| store_id | str | joined to the store master |
| region | str | from the store master |
| text_raw | str | untouched original, kept for audit |
| text_masked | str | PII-masked raw text; the only text the UI and briefs show |
| text_norm | str | normalized copy used by models and rules |
| rating | float | review and app channels, else null |
| lang_pattern | str | english / hinglish / romanized_tamil / romanized_marathi / mixed / native_script; error analysis only |
| is_truncated | bool | per-channel length cap or trailing '...' |
| has_store, has_ts | bool | the radar uses only rows where both are true |
| is_synthetic | bool | true only for generated demo data |

## Synthetic demo data (v2)

- ~46k records, 50 stores (three sizes + one 5.0-size decoy), 4 regions, 120 days
  (2026-05-01 → 2026-08-28, UTC), 30 issue types, 5 owning functions.
- Channel styles: reviews mostly English/Hinglish; app comments with emojis; staff notes
  short with prefixes; call transcripts longer, code-mixed, some truncated.
- ~6% truncated at the channel caps (review 180, app 110, staff_note 120, call 280),
  ~8% typos, ~15% emojis, ~5% duplicates, ~3% cross-channel groups.
- **Planted incidents (the team's own, not the organizers' seeded ones):**
  1. cold_chain_failure at S07 — ramping over 6 days across review/staff_note/call
     (the radar must fire early).
  2. allergen_mislabel at S21 — only ~3 reports over 5 days in 2 channels
     (the policy tier must fire on the first report; volume is irrelevant).
  3. rude_service at S34 — steady for 7 days, mostly app + review.
- **Decoy:** S09, a 5.0-size store with a high but *normal* out-of-stock rate. It must
  never alert — proof that volume is normalized.
- **National rise:** app-crash complaints grow ~4.5x across all stores over the period
  (convex). No single store fires; it shows as a multi-store/national pattern.
- `data/synthetic/truth.parquet` and `ground_truth_incidents.json` are the team's own
  labels for honest SYNTHETIC-tagged evaluation. The pipeline never reads them
  (enforced by tests/test_no_label_leakage.py).

## Radar definitions

- Series: unique duplicate groups (S1+S2) with `p1 >= radar.min_conf`, store + time present.
- Exposure proxy E: the store's total unique reports in the window (documented stand-in
  for footfall; replace with real visits/transactions if organizers supply them).
- Windows: recent W = 3 days, baseline L = 28 days immediately before.
- Baseline rate λ = (K_past + α·π_c) / (E_past + α), empirical-Bayes shrinkage
  (α = 50) toward the global issue share π_c.
- Expected count μ = max(λ · E_recent · φ, μ_min), φ = 1.3 over-dispersion cushion,
  μ_min = 0.3 floor.
- Fire when k ≥ k_min (3) AND p = P(Poisson(μ) ≥ k) ≤ 0.001 AND k/μ ≥ 3, after a 14-day
  warm-up. Cooldown 7 days per (store, issue) episode.
- The detector is causal (tested): each report is judged with only records that existed
  at its moment.

## Alert object

alert_id (stable: E- or P- prefix + store + issue + first time), tier (emerging / policy
/ both), store_id, region, issue, severity, owner, cc, first_signal_ts, alert_ts,
n_reports, n_unique, channels, why (rule or trend numbers), evidence (up to 10 masked
records), confidence (heuristic: high/medium/low), uncertainty_notes, action,
escalation_rule, sla_hours, status (Detected → Reviewed → Assigned → Action taken →
Resolved), repeat_of.

## Final-day plug-in runbook (times are estimates)

| # | Action | Check | Time |
|---|---|---|---|
| 1 | Copy files into data/raw (keep a backup). Run the profiler | ~40k rows, four channels, dates plausible, ≥95% join to stores | 30 min |
| 2 | Confirm the auto mapping, set data_mode: real + timezone, run ingest | Low quarantine rate; missing store/ts rates understood | 15 min |
| 3 | Run the taxonomy matcher, review each match, draft routing.yaml | Every issue has owner + severity; mandatory categories flagged | 45 min |
| 4 | Policy check on real text: review 50 hits, add ≤3 patterns per category | Negated and real cases handled | 20 min |
| 5 | Grow the normalization dictionary from unknown_tokens.txt | Top spelling variants merged | 30 min |
| 6 | Hand-label ~150 records in the Label Tool | dev_labels.csv has 150 rows | 60 min |
| 7 | Run the full pipeline | Every step prints its counts | 45 min |
| 8 | Check radar alert volume on real data; tighten one notch if needed (never tune against evaluate.py) | Sensible alerts per store-week | 20 min |
| 9 | Read evaluate.py, fill the evaluate block in config, export, run once, log it | One logged run | 30 min |
| 10 | Review top alerts and the brief, rehearse, re-record if required | Demo runs on real data | 60 min |

Fallbacks: fuzzy store-name matching if ids don't join; day granularity if timestamps
are dates only; Scenario A (supervised) if a labeled sample appears; M1 TF-IDF-only if
time runs out; config-only changes for evaluate.py formats.
