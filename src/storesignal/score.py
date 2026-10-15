"""Score step: predictions + policy scan + semantic net + severity +
actionability + entities + dedupe/fusion, merged into records_scored.parquet."""
import json

import joblib
import numpy as np
import pandas as pd

from . import classify, dedupe, fuse, semantic
from .config import ROOT, cfg, load_entities, load_policy, load_taxonomy
from .policy import PolicyEngine

SEV_MAP = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}


def run():
    interim = ROOT / cfg['paths']['interim']
    processed = ROOT / cfg['paths']['processed']
    processed.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(interim / 'records_norm.parquet')
    E = np.load(interim / 'embeddings.npy')
    assert len(df) == len(E), 'embeddings and records_norm rows do not align'
    bundle = joblib.load(ROOT / 'models' / 'clf.joblib')
    model, tau = bundle['model'], bundle['tau']

    tax = load_taxonomy()
    fam = fuse.family_map(tax)
    sev_default = {it['id']: it['default_severity'] for it in tax['issues']}
    spec = load_policy()

    # ---- 1. predictions ----
    texts = df['text_norm'].tolist()
    pred = classify.predict(model, texts, E)
    df['issue'] = pred['issue'].tolist()
    df['p1'] = pred['p1'].round(4).tolist()
    df['issue2'] = pred['issue2'].tolist()
    df['p2'] = pred['p2'].round(4).tolist()
    df['margin'] = pred['margin'].round(4).tolist()

    # ---- 2. policy scan (runs on every record, independent of the model) ----
    engine = PolicyEngine()
    rows = []
    for i, t in enumerate(texts):
        for h in engine.scan(t):
            rows.append({'record_id': df.at[i, 'record_id'], 'category': h['category'],
                         'pattern': h['pattern'], 'span': h['span'], 'negated': h['negated']})
    hits = pd.DataFrame(rows)
    hits = hits.merge(df[['record_id', 'ts', 'store_id', 'channel', 'text_masked']],
                      on='record_id', how='left')
    hits.to_parquet(processed / 'policy_hits.parquet')

    non_neg = hits[~hits['negated']]
    policy_cats = non_neg.groupby('record_id')['category'].agg(lambda s: sorted(set(s)))
    policy_flag = df['record_id'].isin(set(non_neg['record_id']))
    all_hit_ids = set(hits['record_id'])
    df['policy_flag'] = policy_flag
    df['policy_weak'] = df['record_id'].isin(all_hit_ids) & ~policy_flag
    cats_raw = df['record_id'].map(policy_cats).fillna('[]')
    df['policy_cats'] = cats_raw.map(
        lambda v: json.dumps(sorted(v)) if isinstance(v, (list, set)) else v)

    # ---- 3. semantic safety net (review queue only) ----
    sem = semantic.semantic_flags(E, texts, percentile=cfg['semantic']['percentile'],
                                  skip_rows=df['policy_flag'].tolist())
    df['semantic_flag'] = sem['semantic_flag'].tolist()
    df['semantic_category'] = sem['semantic_category'].tolist()

    # ---- 4. severity ----
    floor_map = {cat: v['severity_floor'] for cat, v in spec['categories'].items()}
    cats = df['policy_cats'].map(json.loads)
    df['policy_floor'] = cats.map(
        lambda cs: max((SEV_MAP[floor_map[c]] for c in cs if c in floor_map), default=0))
    df['severity'] = [
        classify.severity(sev_default.get(iss, 'medium'),
                          {0: None, 1: 'medium', 2: 'high', 3: 'critical'}.get(floor),
                          rating, text)
        for iss, floor, rating, text in zip(df['issue'], df['policy_floor'], df['rating'], texts)
    ]

    # ---- 5. actionability ----
    df['actionable'] = [classify.actionable_heuristic(t, p) for t, p in zip(texts, df['p1'])]

    # ---- 6. uncertainty ----
    df['needs_review'] = (df['p1'] < tau) | (df['margin'] < 0.1)

    # ---- 7. entities and family ----
    compiled = dedupe.compile_entities()
    df['entities'] = [json.dumps(dedupe.extract_entities(t, compiled)) for t in texts]
    df['family'] = df['issue'].map(fam).fillna('')

    # ---- 8. dedupe + fusion (store+time rows only) ----
    use = df['has_store'] & df['has_ts']
    sub = df.loc[use].copy()
    sub = dedupe.assign_groups(sub, E[use.tolist()],
                               win_h=cfg['dedupe']['win_h'], cos_dup=cfg['dedupe']['cos_dup'],
                               fuzz_dup=cfg['dedupe']['fuzz_dup'],
                               incident_gap_h=cfg['dedupe']['incident_gap_h'],
                               max_span_h=cfg['dedupe'].get('max_span_h', 240))
    df['dup_group_id'] = ''
    df['incident_cluster_id'] = ''
    df.loc[use, 'dup_group_id'] = sub['dup_group_id'].tolist()
    df.loc[use, 'incident_cluster_id'] = sub['incident_cluster_id'].tolist()
    n_gap = (~use).sum()
    if n_gap:
        df.loc[~use, 'dup_group_id'] = ['dx%d' % i for i in range(n_gap)]
        df.loc[~use, 'incident_cluster_id'] = ['cx%d' % i for i in range(n_gap)]

    # ---- 9. policy_any propagation + canonical ----
    df = dedupe.propagate_policy(df)

    # ---- 10. write ----
    if 'is_synthetic' not in df.columns:
        df['is_synthetic'] = False
    df['_idx'] = np.arange(len(df))
    df.to_parquet(processed / 'records_scored.parquet')

    print('score: %d records scored' % len(df))
    print('  policy_flag=%d  policy_weak=%d  semantic_flag=%d  needs_review=%d'
          % (int(df['policy_flag'].sum()), int(df['policy_weak'].sum()),
             int(df['semantic_flag'].sum()), int(df['needs_review'].sum())))
    print('  dup groups=%d  incident clusters=%d  policy_any groups=%d'
          % (df['dup_group_id'].nunique(), df['incident_cluster_id'].nunique(),
             int(df.groupby('dup_group_id')['policy_any'].max().sum())))
    print('  severity: %s' % df['severity'].value_counts().to_dict())
    print('  actionable: %s' % df['actionable'].value_counts().to_dict())
