# Judge Q&A Cheat Sheet

See `reports/metrics.json` for every number. See `reports/qa_notes.md`
for the honesty log. Every claim below has a file and a command.

## On the design
- Why not an LLM? — Templates + number checker; auditable; brief generator
  cannot invent a figure.
- Why three mechanisms? — Classifier (meaning), policy (safety),
  radar (trend). None can switch off another.
- Big stores? — Own-history baseline, exposure proxy, empirical-Bayes shrinkage.

## On the numbers
- False alarm rate: 0.0427/store-week, 40x24 injection grid.
- Policy precision (0.7827) < emerging (0.9394) by design. Both reported.
- Did you use hidden labels? — No. Dev set + synthetic injection. Every
  evaluate.py run is logged.

## On the honest misses
- S21 allergen: radar missed (k<3 in 3-day window), policy caught on first
  report. Complementary by design.
- S34 fired 11.8h later than B3: trade for zero alerts on the decoy store.
- Weak language slices: romanized Tamil 0.44, Marathi 0.31, mixed 0.28.
  Fix is more dev data, more normalization variants.
- Severity F1 dropped 4.7 pt after policy fix: +10 pt precision trade.
  Documented in reports/qa_notes.md.

## On operations
- Scale: radar is O(records), embeddings are batch. Postgres swap optional.
- Privacy: PII masked pre-model. No external APIs.
- New store: empirical-Bayes prior covers it; limited-history note in warm-up.

## On the demo
- Synthetic data, tagged everywhere. Real data on the final day.
- Official lead time only from the organizers' evaluate.py.
