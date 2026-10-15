"""QA tool (guide section 17): sample non-negated policy hits per category
for manual precision review.

Usage:
    python scripts/qa_policy_review.py [n_per_category]

Writes reports/qa_policy_sample.txt. Open it, mark each line TP or FP,
record per-category precision in reports/qa_notes.md.
"""
import sys

import pandas as pd

from storesignal.config import ROOT

N = int(sys.argv[1]) if len(sys.argv) > 1 else 20

df = pd.read_parquet(ROOT / "data" / "processed" / "policy_hits.parquet")
df = df[["record_id", "category", "span", "negated", "text_masked"]]

lines = []
for cat in sorted(df["category"].unique()):
    sub = df[(df["category"] == cat) & (~df["negated"])]
    total = len(sub)
    sub = sub.sample(min(N, len(sub)), random_state=42)
    lines.append(f"\n===== {cat}  ({len(sub)} sampled / {total} total) =====")
    for i, r in enumerate(sub.itertuples(), 1):
        span = (getattr(r, "span", "") or "")[:30]
        text = (getattr(r, "text_masked", "") or "")[:160]
        lines.append(f"  [{i:02d}] match={span!r:30s}  text={text!r}")

out = ROOT / "reports" / "qa_policy_sample.txt"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("\n".join(lines))
print("\n".join(lines))
print(f"\nwrote {out}")
print("\nMark each line TP (truly a problem) or FP (false positive). "
      "Record per-category precision in reports/qa_notes.md.")
