"""Regional weekly brief (R5 outputs 1 and 2): one page per region with top 5
issues, evidence quotes, affected stores, trend arrows, the safety box,
emerging signals, actions due, and data caveats. Every number is traceable
to a facts dictionary; a checker rejects invented numbers."""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from jinja2 import Template
from markdown import markdown

from . import tracker
from .config import ROOT, cfg, load_routes, load_taxonomy

SEV_RANK = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}
TEMPLATE = """# {{ region }} region — week of {{ week_start }}

Data: {{ n_records }} reports · {{ n_stores }} stores · channels: {{ channels|join(', ') }} · {{ caveat_line }}

## This week
{% for b in summary %}- {{ b }}
{% endfor %}

## Top 5 issues
| # | Issue | Sev | Owner | Stores | Trend | Evidence | Rule and next action |
|---|---|---|---|---|---|---|---|
{% for i in top5 %}| {{ loop.index }} | {{ i.name }} | {{ i.severity }} | {{ i.owner }} | {{ i.stores|join(', ') }} | {{ i.trend }} | {% for ch, q in i.quotes %}{{ ch }}: “{{ q }}” {% endfor %}| {{ i.rule }} — {{ i.action }} |
{% endfor %}

## Safety and compliance (policy-triggered, needs human review)
{% if policy %}{% for a in policy %}- {{ a.store_id }} · {{ a.issue }} · {{ a.n_reports }} report(s) · owner {{ a.owner }} · {{ a.escalation_rule }}
{% endfor %}{% else %}- No open policy items this week.
{% endif %}

## Emerging signals
{% if emerging %}{% for a in emerging %}- {{ a.store_id }} · {{ a.issue }} · {{ a.why.k }} reports vs {{ a.why.expected }} expected ({{ a.why.ratio }}x) · {{ a.channels|join(', ') }}
{% endfor %}{% else %}- No emerging signals this week.
{% endif %}

## Actions due
{% if due %}{% for t in due %}- {{ t.alert_id }} · {{ t.owner }} · due {{ t.sla_due[:16] }}{% if t.overdue %} · OVERDUE{% endif %}
{% endfor %}{% else %}- No actions due.
{% endif %}

## Data caveats
{% for c in caveats %}- {{ c }}
{% endfor %}
"""


def week_bounds(ts, tz=None):
    """Monday 00:00 local time of the week containing ts."""
    tz = tz or cfg['timezone']
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize('UTC')
    loc = t.tz_convert(tz)
    start = loc.normalize() - pd.Timedelta(days=loc.weekday())
    return start, start + pd.Timedelta(days=7)


def trend(cur, prev, cur_total, prev_total, emerging):
    if emerging:
        return '▲▲'  # an emerging alert opened this week
    if prev == 0 and cur >= 3:
        return 'NEW'
    sc, sp = cur / max(cur_total, 1), prev / max(prev_total, 1)
    if sp > 0 and sc / sp >= 1.25 and cur - prev >= 2:
        return '▲'
    if sp > 0 and sc / sp <= 0.8 and prev - cur >= 2:
        return '▼'
    return '▬'


def pick_quotes(rows, E_rows=None, k=2):
    """Up to two reports per issue from different channels, closest to the
    cluster centroid. Masked text, cut to 140 chars, original language."""
    if E_rows is not None and len(E_rows) > 0:
        c = np.asarray(E_rows, dtype='float32').mean(axis=0)
        c = c / np.linalg.norm(c)
        order = np.argsort(-(np.asarray(E_rows, dtype='float32') @ c))
    else:
        order = np.arange(len(rows))
    chosen, seen = [], set()
    for i in order:
        r = rows.iloc[i]
        ch = r['channel']
        if ch in seen and len(seen) < rows['channel'].nunique():
            continue  # prefer a new channel first
        chosen.append((ch, str(r['text_masked'])[:cfg['brief']['quote_chars']]))
        seen.add(ch)
        if len(chosen) == k:
            break
    return chosen


def numbers(s):
    return set(re.findall(r'\d+(?:\.\d+)?', s))


def verify(text, facts):
    return numbers(text) <= numbers(json.dumps(facts, default=str))


