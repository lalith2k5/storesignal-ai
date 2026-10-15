"""Honest evaluation on the team's own data. Every value carries a source tag:
SYNTHETIC, DEV or EVALUATE.PY. The organizers' evaluate.py is run by hand and
logged -- it is never used to tune."""
import json

import pandas as pd

from . import evaluate_adapter, metrics
from .config import ROOT, cfg
from .radar import baseline_b3_fire


def _confusion(true, pred):
    """Return (labels, matrix) for a confusion matrix as nested list."""
    from sklearn.metrics import confusion_matrix
    labels = sorted(set(true) | set(pred))
    cm = confusion_matrix(true, pred, labels=labels)
    return labels, cm.tolist()


MANDATORY = {'food_hygiene', 'physical_safety', 'staff_misconduct', 'allergen_mislabel', 'expired_stock'}


def _planted_summary():
    """Detection results on the synthetic planted incidents (the team's own
    ground truth, not the organizers' seeded incidents)."""
    processed = ROOT / cfg['paths']['processed']
    gt_path = ROOT / 'data' / 'synthetic' / 'ground_truth_incidents.json'
    if not gt_path.exists():
        return None
    gt = json.load(open(gt_path, encoding='utf-8'))
    alerts = json.load(open(processed / 'radar_alerts.json', encoding='utf-8'))
    rec = pd.read_parquet(processed / 'records_scored.parquet')
    rec['ts'] = pd.to_datetime(rec['ts'])
    b = cfg['baselines']
    rows = []
    for inc in gt:
        start = pd.Timestamp(inc['start_ts'])
        end = start + pd.Timedelta(days=inc['len'])
        hits = [a for a in alerts if a['store_id'] == inc['store'] and a['issue'] == inc['issue']
                and start <= pd.Timestamp(a['first_ts']) <= end + pd.Timedelta(days=2)]
        delay = min((pd.Timestamp(a['first_ts']) - start).total_seconds() / 3600 for a in hits) if hits else None
        series = rec[(rec['store_id'] == inc['store']) & (rec['issue'] == inc['issue'])
                     & (rec['has_store'] & rec['has_ts']) & rec['canonical']]
        b3 = baseline_b3_fire(series['ts'].tolist(), k=b['b3_k'], days=b['b3_days'])
        b3_delay = (b3 - start).total_seconds() / 3600 if b3 is not None and b3 >= start else None
        rows.append({
            'incident': '%s@%s' % (inc['store'], inc['issue']),
            'detected': delay is not None,
            'delay_hours': round(delay, 1) if delay is not None else None,
            'b3_delay_hours': round(b3_delay, 1) if b3_delay is not None else None,
            'lead_vs_b3_hours': round(b3_delay - delay, 1) if (delay is not None and b3_delay is not None) else None,
        })
    return rows


def _false_alerts_per_store_week():
    processed = ROOT / cfg['paths']['processed']
    alerts = json.load(open(processed / 'radar_alerts.json', encoding='utf-8'))
    rec = pd.read_parquet(processed / 'records_scored.parquet')
    rec['ts'] = pd.to_datetime(rec['ts'])
    p = cfg['radar']
    span = (rec['ts'].max() - rec['ts'].min()) / pd.Timedelta(days=1)
    n_stores = rec['store_id'].nunique()
    store_weeks = max(1.0, n_stores * (span - p['warmup_days']) / 7)
    return {'alerts': len(alerts), 'per_store_week': round(len(alerts) / store_weeks, 4),
            'store_weeks': round(store_weeks, 1)}


