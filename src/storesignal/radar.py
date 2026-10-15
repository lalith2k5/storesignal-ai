"""Early-Warning Radar (the signature feature).

For every store and issue, asks: is the number of unique reports in the last
few days unusually high compared with this store's own history, given how
much feedback this store normally receives? Evaluated causally: each new
report is judged using only the records that existed at that moment.
"""
import json
from bisect import bisect_right
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy.stats import poisson

from .config import ROOT, cfg

DAY = pd.Timedelta(days=1)


def _count(lst, lo, hi):
    return bisect_right(lst, hi) - bisect_right(lst, lo)  # items with lo < t <= hi


def run_radar(df, p):
    """df: unique report groups sorted by ts, columns ts, store_id, issue, group_id.
    p: the radar config dict. Causal: row i is judged using only rows 0..i."""
    day = pd.Timedelta(days=1)
    t0 = df['ts'].min()
    ev, st, gl, allv = defaultdict(list), defaultdict(list), defaultdict(list), []
    n_issues = df['issue'].nunique()
    W, L = p['window_days'], p['lookback_days']
    open_alerts, alerts = {}, []
    for row in df.itertuples():
        t = (row.ts - t0) / day  # float days since the first record
        s, c = row.store_id, row.issue
        ev[(s, c)].append(t)
        st[s].append(t)
        gl[c].append(t)
        allv.append(t)
        k = _count(ev[(s, c)], t - W, t)
        if k < p['k_min'] or t < p['warmup_days']:
            continue
        e_rec = _count(st[s], t - W, t)
        k_past = _count(ev[(s, c)], t - W - L, t - W)
        e_past = _count(st[s], t - W - L, t - W)
        pi_c = (_count(gl[c], t - W - L, t - W) + 1) / (_count(allv, t - W - L, t - W) + n_issues)
        lam = (k_past + p['alpha'] * pi_c) / (e_past + p['alpha'])
        mu = max(lam * e_rec * p['phi'], p['mu_min'])
        pval = float(poisson.sf(k - 1, mu))
        if pval > p['p_thr'] or k / mu < p['ratio_min']:
            continue
        a = open_alerts.get((s, c))
        if a and t - a['last_t'] <= p['cooldown_days']:  # same episode: update, do not re-alert
            a.update(last_t=t, last_ts=row.ts, k=max(a['k'], k), p_min=min(a['p_min'], pval))
        else:
            a = {'store_id': s, 'issue': c, 'first_ts': row.ts, 'first_t': t, 'last_t': t,
                 'last_ts': row.ts, 'k': k, 'mu': mu, 'ratio': k / mu, 'p_min': pval}
            open_alerts[(s, c)] = a
            alerts.append(a)
    return alerts


# ------------------------------------------------------------------ baselines
def baseline_b3_fire(tss, k=5, days=7):
    """B3 fixed threshold: k reports of one issue at one store within `days` days."""
    ts = sorted(tss)
    for i in range(k - 1, len(ts)):
        if ts[i] - ts[i - k + 1] <= pd.Timedelta(days=days):
            return ts[i]
    return None


def baseline_b1_national(daily_by_issue, issue, topn=5):
    """B1 national volume: first day the issue enters the weekly national top-N.
    daily_by_issue: DataFrame with columns ts, issue, group_id (one row per group)."""
    if daily_by_issue.empty:
        return None
    daily_by_issue = daily_by_issue.copy()
    daily_by_issue['day'] = daily_by_issue['ts'].dt.normalize()
    counts = (daily_by_issue.groupby(['day', 'issue']).size().reset_index(name='n'))
    days = sorted(counts['day'].unique())
    for i in range(6, len(days)):
        win = counts[(counts['day'] > days[i] - pd.Timedelta(days=7)) & (counts['day'] <= days[i])]
        tot = win.groupby('issue')['n'].sum().sort_values(ascending=False)
        if issue in tot.index[:topn]:
            return days[i]
    return None


def baseline_b2_zscore(weekly, z=3.0):
    """B2 raw store z-score on weekly store-issue counts, no exposure normalization.
    weekly: Series of weekly counts indexed by week start. Returns first week |z| >= z."""
    if len(weekly) < 4:
        return None
    mean, std = weekly.mean(), weekly.std(ddof=0)
    if std == 0:
        return None
    for wk, v in weekly.items():
        if (v - mean) / std >= z:
            return wk
    return None


# ------------------------------------------------------------ injection tuning
def inject(df, store, issue, start, n, days, ramp, rng):
    """Copy of df plus n extra reports of (store, issue) over `days` days from `start`."""
    pool = df[df['issue'] == issue]
    if pool.empty:
        return df
    u = rng.random(n)
    offs = np.sort(days * (np.sqrt(u) if ramp else u))  # sqrt(u): more events later = a ramp
    new = pool.sample(n, replace=True, random_state=int(rng.integers(1_000_000_000))).copy()
    new['store_id'] = store
    new['ts'] = start + pd.to_timedelta(offs, unit='D')
    new['group_id'] = ['inj-%s-%s-%d' % (store, issue, i) for i in range(n)]
    return pd.concat([df, new], ignore_index=True).sort_values('ts').reset_index(drop=True)


def injection_delay_hours(df, store, issue, start, n, days, ramp, params, rng):
    sl = df[(df['ts'] >= start - pd.Timedelta(days=params['lookback_days'] + 7))
            & (df['ts'] <= start + pd.Timedelta(days=days + 3))]
    sl = inject(sl, store, issue, start, n, days, ramp, rng)
    end = start + pd.Timedelta(days=days + 2)
    hits = [a for a in run_radar(sl, params)
            if a['store_id'] == store and a['issue'] == issue and start <= a['first_ts'] <= end]
    return min((a['first_ts'] - start).total_seconds() / 3600 for a in hits) if hits else None


