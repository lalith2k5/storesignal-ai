import json
from pathlib import Path

import pandas as pd
import pytest

from storesignal.alerts import _policy_alert, policy_alerts
from storesignal.config import ROOT, load_policy

PROCESSED = ROOT / 'data' / 'processed'


def test_policy_alert_structure():
    spec = load_policy()
    rows = [type('R', (), {'record_id': 'test_001', 'ts': pd.Timestamp('2026-06-01T10:00', tz='UTC'), 'channel': 'review',
                           'span': 'allergy', 'dup_group_id': 'd1',
                           'text_masked': 'my son had an allergy reaction'})()]
    a = _policy_alert('S07', 'allergen', rows, spec)
    assert a['tier'] == 'policy'
    assert a['owner'] == 'Supply Chain'
    assert a['severity'] == 'critical'
    assert 'MANDATORY POLICY [allergen]' in a['escalation_rule']
    assert a['n_reports'] == 1


def test_policy_episode_split_on_gap():
    spec = load_policy()
    base = pd.Timestamp('2026-06-01T10:00', tz='UTC')
    hits = pd.DataFrame([
        {'record_id': 'a-1', 'category': 'food_hygiene', 'span': 'keeda', 'negated': False},
        {'record_id': 'a-2', 'category': 'food_hygiene', 'span': 'cockroach', 'negated': False},
        {'record_id': 'a-3', 'category': 'food_hygiene', 'span': 'rat', 'negated': False},
    ])
    rec = pd.DataFrame({
        'record_id': ['a-1', 'a-2', 'a-3'],
        'store_id': ['S1', 'S1', 'S1'],
        'ts': [base, base + pd.Timedelta(days=1), base + pd.Timedelta(days=10)],
        'channel': ['review', 'app', 'review'],
        'text_masked': ['x', 'y', 'z'],
        'dup_group_id': ['d1', 'd2', 'd3'],
    })
    alerts = policy_alerts(hits, rec, spec, gap_days=7)
    assert len(alerts) == 2  # the day-10 hit starts a new episode


@pytest.mark.skipif(not (PROCESSED / 'alerts.json').exists(),
                    reason='pipeline artifacts missing; run `python -m storesignal.cli all` first')
def test_alerts_idempotent():
    from storesignal import alerts as alerts_mod
    first = json.load(open(PROCESSED / 'alerts.json', encoding='utf-8'))
    alerts_mod.run()
    second = json.load(open(PROCESSED / 'alerts.json', encoding='utf-8'))
    assert [a['alert_id'] for a in first] == [a['alert_id'] for a in second]