def _precision_statement(rec, alerts):
    """R5 output 5. An alert is truly actionable when at least half of its
    evidence records are actionable. Hand verdicts from the Label Tool take
    priority; on synthetic data the generator's own truth is used and tagged."""
    verdict_path = ROOT / 'data' / 'labels_dev' / 'alert_verdicts.csv'
    truth_path = ROOT / 'data' / 'synthetic' / 'truth.parquet'
    if verdict_path.exists():
        v = pd.read_csv(verdict_path)
        label = {str(r['alert_id']): int(r['actionable']) for r in v.to_dict('records')}
        source = 'DEV-HAND-LABELS'
    elif truth_path.exists():
        truth = pd.read_parquet(truth_path)
        by_id = dict(zip(truth['record_id'], truth['true_issue']))

        def _judge(a):
            ev = a.get('evidence', [])
            if not ev:
                return None
            act = 0
            for e in ev:
                t = by_id.get(e['record_id'])
                if t is None:
                    continue
                if t == a['issue'] or (a['tier'] != 'emerging' and t in MANDATORY):
                    act += 1
            return int(act >= max(1, len(ev) // 2))

        label = {a['alert_id']: _judge(a) for a in alerts}
        label = {k: v for k, v in label.items() if v is not None}
        source = 'SYNTHETIC-TRUTH'
    else:
        return {'status': 'NOT RUN'}

    def _tier_stats(ids):
        sub = [a for a in alerts if a['alert_id'] in ids and a['alert_id'] in label]
        n = len(sub)
        k = sum(label[a['alert_id']] for a in sub)
        lo, hi = metrics.wilson(k, n)
        return {'n': n, 'actionable': k, 'precision': round(k / n, 4) if n else None,
                'wilson_95': [round(lo, 4), round(hi, 4)]}

    return {
        'source': source,
        'overall': _tier_stats(list(label.keys())),
        'policy_tier': _tier_stats([a['alert_id'] for a in alerts if a['tier'] in ('policy', 'both')]),
        'emerging_tier': _tier_stats([a['alert_id'] for a in alerts if a['tier'] in ('emerging', 'both')]),
        'note': 'Policy tier is allowed to be lower by design: mandatory rules favor recall.',
    }


def run():
    processed = ROOT / cfg['paths']['processed']
    reports = ROOT / 'reports'
    reports.mkdir(parents=True, exist_ok=True)
    rec = pd.read_parquet(processed / 'records_scored.parquet')
    rec['ts'] = pd.to_datetime(rec['ts'])
    out = {'source': 'SYNTHETIC' if cfg.get('data_mode') == 'synthetic' else 'REAL',
           'data_mode': cfg.get('data_mode'),
           'generated_at': pd.Timestamp.now(tz='UTC').isoformat()}

    # ---- classification vs the team's own labels ----
    truth_path = ROOT / 'data' / 'synthetic' / 'truth.parquet'
    if truth_path.exists():
        truth = pd.read_parquet(truth_path)
        m = rec.merge(truth, on='record_id', how='inner')
        cls = metrics.classification_metrics(m['true_issue'], m['issue'],
                                             m[['channel', 'lang_pattern']])
        labels, cm = _confusion(m['true_issue'].tolist(), m['issue'].tolist())
        out['classification'] = {
            'source': 'SYNTHETIC',
            'macro_f1': round(cls['macro_f1'], 4),
            'weighted_f1': round(cls['weighted_f1'], 4),
            'by_channel': cls.get('by_channel', {}),
            'by_lang_pattern': cls.get('by_lang_pattern', {}),
            'per_class': cls.get('report', {}),
            'confusion_matrix': cm,
            'confusion_labels': labels,
            'n': len(m),
        }
        # also write CSV for the Trust page / manual review
        import pandas as _pd
        cm_df = _pd.DataFrame(cm, index=labels, columns=labels)
        cm_df.to_csv(reports / 'confusion_matrix.csv')
        out['accuracy_vs_coverage'] = metrics.accuracy_vs_coverage(
            m['p1'], m['issue'] == m['true_issue'])
        out['ece'] = round(metrics.ece(m['p1'], m['issue'] == m['true_issue']), 4)
    else:
        out['classification'] = {'status': 'NOT RUN', 'reason': 'no synthetic truth / dev labels'}

    # ---- severity / actionability vs dev labels if present ----
    _SEV_MAP = {0: 'low', 1: 'medium', 2: 'high', 3: 'critical'}
    def _sev_str(s):
        return s.map(lambda v: _SEV_MAP.get(v, v) if not isinstance(v, str) else v)

    dev_path = ROOT / 'data' / 'labels_dev' / 'dev_labels.csv'
    if dev_path.exists():
        dev = pd.read_csv(dev_path)
        d = rec.merge(dev, on='record_id', how='inner')
        if 'severity' in dev.columns and len(d) >= 30:
            sev = metrics.classification_metrics(_sev_str(d['severity_y']), _sev_str(d['severity_x']))
            out['severity_dev'] = {'source': 'DEV', 'macro_f1': round(sev['macro_f1'], 4), 'n': len(d)}
        else:
            out['severity_dev'] = {'status': 'NOT RUN'}
        if 'actionable' in dev.columns and len(d) >= 30:
            act = metrics.classification_metrics(d['actionable_y'].astype(int), d['actionable_x'].astype(int))
            out['actionability_dev'] = {'source': 'DEV', 'macro_f1': round(act['macro_f1'], 4), 'n': len(d)}
        else:
            out['actionability_dev'] = {'status': 'NOT RUN'}
    else:
        out['severity_dev'] = {'status': 'NOT RUN'}
        out['actionability_dev'] = {'status': 'NOT RUN'}

    # ---- radar ----
    out['radar'] = {
        'planted_incidents': _planted_summary(),
        'false_alerts': _false_alerts_per_store_week(),
        'note': ("Lead time versus B3 (fixed 5-in-7-days rule) is the team's own measure; "
                 "the organizers' lead time comes only from evaluate.py."),
    }
    grid_path = reports / 'radar_grid.csv'
    if grid_path.exists():
        g = pd.read_csv(grid_path)
        out['radar']['injection_tuning'] = g.head(5).to_dict('records')

    # ---- precision statement ----
    alerts = json.load(open(processed / 'alerts.json', encoding='utf-8'))
    out['precision_statement'] = _precision_statement(rec, alerts)

    # ---- policy: reviewed flags from the team's manual QA ----
    review_path = ROOT / 'data' / 'labels_dev' / 'policy_review.csv'
    if review_path.exists():
        rv = pd.read_csv(review_path)
        out['policy_review'] = {'source': 'DEV', 'n_reviewed': len(rv),
                                'precision': round(rv['correct'].mean(), 4) if 'correct' in rv else None}
    else:
        out['policy_review'] = {'status': 'NOT RUN'}

    json.dump(out, open(reports / 'metrics.json', 'w'), indent=2, default=str)
    metrics.log_run({'data_mode': cfg.get('data_mode'),
                     'classification_macro_f1': (out.get('classification') or {}).get('macro_f1')},
                    cfg, path=str(reports / 'eval_log.csv'))

    # ---- export files for the organizers' evaluate.py (column names from config) ----
    detections = json.load(open(processed / 'radar_alerts.json', encoding='utf-8'))
    evaluate_adapter.export(rec, detections)
    print('evaluate: metrics.json written')
    print(json.dumps({k: v for k, v in out.items()
                      if k in ('classification', 'radar', 'precision_statement')},
                     indent=2, default=str))