def link_cross_store(alerts, days=7):
    pid = {}
    for c in {a['issue'] for a in alerts}:
        lst = sorted((a for a in alerts if a['issue'] == c), key=lambda a: a['first_ts'])
        for i, a in enumerate(lst):
            for b in lst[i + 1:]:
                if (b['first_ts'] - a['first_ts']).days > days:
                    break
                if b['store_id'] != a['store_id']:
                    tag = pid.get(id(a)) or 'pat-' + c + '-' + a['first_ts'].strftime('%Y%m%d')
                    pid[id(a)] = pid[id(b)] = tag
    for a in alerts:
        a['pattern_id'] = pid.get(id(a))
    return alerts


def forecast_next(daily, h=3):
    y = np.log1p(np.asarray(daily[-7:], dtype=float))
    slope, icpt = np.polyfit(np.arange(len(y)), y, 1)
    return np.clip(np.expm1(icpt + slope * np.arange(len(y), len(y) + h)), 0, None)


def run():
    """Radar on the scored records. Causal detector over unique duplicate groups."""
    processed = ROOT / cfg['paths']['processed']
    df = pd.read_parquet(processed / 'records_scored.parquet')
    p = cfg['radar']
    keep = df['has_store'] & df['has_ts'] & df['canonical'] & (df['p1'] >= p['min_conf'])
    frame = df.loc[keep, ['ts', 'store_id', 'issue', 'dup_group_id']].rename(
        columns={'dup_group_id': 'group_id'}).copy()
    frame = frame.sort_values(['ts', 'group_id'], kind='stable').reset_index(drop=True)

    params = dict(p)
    span_days = (frame['ts'].max() - frame['ts'].min()) / DAY
    if span_days < params['warmup_days']:
        params['warmup_days'] = max(1.0, span_days / 3)
        print(f'radar: data span {span_days:.0f} days < warmup; warmup shortened to '
              f'{params["warmup_days"]:.0f} days')

    alerts = run_radar(frame, params)
    alerts = link_cross_store(alerts)
    out = []
    for a in alerts:
        out.append({**a, 'first_ts': a['first_ts'].isoformat(), 'last_ts': a['last_ts'].isoformat(),
                    'ratio': round(float(a['ratio']), 2), 'mu': round(float(a['mu']), 2)})
    with open(processed / 'radar_alerts.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2)

    n_stores = frame['store_id'].nunique()
    store_weeks = max(1.0, n_stores * (span_days - params['warmup_days']) / 7)
    print('radar: %d alerts on %d unique groups (%d stores)' % (len(out), len(frame), n_stores))
    print('radar: %.3f alerts per store-week (calibration window)' % (len(out) / store_weeks))
    print('radar: cross-store patterns: %d' %
          len({a.get('pattern_id') for a in out if a.get('pattern_id')}))


def tune(n_trials=40, n_jobs=-1):
    """Injection-based tuning (9.4). Plants ~n_trials incidents of size n=6 over
    3 days into copies of the data and scores each parameter grid point.
    Writes reports/radar_grid.csv. Never touches hidden labels."""
    from joblib import Parallel, delayed

    processed = ROOT / cfg['paths']['processed']
    df = pd.read_parquet(processed / 'records_scored.parquet')
    p0 = cfg['radar']
    keep = df['has_store'] & df['has_ts'] & df['canonical'] & (df['p1'] >= p0['min_conf'])
    frame = df.loc[keep, ['ts', 'store_id', 'issue', 'dup_group_id']].rename(
        columns={'dup_group_id': 'group_id'})
    frame = frame.sort_values('ts').reset_index(drop=True)

    grid = []
    for wd in [3, 5]:
        for km in [3, 4]:
            for pt in [1e-2, 5e-4, 1e-4]:
                for rm in [2.5, 3.0]:
                    params = {**p0, 'window_days': wd, 'k_min': km, 'p_thr': pt, 'ratio_min': rm}
                    grid.append((wd, km, pt, rm, params))

    counts = frame.groupby(['store_id', 'issue']).size()
    eligible = counts[counts >= 20]
    rng = np.random.default_rng(cfg['seed'])

    def trial(i):
        r = np.random.default_rng(1000 + i)
        store, issue = eligible.sample(1, random_state=1000 + i).index[0]
        start = frame['ts'].min() + pd.Timedelta(days=float(r.uniform(35, 80)))
        results = {}
        for wd, km, pt, rm, params in grid:
            d = injection_delay_hours(frame, store, issue, start, n=6, days=3,
                                      ramp=bool(i % 2), params=params, rng=r)
            results[(wd, km, pt, rm)] = d
        return results

    rows = Parallel(n_jobs=n_jobs, verbose=5)(delayed(trial)(i) for i in range(n_trials))
    out = []
    for (wd, km, pt, rm, params) in grid:
        delays = [r[(wd, km, pt, rm)] for r in rows]
        det = [d for d in delays if d is not None]
        out.append({'window_days': wd, 'k_min': km, 'p_thr': pt, 'ratio_min': rm,
                    'detection_rate': round(len(det) / len(delays), 3),
                    'median_delay_hours': round(float(np.median(det)), 1) if det else None,
                    'n_detected': len(det), 'n_trials': len(delays)})
    res = pd.DataFrame(out).sort_values(['detection_rate', 'median_delay_hours'],
                                        ascending=[False, True])
    reports = ROOT / 'reports'
    reports.mkdir(parents=True, exist_ok=True)
    res.to_csv(reports / 'radar_grid.csv', index=False)
    print(res.to_string(index=False))
    print(f'tune: saved reports/radar_grid.csv ({len(rows)} trials x {len(grid)} settings)')
