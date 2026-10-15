"""Evidence-backed alerts: emerging (radar), policy (mandatory), or both.
Alert ids are built from store, issue and first time, so re-running the
pipeline produces the same ids and the tracker never creates duplicates."""
import json

import pandas as pd

from .config import ROOT, cfg, load_policy, load_routes, load_taxonomy
from .routing import route_for
from . import tracker


def emerging_alert(a, rec, route, W):
    lo = a['first_ts'] - pd.Timedelta(days=W)
    ev = rec[(rec['store_id'] == a['store_id']) & (rec['issue'] == a['issue'])
             & (rec['ts'] >= lo) & (rec['ts'] <= a['last_ts'])].sort_values('ts')
    return {
        'alert_id': 'E-%s-%s-%s' % (a['store_id'], a['issue'],
                                    a['first_ts'].strftime('%Y%m%d%H%M')),
        'tier': 'emerging', 'store_id': a['store_id'], 'issue': a['issue'],
        'owner': route['owner'], 'cc': route.get('cc', []), 'severity': route['severity'],
        'alert_ts': a['first_ts'], 'first_signal_ts': ev['ts'].min(),
        'n_reports': len(ev), 'n_unique': int(ev['dup_group_id'].nunique()),
        'channels': sorted(ev['channel'].unique()),
        'why': {'k': a['k'], 'expected': round(float(a['mu']), 2), 'ratio': round(float(a['ratio']), 1),
                'p': a['p_min'], 'window_days': W, 'pattern_id': a.get('pattern_id')},
        'evidence': ev[['record_id', 'channel', 'ts', 'text_masked']].head(10).to_dict('records'),
        'action': route['first_action'], 'escalation_rule': route['escalation_rule'],
    }


def policy_alerts(hits, rec, spec, gap_days=7):
    """One alert per store, category and episode (a gap of `gap_days` starts a new episode)."""
    # Pull from `rec` only the columns `hits` does not already have.
    needed = ['dup_group_id']
    for col in ('ts', 'store_id', 'channel', 'text_masked'):
        if col not in hits.columns:
            needed.append(col)
    h = hits.merge(rec[['record_id'] + needed],
                   on='record_id', how='inner').sort_values('ts')
    h['store_id'] = h['store_id'].fillna('UNKNOWN')
    out = []
    for (store, cat), g in h.groupby(['store_id', 'category'], sort=True):
        cur = []
        for r in g.itertuples():
            if cur and (r.ts - cur[-1].ts).days > gap_days:
                out.append(_policy_alert(store, cat, cur, spec))
                cur = []
            cur.append(r)
        if cur:
            out.append(_policy_alert(store, cat, cur, spec))
    return out


def _policy_alert(store, cat, rows, spec):
    pc = spec['categories'][cat]
    chans = sorted({r.channel for r in rows})
    return {
        'alert_id': 'P-%s-%s-%s' % (store, cat, rows[0].ts.strftime('%Y%m%d%H%M')),
        'tier': 'policy', 'store_id': store, 'issue': cat, 'owner': pc['owner'], 'cc': pc.get('cc', []),
        'severity': pc['severity_floor'], 'alert_ts': rows[0].ts,
        'n_reports': len(rows), 'n_unique': len({r.dup_group_id for r in rows}), 'channels': chans,
        'why': {'policy_category': cat, 'matched': sorted({r.span for r in rows}),
                'corroborated': len(chans) > 1},
        'evidence': [{'record_id': r.record_id, 'channel': r.channel, 'ts': r.ts,
                      'text_masked': r.text_masked} for r in rows[:10]],
        'escalation_rule': 'MANDATORY POLICY [' + cat + ']: ' + pc['escalation'],
        'note': 'Needs human review. Unverified report.',
    }


def _confidence(a):
    n_ch = len(a['channels'])
    p = a['why'].get('p', 1.0) if a['why'].get('p') is not None else 1.0
    policy = a['tier'] in ('policy', 'both')
    if n_ch >= 2 and (policy or p <= 1e-5):
        return 'high'
    if n_ch >= 2 or p <= 1e-4:
        return 'medium'
    return 'low'


