# StoreSignal AI

**Turning store chatter into earlier, explainable, accountable action.**

StoreSignal AI is a multilingual retail operations early-warning and incident-resolution
intelligence system built for the R5 hackathon challenge (*"Turning Store Chatter Into
Action"*). It converts a messy, code-mixed, four-channel feedback stream (~40k records:
online reviews, in-app comments, staff shift notes, call-centre transcripts) into:

- a **weekly one-page regional brief** — top 5 issues, evidence quotes, affected stores,
  trend arrows, a safety-and-compliance box, emerging signals, actions due, caveats;
- **owner routing** — issue → owning function (Store Ops, Supply Chain, Merchandising,
  Digital, HR), severity, first action, escalation rule, SLA;
- an **Early-Warning Radar** — causal, store-specific, exposure-normalised detection of
  issues that are small in absolute volume but rising sharply at one store;
- a **safety-first policy guardrail** — allergen / hygiene / misconduct / physical-safety
  reports escalate regardless of volume, independently of any model score or dedupe step;
- **evidence-backed, explainable alerts** — every alert shows why it fired and quotes the
  source records;
- **honest evaluation** — classification quality, false-alert rate, precision statement
  with a Wilson interval, and a baseline comparison (radar vs simple volume rules).

## Status

**Demo-first build, complete and running end-to-end on synthetic data.** The organizers'
40k-record dataset, taxonomy, store master and `evaluate.py` arrive on the final day; the
four ⚠ DATA-DEPENDENT files (`adapters.py`, `evaluate_adapter.py`, `taxonomy.yaml`,
`routing.yaml`) plus the final-day runbook are designed so the real-data hookup is a short,
rehearsed checklist. **Every synthetic number is labelled; no simulated figure is presented
as a measured result.**

## Quick start

```bash
make setup        # python3.11 -m venv .venv && install requirements && pip install -e .
make synth        # generate ~46k synthetic demo records (SYNTHETIC)
make all          # ingest -> normalize -> embed -> weak_labels -> train -> score -> radar -> alerts -> brief -> evaluate
make test         # pytest
make app          # streamlit run app/Home.py  →  http://localhost:8501
make reset-demo   # rebuild tracker + alerts for a repeatable demo
```

First `make all` downloads the embedding model (`intfloat/multilingual-e5-small`, ~0.5 GB)
and embeds ~46k texts (5–15 min on an M2; cached afterwards).

## Repository layout

```
config/          config.yaml, taxonomy.yaml (30 issues), routing.yaml, policy_rules.yaml,
                 normalization.yaml, entities.yaml, safety_prototypes.yaml
data/
  synthetic/     generated demo records + the team's own truth labels (pipeline never reads them)
  interim/       records.parquet, records_norm.parquet, embeddings.npy, weak_labels.parquet
  processed/     records_scored.parquet, policy_hits.parquet, radar_alerts.json,
                 alerts.json, tracker.sqlite
  labels_dev/    hand-labelled dev set (Label Tool), sample_ids.csv
models/          trained classifier (clf.joblib)
reports/         metrics.json, eval_log.csv, radar_grid.csv, briefs/, unknown_tokens.txt
src/storesignal/ the pipeline modules (each exposes run(); `cli.py` orchestrates)
app/             Streamlit UI: Home + Radar, Incidents, Brief, Trust, Label Tool
tests/           unit + integration tests (radar causality, decoy, national rise, ...)
```

## The pipeline

```
4 channels + store master ─► ingest/validate ─► normalize + PII mask ─► embeddings
  ─► weak labels (keywords + embedding prototypes) ─► hybrid classifier (TF-IDF + emb + LR)
  ─► policy engine (independent rules) ─► dedupe + incident fusion
  ─► causal early-warning radar ─► evidence-backed alerts + routing ─► SQLite tracker
  ─► regional briefs ─► evaluation + exports for the organizers' evaluate.py
```

Three separate mechanisms — **classifier** (statistics), **policy** (rules), **radar**
(trend) — and none of them can switch off another. Raw data is immutable; every derived
file rebuilds with one command.

## Honest limits (read me)

- Thresholds, run-times and hour estimates are **starting values**, tuned on the team's
  own dev set and injection trials — never on hidden evaluation labels.
- The Hinglish/Tamil/Marathi word lists are starter lists; grow them from
  `reports/unknown_tokens.txt` (ideally with a native speaker).
- The radar's lead-time comparison is the team's own measure (vs the simple 5-in-7-days
  rule); the organizers' lead time comes only from their `evaluate.py`.
- `data_mode: real` + the ⚠ files are the final-day hookup; the runbook is in
  `docs/data_dictionary.md`.

## Demo story (the three-minute arc)

Scattered signals → connected evidence → early warning → policy-aware escalation →
owner action → evaluation proof. One planted freezer failure at a small store ramps up
and the radar fires days before a simple volume rule; a single allergen report escalates
anyway (policy tier); a big decoy store with a high-but-normal out-of-stock rate stays
quiet (volume normalisation); a slow national app-crash rise shows as a multi-store
pattern, not a false single-store alert.