def build_facts(rec, alerts, region, week_start, E=None):
    tz = cfg['timezone']
    week_end = week_start + pd.Timedelta(days=7)
    loc_ts = rec['ts'].dt.tz_convert(tz)
    wk = rec[(rec['region'] == region) & (loc_ts >= week_start) & (loc_ts < week_end)]
    prev_start = week_start - pd.Timedelta(days=7)
    prev = rec[(rec['region'] == region) & (loc_ts >= prev_start) & (loc_ts < week_start)]
    hist4 = rec[(rec['region'] == region) & (loc_ts >= week_start - pd.Timedelta(days=28))
                & (loc_ts < week_start)]

    routes = load_routes()['routes']
    tax = {it['id']: it for it in load_taxonomy()['issues']}
    default = load_routes()['default']

    # per-issue counts (canonical unique groups)
    cur_counts = wk[wk['canonical']].groupby('issue')['dup_group_id'].nunique()
    prev_counts = prev[prev['canonical']].groupby('issue')['dup_group_id'].nunique()
    hist_counts = hist4[hist4['canonical']].groupby('issue')['dup_group_id'].nunique()
    cur_total, prev_total = cur_counts.sum(), prev_counts.sum()

    # alerts: opened this week in region + open earlier alerts in region
    con = tracker.connect()
    con = tracker.init_db(con)
    open_rows = con.execute("SELECT * FROM alerts WHERE status != 'Resolved'").fetchall()
    cols = [d[0] for d in con.execute("SELECT * FROM alerts LIMIT 1").description]
    open_df = pd.DataFrame(open_rows, columns=cols)
    open_df['alert_ts'] = pd.to_datetime(open_df['alert_ts'])
    region_open = open_df[open_df['region'] == region]
    region_open['alert_ts_local'] = region_open['alert_ts'].dt.tz_convert(tz)
    opened_week = region_open[(region_open['alert_ts_local'] >= week_start)
                              & (region_open['alert_ts_local'] < week_end)]

    policy = region_open[region_open['tier'].isin(['policy', 'both'])]
    emerging = region_open[region_open['tier'].isin(['emerging', 'both'])]

    # emerging score per issue = largest -log10(p) among region's open emerging alerts
    escore = {}
    for a in emerging.to_dict('records'):
        payload = json.loads(a['payload_json'])
        p = payload['why'].get('p') or 1.0
        escore[a['issue']] = max(escore.get(a['issue'], 0.0), -np.log10(max(p, 1e-300)))

    policy_issue = set(policy['issue'])
    all_issues = sorted(set(cur_counts.index) | set(prev_counts.index) | set(policy_issue))
    ranked = []
    for iss in all_issues:
        cur = int(cur_counts.get(iss, 0))
        pr = int(prev_counts.get(iss, 0))
        h4 = int(hist_counts.get(iss, 0))
        share_now = cur / max(cur_total, 1)
        share_hist = h4 / max(hist_counts.sum(), 1)
        ranked.append({
            'issue': iss,
            'has_policy': iss in policy_issue,
            'severity_rank': SEV_RANK.get(routes.get(iss, default).get('severity', 'medium'), 1),
            'emerging_score': escore.get(iss, 0.0),
            'share_excess': round(share_now - share_hist, 4),
            'n_unique': cur,
            'n_prev': pr,
            'n_hist4': h4,
        })
    ranked.sort(key=lambda r: (r['has_policy'], r['severity_rank'], r['emerging_score'],
                               r['share_excess'], r['n_unique']), reverse=True)
    top5 = []
    for r in ranked[:cfg['brief']['top_n']]:
        if r['n_unique'] == 0 and r['has_policy'] is False:
            continue
        ev = wk[(wk['issue'] == r['issue']) & wk['canonical']]
        if len(ev) == 0:
            ev = prev[prev['issue'] == r['issue']]
        E_rows = None
        if E is not None and len(ev):
            E_rows = E[ev['_idx'].tolist()]
        affected = ev[ev['canonical']].groupby('store_id')['dup_group_id'].nunique()
        affected = affected[affected >= 2].index.tolist()
        # include stores with an alert this week for this issue
        if len(opened_week):
            al_stores = opened_week[opened_week['issue'] == r['issue']]['store_id'].tolist()
            affected = sorted(set(affected) | set(al_stores))[:8]
        quotes = pick_quotes(ev, E_rows)
        t = trend(r['n_unique'], r['n_prev'], int(cur_total), int(prev_total),
                  r['emerging_score'] > 0)
        rt = routes.get(r['issue'], default)
        top5.append({
            'name': tax.get(r['issue'], {}).get('name', r['issue']),
            'severity': rt.get('severity', 'medium'),
            'owner': rt.get('owner', default['owner']),
            'stores': [str(s) for s in affected] or ['—'],
            'trend': t,
            'quotes': quotes,
            'rule': rt.get('escalation_rule', ''),
            'action': rt.get('first_action', ''),
        })

    # policy list for the safety box
    policy_list = []
    for a in policy.sort_values('alert_ts').to_dict('records'):
        payload = json.loads(a['payload_json'])
        policy_list.append({
            'store_id': a['store_id'], 'issue': a['issue'], 'n_reports': payload.get('n_reports', 1),
            'owner': a['owner'], 'escalation_rule': payload.get('escalation_rule', ''),
        })

    emerging_list = []
    for a in emerging.sort_values('alert_ts').to_dict('records'):
        payload = json.loads(a['payload_json'])
        emerging_list.append({
            'store_id': a['store_id'], 'issue': a['issue'],
            'why': payload.get('why', {}), 'channels': payload.get('channels', []),
        })

    # actions due / overdue
    due = []
    for a in region_open[region_open['status'].isin(['Detected', 'Reviewed', 'Assigned', 'Action taken'])].to_dict('records'):
        overdue = pd.Timestamp(a['sla_due']) < pd.Timestamp.now(tz='UTC')
        due.append({'alert_id': a['alert_id'], 'owner': a['owner'], 'sla_due': a['sla_due'],
                    'overdue': overdue})

    # caveats
    caveats = [
        'Exposure proxy: store total feedback volume; no visit or transaction counts available',
        '%.1f%% of region records sent to review (low confidence)' % (
            100 * wk['needs_review'].mean() if len(wk) else 0.0),
        '%.1f%% of region records missing store or timestamp' % (
            100 * (~(wk['has_store'] & wk['has_ts'])).mean() if len(wk) else 0.0),
        'Evidence quotes are masked, verbatim, and cut to %d characters' % cfg['brief']['quote_chars'],
    ]
    if hist_counts.sum() == 0:
        caveats.append('Limited history: fewer than four weeks of baseline data')

    # summary bullets from counts only
    n_policy = len(policy_list)
    n_emerging = len(emerging_list)
    n_overdue = sum(1 for t in due if t['overdue'])
    summary = [
        '%d report(s) this week from %d store(s); %d new alert(s) opened'
        % (len(wk), wk['store_id'].nunique(), len(opened_week)),
        '%d policy item(s) awaiting human review' % n_policy,
        '%d emerging signal(s) open in this region' % n_emerging,
        '%d overdue action(s)' % n_overdue,
    ]
    if n_policy:
        summary.append('Priority: policy items are never cut by the top-5 limit')

    facts = {
        'region': region, 'week_start': week_start.strftime('%Y-%m-%d'),
        'n_records': int(len(wk)), 'n_stores': int(wk['store_id'].nunique()),
        'channels': sorted(wk['channel'].unique().tolist()),
        'caveat_line': 'exposure-proxy caveats below',
        'summary': summary, 'top5': top5, 'policy': policy_list,
        'emerging': emerging_list, 'due': due, 'caveats': caveats,
        'cur_counts': {k: int(v) for k, v in cur_counts.items()},
        'prev_counts': {k: int(v) for k, v in prev_counts.items()},
    }
    return facts


