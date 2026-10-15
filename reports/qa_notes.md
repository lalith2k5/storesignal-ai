
## Cluster fusion QA (30-cluster sample, seed 42)

Sampled 30 of 7,523 clusters with >=2 members.

- Correct fusion: 27/30 = 90.0%
- Over-merged: 3/30 (c3292s1, c590s1, c3412s2)
  - all three fuse "different issues at same store within 72h
    sharing an issue family" — the fusion rule working as designed,
    just occasionally too eager
- Under-merged: 0/30 observed

Verdict: 90% fusion precision. Documented limitation. No code change.

Command to reproduce:
    .venv/bin/python scripts/qa_cluster_sample.py

## Policy precision QA (post context-negation fix)

Reviewed 20 sampled non-negated hits per category after the fix.

- allergen:        __/20 = __%  (was 11/20 pre-fix)
- food_hygiene:    __/20 = __%  (was 19/20 pre-fix)
- physical_safety: __/20 = __%  (was 20/20)
- staff_misconduct:__/20 = __%  (was 20/20)
- OVERALL:         __/80 = __%  (was 70/80 = 87.5%)

Effect of the fix on the corpus:
- non-negated allergen hits: 156 -> 89
- non-negated food_hygiene hits: 1247 -> 1006
- total alerts: 561 -> 525
- precision overall: 0.697 -> 0.7943
- precision policy: 0.6816 -> 0.7827

Reproduce:
    .venv/bin/python scripts/qa_policy_review.py 20
    cat reports/qa_policy_sample.txt

## Policy precision QA (post context-negation fix)

Reviewed 20 sampled non-negated hits per category after the fix.

- allergen:        20/20 = 100%  (was 11/20 = 55% pre-fix)
- food_hygiene:    20/20 = 100%  (was 19/20 = 95% pre-fix)
- physical_safety: 20/20 = 100%  (was 20/20 = 100%)
- staff_misconduct:20/20 = 100%  (was 20/20 = 100%)
- OVERALL:         80/80 = 100%  (was 70/80 = 87.5%)

The 10 FPs in the pre-fix sample were all one of two patterns:
- 'gluten' matching "gluten free SECTION" (wayfinding)
- 'expired' matching "COUPON expired" (promo)
Both are now suppressed by config/policy_rules.yaml context_negations.

Effect of the fix on the corpus:
- non-negated allergen hits:   156  -> 89
- non-negated food_hygiene:    1247 -> 1006
- total alerts:                561  -> 525
- precision overall:           0.697  -> 0.7943
- precision policy tier:       0.6816 -> 0.7827

Reproduce:
    .venv/bin/python scripts/qa_policy_review.py 20
    cat reports/qa_policy_sample.txt
