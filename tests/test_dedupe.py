import json

import numpy as np
import pandas as pd

from storesignal import dedupe


def _frame():
    ts = pd.Timestamp('2026-05-10', tz='UTC')
    rows = [
        # exact duplicate pair (same store + text)
        {'store_id': 'S1', 'ts': ts, 'text_norm': 'freezer not cooling', 'family': 'cold_chain',
         'entities': json.dumps(['freezer']), 'policy_flag': False},
        {'store_id': 'S1', 'ts': ts + pd.Timedelta(hours=1), 'text_norm': 'freezer not cooling',
         'family': 'cold_chain', 'entities': json.dumps(['freezer']), 'policy_flag': True},
        # same family, close in time, similar meaning -> incident cluster
        {'store_id': 'S1', 'ts': ts + pd.Timedelta(hours=20), 'text_norm': 'fridge temperature high',
         'family': 'cold_chain', 'entities': json.dumps(['fridge']), 'policy_flag': False},
        # different store: no grouping
        {'store_id': 'S2', 'ts': ts, 'text_norm': 'freezer not cooling', 'family': 'cold_chain',
         'entities': json.dumps(['freezer']), 'policy_flag': False},
    ]
    return pd.DataFrame(rows)


def test_duplicates_collapse_and_policy_any_propagates():
    df = _frame()
    n = len(df)
    # two close/similar vectors for the fusion pair, others distinct
    E = np.array([[1, 0, 0], [0.99, 0.14, 0], [0.97, 0.24, 0], [0, 1, 0]], dtype='float32')
    E = E / np.linalg.norm(E, axis=1, keepdims=True)
    out = dedupe.assign_groups(df, E)
    assert out.loc[0, 'dup_group_id'] == out.loc[1, 'dup_group_id']  # exact dup
    assert out.loc[0, 'incident_cluster_id'] == out.loc[2, 'incident_cluster_id']  # fusion
    assert out.loc[3, 'dup_group_id'] != out.loc[0, 'dup_group_id']  # other store untouched

    out = dedupe.propagate_policy(out)
    g0 = out.loc[0, 'dup_group_id']
    assert bool(out[out['dup_group_id'] == g0]['policy_any'].max())
    assert out.loc[out['dup_group_id'] == g0, 'canonical'].sum() == 1


def test_entities_extraction():
    compiled = dedupe.compile_entities()
    ents = dedupe.extract_entities('the freezer in aisle 3 broke, batch #B77 affected', compiled)
    assert 'freezer' in ents
    assert 'batch:B77' in ents
