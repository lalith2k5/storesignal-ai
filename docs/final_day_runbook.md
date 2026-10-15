# Final-Day Runbook — StoreSignal AI

**When to run:** only after the organizers hand over the real dataset,
taxonomy, store master, and evaluate.py. Do NOT run on synthetic data.

**Time budget:** 5–6 hours. **Hard stop:** 1 hour before the deadline.

## Readiness gates (verify now)

- G1 `inspect_data` runs on empty `data/raw/` ✓
- G2 `automap` runs ✓
- G3 `pytest tests/test_loader.py` → 3 passed ✓
- G4 `build_taxonomy` runs (errors without organizer taxonomy — expected) ✓
- G5 Offline embedding: `HF_HUB_OFFLINE=1 python -c "from sentence_transformers import SentenceTransformer; m=SentenceTransformer('intfloat/multilingual-e5-small'); print(m.get_embedding_dimension())"` → 384 ✓
- G6 `grep "cfg\['evaluate'\]" src/storesignal/evaluate_adapter.py` ✓
- G7 Timed rehearsal on synthetic — target ~2:15

## The 10 steps

1. **Back up + copy files + profile** (30 min)
   - `mkdir -p ~/hackathon_backup/pre-real-$(date +%Y%m%d_%H%M)`
   - `cp -r data/synthetic reports models/clf.joblib ~/hackathon_backup/pre-real-$(date +%Y%m%d_%H%M)/`
   - `cp -r <organizer files> data/raw/`
   - `.venv/bin/python -m storesignal.cli inspect`
   - **COPY, don't move. To revert: restore from the backup folder.**

2. **Confirm mapping, flip to real** (15 min)
   - `sed -i '' 's/^data_mode:.*/data_mode: real/' config/config.yaml` (macOS)
   - `.venv/bin/python -m storesignal.cli ingest`

3. **Taxonomy matcher, review** (45 min)
   - `cp <organizer taxonomy> data/raw/`
   - `.venv/bin/python -m storesignal.cli build_taxonomy`
   - Review every row of `reports/taxonomy_match.csv`
   - Owners always from their file — never ours

4. **Policy scan on real text** (20 min)
   - Sample 50 non-negated hits, add up to 3 patterns per category

5. **Normalization dictionary** (30 min)
   - `.venv/bin/python -m storesignal.cli normalize`
   - Group spelling variants from `reports/unknown_tokens.txt`

6. **Hand-label ~150 records** (60 min)
   - `.venv/bin/python -m storesignal.cli label_sample`
   - `make app` → Label Tool page

7. **Full pipeline** (45 min)
   - `time make all`

8. **Radar sanity** (20 min)
   - Check `reports/metrics.json` → `radar.false_alerts.per_store_week`
   - If > 0.10: `radar.p_thr: 1e-4`, rerun `alerts` only
   - **Never tune against evaluate.py**

9. **Read + run evaluate.py once** (30 min)
   - Read `head -60` and the arg parser
   - Fill `config.yaml`'s `evaluate:` block with real column names
   - `.venv/bin/python -m storesignal.cli evaluate`
   - Run their script, tee to `reports/eval_runs/<timestamp>.txt`
   - Log in `reports/eval_log.csv`

10. **Review + demo** (60 min)
    - Top 20 alerts by severity
    - Walk all 6 Streamlit pages
    - Re-record if numbers changed

## Fallbacks

| Situation | Action |
|---|---|
| Store IDs don't join | Fuzzy-match name, mark UNKNOWN, exclude from radar |
| Dates only (no time) | `radar.window_days: 5`, report lead time in days |
| Labelled sample provided | Scenario A: supervised training |
| evaluate.py wants other columns | Change only `evaluate:` block + adapter |
| Out of time | Protect: ingest → normalize → score (M1) → radar → alerts → brief |

## One rule that overrides everything

Do NOT tune against `evaluate.py`. Every run must be logged in
`reports/eval_log.csv`.
