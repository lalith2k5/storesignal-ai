import numpy as np
import pandas as pd

from storesignal.config import cfg
from storesignal.radar import run_radar


def keys(alerts, cut=None):
    return {(a['store_id'], a['issue'], a['first_ts']) for a in alerts
            if cut is None or a['first_ts'] <= cut}


def test_radar_is_causal(sample_groups):
    p = cfg['radar']
    cut = sample_groups['ts'].quantile(0.6)
    early = run_radar(sample_groups[sample_groups['ts'] <= cut], p)
    full = run_radar(sample_groups, p)
    assert keys(early) == keys(full, cut)  # the future must not change the past


def test_radar_finds_planted(sample_groups):
    alerts = run_radar(sample_groups, cfg['radar'])
    assert any(a['store_id'] == 'S03' and a['issue'] == 'freezer_failure' for a in alerts)


def _frame(n_stores, days, per_day, issue, inject_store, inject_issue, inject_k, big_share=0.0):
    rng = np.random.default_rng(0)
    start = pd.Timestamp('2026-05-01', tz='UTC')
    rows = []
    i = 0
    for s in range(n_stores):
        for d in range(days):
            for _ in range(int(rng.poisson(per_day))):
                iss = inject_issue if (big_share and rng.random() < big_share) else issue
                ts = start + pd.Timedelta(days=d, hours=float(rng.uniform(0, 24)))
                rows.append({'store_id': 'S%d' % s, 'ts': ts, 'issue': iss, 'group_id': 'g%d' % i})
                i += 1
    for k in range(inject_k):
        ts = start + pd.Timedelta(days=days - 3) + pd.Timedelta(hours=6 * k)
        rows.append({'store_id': inject_store, 'ts': ts, 'issue': inject_issue, 'group_id': 'inj%d' % k})
    return pd.DataFrame(rows).sort_values('ts').reset_index(drop=True)


def test_radar_small_store():
    """The same raw count alerts in a tiny store but not in a big one."""
    p = cfg['radar']
    tiny = _frame(n_stores=1, days=60, per_day=2, issue='other_issue', inject_store='S0',
                  inject_issue='freezer_failure', inject_k=4)
    alerts_tiny = run_radar(tiny, p)
    assert any(a['store_id'] == 'S0' and a['issue'] == 'freezer_failure' for a in alerts_tiny)

    big = _frame(n_stores=1, days=60, per_day=30, issue='other_issue', inject_store='S0',
                 inject_issue='freezer_failure', inject_k=4, big_share=0.20)
    alerts_big = run_radar(big, p)
    assert not any(a['store_id'] == 'S0' and a['issue'] == 'freezer_failure' for a in alerts_big)


def test_decoy_quiet():
    """The large decoy store with a high but normal out-of-stock rate must not alert."""
    from storesignal import synth
    inc = [{'store': 'S01', 'issue': 'cold_chain_failure', 'start': 45, 'len': 5,
            'per_day': 2.0, 'channels': ['review', 'staff_note', 'call']}]
    df = synth.make(days=60, n_stores=12, incidents=inc, write=False).rename(columns={'true_issue': 'issue'})
    df['group_id'] = df['record_id']
    df = df.sort_values('ts').reset_index(drop=True)
    decoy = 'S09'
    assert df[(df['store_id'] == decoy) & (df['issue'] == 'out_of_stock')].shape[0] > 50
    alerts = run_radar(df, cfg['radar'])
    assert not any(a['store_id'] == decoy and a['issue'] == 'out_of_stock' for a in alerts)


def test_national_rise():
    """A slow national rise in app crashes fires no single-store alert but
    shows as a national trend (7-day rate vs prior 28-day rate)."""
    from storesignal import synth
    df = synth.make(days=60, n_stores=12, incidents=[], write=False).rename(columns={'true_issue': 'issue'})
    df['group_id'] = df['record_id']
    df = df.sort_values('ts').reset_index(drop=True)
    alerts = run_radar(df, cfg['radar'])
    assert not any(a['issue'] == 'app_crash' for a in alerts)

    app = df[df['issue'] == 'app_crash'].copy()
    app['day'] = app['ts'].dt.normalize()
    daily = app.groupby('day').size()
    last7 = daily[daily.index > daily.index.max() - pd.Timedelta(days=7)].sum() / 7
    prior28 = daily[(daily.index <= daily.index.max() - pd.Timedelta(days=7))
                    & (daily.index > daily.index.max() - pd.Timedelta(days=35))].sum() / 28
    assert last7 / prior28 >= 1.4