def render(facts):
    out = Template(TEMPLATE).render(**facts)
    if not verify(out, facts):
        raise ValueError('brief contains a number not present in the facts')
    return out


def export(facts, md_text):
    reports = ROOT / cfg['paths']['reports'] / 'briefs'
    reports.mkdir(parents=True, exist_ok=True)
    name = '%s_%s' % (facts['region'], facts['week_start'])
    md_path = reports / (name + '.md')
    html_path = reports / (name + '.html')
    md_path.write_text(md_text, encoding='utf-8')
    css = '<style>@page { size: A4; margin: 12mm; } body { font: 10pt -apple-system, sans-serif; '
    css += 'max-width: 180mm; margin: 0 auto; } table { border-collapse: collapse; width: 100%; } '
    css += 'td, th { border: 1px solid #ccc; padding: 3px 5px; font-size: 9pt; } '
    css += 'h1 { font-size: 15pt; } h2 { font-size: 11pt; margin-top: 8px; }</style>'
    html_path.write_text(css + markdown(md_text, extensions=['tables']), encoding='utf-8')
    return md_path, html_path


def run():
    processed = ROOT / cfg['paths']['processed']
    rec = pd.read_parquet(processed / 'records_scored.parquet')
    rec['ts'] = pd.to_datetime(rec['ts'])
    alerts = json.load(open(processed / 'alerts.json', encoding='utf-8'))
    E = None
    emb_path = ROOT / cfg['paths']['interim'] / 'embeddings.npy'
    if emb_path.exists():
        E = np.load(emb_path)
    tz = cfg['timezone']
    loc = rec['ts'].dt.tz_convert(tz)
    last_full = week_bounds(loc.max(), tz)[0] - pd.Timedelta(days=7)
    weeks = [last_full - pd.Timedelta(days=7 * i) for i in range(cfg['brief']['weeks'])]
    regions = sorted(rec['region'].dropna().unique())
    n = 0
    for region in regions:
        for ws in weeks:
            facts = build_facts(rec, alerts, region, ws, E=E)
            if facts['n_records'] == 0 and len(facts['policy']) == 0:
                continue
            md_text = render(facts)
            md_path, html_path = export(facts, md_text)
            n += 1
            print('brief: %s (%d records, %d top issues, %d policy items)' %
                  (md_path.name, facts['n_records'], len(facts['top5']), len(facts['policy'])))
    print('brief: %d briefs written to reports/briefs/' % n)
