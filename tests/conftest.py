import pytest

from storesignal import synth


@pytest.fixture(scope='session')
def sample_groups():
    inc = [{'store': 'S03', 'issue': 'freezer_failure', 'start': 45, 'len': 5,
            'per_day': 2.0, 'channels': ['review', 'staff_note', 'call']}]
    df = synth.make(days=60, n_stores=8, incidents=inc).rename(columns={'true_issue': 'issue'})
    df['group_id'] = df['record_id']
    return df.sort_values('ts').reset_index(drop=True)


@pytest.fixture(scope='session')
def risers():
    """A full demo frame with the planted incidents, the decoy store and the
    national app-crash rise, labeled with the generator's own truth."""
    import json
    from storesignal.config import ROOT
    gt = json.load(open(ROOT / 'data' / 'synthetic' / 'ground_truth_incidents.json', encoding='utf-8'))
    inc = [{'store': g['store'], 'issue': g['issue'],
            'start': int((__import__('pandas').Timestamp(g['start_ts'])
                          - __import__('pandas').Timestamp('2026-05-01', tz='UTC')).days),
            'len': g['len'], 'per_day': 2.5 if g['issue'] == 'cold_chain_failure' else 2.0,
            'ramp': g['issue'] == 'cold_chain_failure',
            'channels': ['review', 'staff_note', 'call']}
           for g in gt]
    df = synth.make(days=60, n_stores=12, incidents=inc).rename(columns={'true_issue': 'issue'})
    df['group_id'] = df['record_id']
    return df.sort_values('ts').reset_index(drop=True)
