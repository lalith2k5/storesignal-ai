"""QA tool (§17): print N random policy flags per category for manual precision review.
Usage: python scripts/qa_policy_review.py [n_per_category]
"""
import sys
import pandas as pd

N = int(sys.argv[1]) if len(sys.argv) > 1 else 50

hits = pd.read_parquet('data/processed/policy_hits.parquet')[['record_id', 'category', 'negated']]
recs = pd.read_parquet('data/processed/records_scored.parquet')[['record_id', 'text_masked']]
df = hits.merge(recs, on='record_id', how='left')

for cat in sorted(df['category'].unique()):
    sub = df[(df['category'] == cat) & (~df['negated'])]
    sub = sub.sample(min(N, len(sub)), random_state=42)
    print(f"\n===== {cat} ({len(sub)} sampled / {(df['category'] == cat).sum()} total) =====")
    for i, r in enumerate(sub.itertuples(), 1):
        print(f"  [{i:02d}] {r.text_masked[:140]}")

print("\nReview each line as TP (truly a problem) or FP (false positive). Record precision per category in docs/qa_notes.md.")