def run():
    processed = ROOT / cfg['paths']['processed']
    rec = pd.read_parquet(processed / 'records_scored.parquet')
    rec['ts'] = pd.to_datetime(rec['ts'])
    radar_alerts = json.load(open(processed / 'radar_alerts.json', encoding='utf-8'))
    hits = pd.read_parquet(processed / 'policy_hits.parquet')
    routes = load_routes()
    policy_spec = load_policy()
    tax = load_taxonomy()
    issue_name = {it['id']: it['name'] for it in tax['issues']}
    family = {it['id']: it.get('family', '') for it in tax['issues']}
    W = cfg['radar']['window_days']

    # ---- emerging alerts ----
    alerts = []
    rec_ids = set(rec['record_id'])
    for a in radar_alerts:
        a = {**a, 'first_ts': pd.Timestamp(a['first_ts']), 'last_ts': pd.Timestamp(a['last_ts'])}
        lo = a['first_ts'] - pd.Timedelta(days=W)
        ev = rec[(rec['store_id'] == a['store_id']) & (rec['issue'] == a['issue'])
                 & (rec['ts'] >= lo) & (rec['ts'] <= a['last_ts'])]
        cats = sorted({c for cs in ev['policy_cats'].map(json.loads).tolist() for c in cs})
        route = route_for(a['issue'], cats, routes, policy_spec)
        al = emerging_alert(a, rec, route, W)
        al['policy_cats'] = cats
        al['tier'] = 'both' if cats else 'emerging'
        al['confidence'] = _confidence(al)
        al['explanation'] = ('%s at store %s: %d unique reports in %d days versus about %s expected '
                             '(%sx, p=%s). Channels: %s. Possible common %s issue, cause not confirmed.'
                             % (issue_name.get(a['issue'], a['issue']), a['store_id'], al['n_unique'],
                                W, al['why']['expected'], al['why']['ratio'], al['why']['p'],
                                ', '.join(al['channels']) or 'none',
                                family.get(a['issue'], 'operational')))
        al['uncertainty_notes'] = []
        alerts.append(al)

    # ---- policy alerts (non-negated hits only) ----
    non_neg = hits[~hits['negated']]
    for al in policy_alerts(non_neg, rec, policy_spec):
        al['confidence'] = _confidence(al)
        matched = ', '.join(al['why']['matched'][:6])
        al['explanation'] = ('Policy match [%s] on: %s. %d report(s) across %d channel(s). '
                             'Needs human review, unverified. Escalation rule: %s.'
                             % (al['issue'], matched, al['n_reports'], len(al['channels']),
                                al['escalation_rule']))
        al['uncertainty_notes'] = ['Unverified customer/staff report', 'Needs human review']
        alerts.append(al)

    # ---- enrich: region, SLA, repeat detection, tracker ----
    store_region = dict(zip(rec['store_id'].astype(str), rec['region'].astype(str)))
    con = tracker.connect()
    con = tracker.init_db(con)
    existing = {r[0]: r[1] for r in con.execute('SELECT alert_id, status FROM alerts').fetchall()}
    resolved = {r[0]: r[1] for r in con.execute(
        "SELECT alert_id, alert_ts FROM alerts WHERE status='Resolved'").fetchall()}
    n_new = 0
    for al in alerts:
        al['region'] = store_region.get(str(al['store_id']), 'Unknown')
        route_all = routes['routes'].get(al['issue'], routes['default'])
        sla = route_all.get('sla_hours', 72)
        al['sla_hours'] = sla
        # repeat: same store and issue as a Resolved alert in the last 30 days
        repeats = [aid for aid, ats in resolved.items()
                   if aid.rsplit('-', 2)[0] == ('%s-%s' % (al['store_id'], al['issue']))
                   and pd.Timestamp(ats) >= al['alert_ts'] - pd.Timedelta(days=30)]
        if repeats:
            al['repeat_of'] = repeats[0]
        if al['alert_id'] in existing:
            continue  # idempotent: never re-insert
        tracker.upsert_alert(con, al)
        n_new += 1

    # explanation + uncertainty polish
    for al in alerts:
        notes = list(al.get('uncertainty_notes', []))
        notes.append('Exposure proxy: store total feedback volume (no visit counts available)')
        al['uncertainty_notes'] = notes
        if 'action' not in al:
            al['action'] = routes['routes'].get(al['issue'], routes['default'])['first_action']

    with open(processed / 'alerts.json', 'w', encoding='utf-8') as f:
        json.dump(alerts, f, indent=2, default=str)
    print('alerts: %d alerts built (%d new in tracker)'
          % (len(alerts), n_new))
    print('  tiers: %s' % pd.Series([a['tier'] for a in alerts]).value_counts().to_dict())
    print('  confidence: %s' % pd.Series([a['confidence'] for a in alerts]).value_counts().to_dict())
