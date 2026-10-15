"""QA tool (§17): print N random incident clusters for eyeball review.
Usage: python scripts/qa_cluster_sample.py [n_clusters]
"""
import sys
import pandas as pd

N = int(sys.argv[1]) if len(sys.argv) > 1 else 30

df = pd.read_parquet('data/processed/records_scored.parquet')
sizes = df.groupby('incident_cluster_id').size()
eligible = sizes[sizes >= 2].index.tolist()
import numpy as np
rng = np.random.default_rng(42)
sample = rng.choice(eligible, size=min(N, len(eligible)), replace=False)

print(f"Sampled {len(sample)} of {len(eligible)} clusters with >=2 members.\n")
for cid in sample:
    members = df[df['incident_cluster_id'] == cid].sort_values('ts')
    print(f"===== cluster {cid}  n={len(members)}  channels={sorted(members['channel'].unique())} =====")
    for r in members.itertuples():
        print(f"  [{r.channel:11}] {r.ts} {r.text_masked[:100]}")
    print()
